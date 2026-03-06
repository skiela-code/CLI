# Document Library & Customer Profiles — Implementation Plan

## Design Decisions (per user input)
- **Extend existing Document model** — add `source` field (generated/uploaded), no separate LibraryDocument
- **Use Deal.org_name directly** — no separate Company model; customer profiles are views grouped by org_name
- **pdfplumber** for PDF text extraction

---

## PHASE 1: Database Schema (Migration 003)

### 1.1 Modify `Document` model — add library fields

Add to existing Document model:
```python
source: Mapped[str] = mapped_column(String(20), default="generated")  # "generated" | "uploaded"
file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # for uploaded docs
extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # full extracted text
company_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # matched company
company_match_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
classification_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
import_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "queued" | "approved" | "rejected"
```

### 1.2 New `ContractMetadata` model

```python
class ContractMetadata(Base):
    __tablename__ = "contract_metadata"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), unique=True)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    signed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    initial_term_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    renewal_term_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    notice_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pricing_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_confidence: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # per-field confidences
    extraction_snippets: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # source text per field
    metadata_status: Mapped[str] = mapped_column(String(20), default="imported")  # imported|auto_tagged|needs_review|approved

    document = relationship("Document", backref="contract_metadata_rel")
```

### 1.3 New `ServiceCatalog` model

```python
class ServiceCatalog(Base):
    __tablename__ = "service_catalog"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

### 1.4 New `DocumentService` junction table

```python
class DocumentService(Base):
    __tablename__ = "document_services"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_catalog.id", ondelete="CASCADE"))
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

### 1.5 New `DocumentRelationship` model

```python
class DocumentRelationship(Base):
    __tablename__ = "document_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    child_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    relationship_type: Mapped[str] = mapped_column(String(50), default="annex")  # annex|amendment|renewal
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

### 1.6 New `ImportJob` model

```python
class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="processing")  # processing|completed|failed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

### 1.7 Extend DocType enum

Add `other` to existing DocType:
```python
class DocType(str, enum.Enum):
    CONTRACT = "contract"
    NDA = "nda"
    PURCHASE_ANNEX = "purchase_annex"
    COMMERCIAL_OFFER = "commercial_offer"
    OTHER = "other"
```

### 1.8 Migration file: `migrations/versions/003_document_library.py`

- Add columns to `documents`: source, file_path, extracted_text, company_name, company_match_confidence, classification_confidence, import_status
- Create `contract_metadata` table
- Create `service_catalog` table
- Create `document_services` table
- Create `document_relationships` table
- Create `import_jobs` table
- Add FTS trigger update for documents to include extracted_text
- Backfill existing documents with `source='generated'`

---

## PHASE 2: Text Extraction Service

### 2.1 New file: `app/services/text_extraction.py`

```python
async def extract_text(file_path: str) -> str:
    """Extract text from DOCX or PDF file."""
```

- For `.docx`: use python-docx (already installed) to extract all paragraph text
- For `.pdf`: use pdfplumber to extract text page-by-page
- Return concatenated text string
- Handle errors gracefully (return empty string on failure)

### 2.2 New dependency: `pdfplumber` in requirements.txt

---

## PHASE 3: Document Classification Service

### 3.1 New file: `app/services/document_classifier.py`

```python
async def classify_document(filename: str, text: str) -> tuple[str, float]:
    """Classify document type. Returns (doc_type, confidence)."""
```

**Step 1 — Rule-based (fast, no AI):**
- Filename patterns: `contract`, `nda`, `annex`, `offer`, `proposal`
- Keyword density: count occurrences of type-specific keywords in text
- If high confidence (>0.8), return without AI

**Step 2 — AI classification (for ambiguous cases):**
- Use `get_llm_router().generate()` with a classification prompt
- System prompt: "Classify this document. Return ONLY one of: contract, nda, purchase_annex, commercial_offer, other"
- Parse AI response to extract type
- Return with confidence score

---

## PHASE 4: Metadata Extraction Service

### 4.1 New file: `app/services/metadata_extraction.py`

```python
async def extract_contract_metadata(text: str) -> dict:
    """Extract structured contract metadata from document text."""
```

**Step 1 — Rule-based keyword scanning:**
- Regex patterns for dates (effective date, signed date)
- Keyword search: "initial term", "renewal", "notice period", "auto-renew"
- Extract paragraphs containing these keywords

