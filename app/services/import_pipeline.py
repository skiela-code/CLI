"""Import pipeline: background processing of uploaded documents."""

import asyncio
import os
import uuid
import zipfile
from datetime import datetime, date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.logging import log
from app.models.models import (
    ContractMetadata, DocStatus, DocType, Document, DocumentService,
    ImportJob, ServiceCatalog,
)
from app.services.text_extraction import extract_text
from app.services.document_classifier import classify_document
from app.services.metadata_extraction import extract_contract_metadata
from app.services.company_matching import match_company
from app.services.service_extraction import extract_services

settings = get_settings()

_running_imports: dict[str, asyncio.Task] = {}


def get_import_status(job_id: str) -> dict[str, Any]:
    """Check import job status."""
    task = _running_imports.get(job_id)
    if task is None:
        return {"status": "completed"}
    if task.done():
        _running_imports.pop(job_id, None)
        if task.exception():
            return {"status": "failed", "error": str(task.exception())}
        return {"status": "completed"}
    return {"status": "processing"}


async def start_import(
    db: AsyncSession,
    file_paths: list[str],
    user_id: uuid.UUID,
) -> str:
    """Create import job and launch background processing."""
    job = ImportJob(
        created_by=user_id,
        total_files=len(file_paths),
        processed_files=0,
        status="processing",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    job_id = str(job.id)
    task = asyncio.create_task(_process_import(job_id, file_paths, str(user_id)))
    _running_imports[job_id] = task
    log.info("import_started", job_id=job_id, file_count=len(file_paths))
    return job_id


def extract_zip(zip_path: str, extract_dir: str) -> list[str]:
    """Extract ZIP archive and return list of valid file paths."""
    paths = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_dir)
        for name in zf.namelist():
            if name.startswith("__MACOSX") or name.startswith("."):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in (".pdf", ".docx"):
                full_path = os.path.join(extract_dir, name)
                if os.path.isfile(full_path):
                    paths.append(full_path)
    return paths


async def _process_import(job_id: str, file_paths: list[str], user_id: str) -> None:
    """Background task: process each file through the import pipeline."""
    async with async_session_factory() as db:
        try:
            job = await db.get(ImportJob, uuid.UUID(job_id))
            if not job:
                return

            for i, file_path in enumerate(file_paths):
                try:
                    await _process_single_file(db, file_path, user_id, job)
                except Exception as e:
                    log.error("import_file_failed", file=file_path, error=str(e))

                job.processed_files = i + 1
                await db.commit()

            job.status = "completed"
            job.completed_at = datetime.utcnow()
            await db.commit()
            log.info("import_complete", job_id=job_id)

        except Exception as e:
            log.error("import_job_failed", job_id=job_id, error=str(e))
            try:
                job = await db.get(ImportJob, uuid.UUID(job_id))
                if job:
                    job.status = "failed"
                    await db.commit()
            except Exception:
                pass
        finally:
            _running_imports.pop(job_id, None)


async def _process_single_file(
    db: AsyncSession, file_path: str, user_id: str, job: ImportJob
) -> None:
    """Process a single file through the import pipeline."""
    filename = os.path.basename(file_path)
    log.info("processing_file", filename=filename)

    # 1. Extract text
    text = extract_text(file_path)

    # 2. Classify document
    doc_type_str, classification_confidence = await classify_document(filename, text)

    # 3. Match company
    company_name, company_confidence = await match_company(db, filename, text)

    # 4. Create Document record
    doc = Document(
        title=filename,
        doc_type=DocType(doc_type_str),
        status=DocStatus.DRAFT,
        source="uploaded",
        file_path=file_path,
        extracted_text=text,
        company_name=company_name,
        company_match_confidence=company_confidence,
        classification_confidence=classification_confidence,
        import_status="queued",
        import_job_id=job.id,
        created_by=uuid.UUID(user_id),
    )
    db.add(doc)
    await db.flush()

    # 5. Extract contract metadata if it's a contract
    if doc_type_str == "contract" and text.strip():
        metadata_result = await extract_contract_metadata(text)
        cm = ContractMetadata(document_id=doc.id)

        confidences = {}
        snippets = {}

        for field, data in metadata_result.items():
            value = data.get("value")
            conf = data.get("confidence", 0.5)
            snippet = data.get("snippet", "")
            confidences[field] = conf
            snippets[field] = snippet

            if field == "effective_date" and isinstance(value, str):
                try:
                    cm.effective_date = date.fromisoformat(value)
                except (ValueError, TypeError):
                    pass
            elif field == "signed_date" and isinstance(value, str):
                try:
                    cm.signed_date = date.fromisoformat(value)
                except (ValueError, TypeError):
                    pass
            elif field == "initial_term_months":
                try:
                    cm.initial_term_months = int(value)
                except (ValueError, TypeError):
                    pass
            elif field == "renewal_term_months":
                try:
                    cm.renewal_term_months = int(value)
                except (ValueError, TypeError):
                    pass
            elif field == "auto_renew":
                cm.auto_renew = bool(value)
            elif field == "notice_period_days":
                try:
                    cm.notice_period_days = int(value)
                except (ValueError, TypeError):
                    pass
            elif field == "pricing_summary":
                cm.pricing_summary = str(value) if value else None

        cm.extraction_confidence = confidences
        cm.extraction_snippets = snippets
        cm.metadata_status = "auto_tagged"
        db.add(cm)

    # 6. Extract services
    svc_results = await extract_services(db, text)
    for svc in svc_results:
        ds = DocumentService(
            document_id=doc.id,
            service_id=uuid.UUID(svc["service_id"]),
            confidence=svc.get("confidence"),
            source_snippet=svc.get("source_snippet"),
        )
        db.add(ds)

    await db.flush()