**Step 2 — AI structured extraction:**
- Send extracted snippets to LLM router
- System prompt requesting JSON output with specific fields
- Parse response, assign confidence scores per field
- Return: `{field: {value, confidence, source_snippet}}`

---

## PHASE 5: Company Matching Service

### 5.1 New file: `app/services/company_matching.py`

```python
async def match_company(db: AsyncSession, filename: str, text: str) -> tuple[str | None, float]:
    """Match document to a company. Returns (org_name, confidence)."""
```

**Matching signals (in priority order):**
1. Load all known org_names from `deals` table
2. Check filename for company name patterns
3. Search document text for known company names (case-insensitive)
4. Check for email domains matching known contacts
5. Return best match with confidence score

---

## PHASE 6: Renewal Computation Service

### 6.1 New file: `app/services/renewal_service.py`

```python
def compute_renewal(metadata: ContractMetadata) -> dict:
    """Compute renewal dates from contract metadata."""
```

Returns:
```python
{
    "current_term_start": date,
    "current_term_end": date,
    "next_renewal_date": date | None,
    "cancel_by_date": date | None,
    "renewal_status": "active" | "expiring_soon" | "expired" | "unknown"
}
```

Logic:
- `term_end = effective_date + initial_term_months`
- If `auto_renew` and past term_end: roll forward by `renewal_term_months` until future
- `cancel_by = next_renewal_date - notice_period_days`
- Status based on days until renewal (30/60/90 day thresholds)

---

## PHASE 7: Service Extraction

### 7.1 New file: `app/services/service_extraction.py`

```python
async def extract_services(db: AsyncSession, text: str) -> list[dict]:
    """Extract services from document text against the catalog."""
```

- Load service catalog from DB
- Use LLM router with prompt: "From this document, identify which of these services are mentioned: [catalog list]. Return JSON array."
- Parse response, match to catalog entries
- Flag unknown services for manual review
- Return list of `{service_id, confidence, source_snippet}`

---

## PHASE 8: Import Pipeline Service

### 8.1 New file: `app/services/import_pipeline.py`

```python
async def process_import(job_id: str, file_paths: list[str], user_id: str) -> None:
    """Background task: process uploaded files through the import pipeline."""
```

Pipeline steps per file:
1. Extract text (`text_extraction.py`)
2. Classify document (`document_classifier.py`)
3. Extract metadata (`metadata_extraction.py`)
4. Match company (`company_matching.py`)
5. Extract services (`service_extraction.py`)
6. Create Document record with `source="uploaded"`, `import_status="queued"`
7. Create ContractMetadata if type is contract
8. Create DocumentService entries
9. Update ImportJob progress

Uses `asyncio.create_task()` pattern from doc_generator.py.

---

## PHASE 9: Routes

### 9.1 New file: `app/api/library_routes.py` — prefix `/library`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/library` | Library main page — list uploaded documents, filters |
| GET | `/library/upload` | Upload page (drag & drop, multi-file) |
| POST | `/library/upload` | Handle file upload (multi-file + ZIP) |
| GET | `/library/import/{job_id}` | Import progress page |
| GET | `/library/queue` | Import queue — documents awaiting approval |
| POST | `/library/queue/{doc_id}/approve` | Approve queued document |
| POST | `/library/queue/{doc_id}/reject` | Reject queued document |
| POST | `/library/queue/{doc_id}/update` | Update metadata before approval |
| GET | `/library/{doc_id}` | Library document detail (metadata, text preview, services) |
| POST | `/library/{doc_id}/metadata` | Edit metadata |
| POST | `/library/{doc_id}/relate` | Create document relationship |
| GET | `/library/renewals` | Renewal dashboard |

### 9.2 New file: `app/api/customer_routes.py` — prefix `/customers`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/customers` | Customer list (grouped from deals + documents) |
| GET | `/customers/{org_name}` | Customer profile page |

### 9.3 New file: `app/api/services_routes.py` — prefix `/services`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/services` | Service catalog management |
| POST | `/services` | Add service to catalog |
| POST | `/services/{id}/delete` | Remove service |

---

## PHASE 10: Templates (UI)

### 10.1 Library pages
- `app/templates/pages/library.html` — Document list with source/type/company filters
- `app/templates/pages/library_upload.html` — Drag & drop upload area, file list, submit
- `app/templates/pages/library_import_progress.html` — Progress bar, file status table (HTMX polling)
- `app/templates/pages/library_queue.html` — Queue table: file, company, type, renewal, confidence, actions
- `app/templates/pages/library_detail.html` — Document metadata, text preview, services, relationships, edit form

### 10.2 Customer pages
- `app/templates/pages/customers.html` — Customer list with contract/renewal info
- `app/templates/pages/customer_profile.html` — Tabbed: Overview (contract, renewal, services, alerts), Documents (table), Timeline (chronological)

### 10.3 Other pages
- `app/templates/pages/renewal_dashboard.html` — Renewal table with 30/60/90 day filters
- `app/templates/pages/service_catalog.html` — Service CRUD

---

## PHASE 11: Navigation & Wiring

### 11.1 `app/main.py` — register new routers
```python
from app.api.library_routes import router as library_router
from app.api.customer_routes import router as customer_router
from app.api.services_routes import router as services_router
app.include_router(library_router)
app.include_router(customer_router)
app.include_router(services_router)
```

### 11.2 `app/templates/layouts/base.html` — add nav items
After "Documents" in sidebar:
- Library (icon: bi-archive)
- Customers (icon: bi-people)
- Renewals (icon: bi-calendar-check)

### 11.3 Enhance global search
Update `app/services/search.py` to include library documents (source="uploaded") in FTS results.

### 11.4 Enhance document generation
Update `app/services/doc_generator.py` to query library documents for the same company when generating, providing past contracts/offers as AI context.

---

## PHASE 12: Seed Data

Update `app/seed_data.py`:
- Add sample service catalog entries (Managed Kubernetes, Monitoring, Backup, 24/7 Support, Incident Response)
- Add sample library documents with contract metadata for demo purposes

---

## PHASE 13: Tests

New test files:
- `tests/test_text_extraction.py` — DOCX/PDF extraction
- `tests/test_classifier.py` — Rule-based classification
- `tests/test_metadata_extraction.py` — Keyword scanning
- `tests/test_renewal_service.py` — Renewal date computation
- `tests/test_company_matching.py` — Company name matching

---

## Implementation Order

1. **Phase 1** — Database schema (models + migration 003)
2. **Phase 2** — Text extraction service + pdfplumber dependency
3. **Phase 3** — Document classification
4. **Phase 4** — Metadata extraction
5. **Phase 5** — Company matching
6. **Phase 6** — Renewal computation
7. **Phase 7** — Service extraction + catalog model
8. **Phase 8** — Import pipeline (ties 2-7 together)
9. **Phase 9** — Routes (library, customers, services)
10. **Phase 10** — Templates (UI pages)
11. **Phase 11** — Navigation, search, doc generation integration
12. **Phase 12** — Seed data
13. **Phase 13** — Tests

---

## File Summary

### New files (25):
- `migrations/versions/003_document_library.py`
- `app/services/text_extraction.py`
- `app/services/document_classifier.py`
- `app/services/metadata_extraction.py`
- `app/services/company_matching.py`
- `app/services/renewal_service.py`
- `app/services/service_extraction.py`
- `app/services/import_pipeline.py`
- `app/api/library_routes.py`
- `app/api/customer_routes.py`
- `app/api/services_routes.py`
- `app/templates/pages/library.html`
- `app/templates/pages/library_upload.html`
- `app/templates/pages/library_import_progress.html`
- `app/templates/pages/library_queue.html`
- `app/templates/pages/library_detail.html`
- `app/templates/pages/customers.html`
- `app/templates/pages/customer_profile.html`
- `app/templates/pages/renewal_dashboard.html`
- `app/templates/pages/service_catalog.html`
- `tests/test_text_extraction.py`
- `tests/test_classifier.py`
- `tests/test_metadata_extraction.py`
- `tests/test_renewal_service.py`
- `tests/test_company_matching.py`

### Modified files (7):
- `app/models/models.py` — new models + enum extension
- `app/main.py` — register routers
- `app/templates/layouts/base.html` — sidebar nav
- `app/services/search.py` — include library docs
- `app/services/doc_generator.py` — load library context
- `app/seed_data.py` — sample catalog + library docs
- `requirements.txt` — add pdfplumber
