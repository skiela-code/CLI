# Architecture

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      Browser (GUI)                       │
│         Jinja2 + HTMX + Bootstrap 5                      │
└─────────────┬───────────────────────────────┬───────────┘
              │ HTTP                          │
              ▼                               ▼
┌─────────────────────────┐     ┌──────────────────────────┐
│       FastAPI App        │     │    Static Assets          │
│                         │     │    /static/css,js          │
│  ┌───────────────────┐  │     └──────────────────────────┘
│  │   Auth Middleware  │  │
│  │  (OIDC / DevLogin) │  │
│  └───────┬───────────┘  │
│          ▼               │
│  ┌───────────────────┐  │
│  │   Route Handlers   │  │
│  │  (deals, templates, │ │
│  │   docs, approvals,  │ │
│  │   pricing, search)  │ │
│  └───────┬───────────┘  │
│          ▼               │
│  ┌───────────────────┐  │     ┌──────────────────────────┐
│  │    Services Layer   │──────▶│   Integrations            │
│  │  - doc_generator   │  │    │  - Pipedrive Client       │
│  │  - template_engine │  │    │  - Claude AI Provider     │
│  │  - red_flags       │  │    │  - Notification (SMTP)    │
│  │  - search (FTS)    │  │    └──────────────────────────┘
│  │  - notifications   │  │
│  └───────┬───────────┘  │
│          ▼               │
│  ┌───────────────────┐  │
│  │   SQLAlchemy Async  │  │
│  │   (asyncpg)        │  │
│  └───────┬───────────┘  │
└──────────┼──────────────┘
           ▼
┌──────────────────────────┐
│     PostgreSQL 16         │
│  - Data storage           │
│  - FTS indexes (GIN)      │
│  - Search triggers        │
└──────────────────────────┘
```

## Request Flows

### 1. Generate Document

```
User -> POST /documents/generate
  -> Create Document record (status=draft)
  -> asyncio.create_task(generate_document)
  -> Redirect to /documents/{id}

Background task:
  -> Load template + deal + pricing
  -> For each placeholder:
      - deal_field -> resolve from Deal model
      - content_block -> load from ContentBlock
      - ai_generated -> call ClaudeProvider.generate_section()
  -> For commercial offers: ClaudeProvider.generate_narrative()
  -> Render DOCX via template_engine.render_document()
  -> Run red_flags.check_red_flags()
  -> Save DocumentVersion + update Document
```

### 2. Approval Flow

```
User -> POST /documents/{id}/approve/request
  -> Select approver from user list
  -> Create Approval record (status=pending)
  -> Update Document status to pending_approval
  -> send_notification() to approver (DB inbox + optional SMTP)
  -> Redirect

Approver -> GET /approvals (inbox)
  -> See pending approvals
  -> POST /approvals/{id}/decide (approve/reject + comment)
  -> Update Approval and Document status
  -> Notify document creator
```

### 3. Template Upload + Mapping

```
User -> POST /templates/upload (multipart form with DOCX)
  -> Save file to upload_path
  -> extract_placeholders() -> find all {{TOKEN}} patterns
  -> Create Template + TemplatePlaceholder records
  -> Redirect to template detail

User -> GET /templates/{id}/builder
  -> Show all placeholders with mapping form
  -> POST /templates/{id}/builder
  -> Save source type, field mapping, AI prompt, content block for each
```

### 4. Attach to Pipedrive

```
User -> POST /documents/{id}/attach-pipedrive
  -> Load Document + Deal (must have pipedrive_id)
  -> Load latest DocumentVersion
  -> PipedriveClient.attach_file() -> POST /files
  -> PipedriveClient.create_note() -> POST /notes
  -> Audit log
```

## Async Job Handling

**Decision: asyncio.create_task() (in-process)**

Justification:
1. **No extra infrastructure** — No Redis, no Celery workers, no message broker.
2. **I/O-bound work** — Document generation involves API calls (Claude, Pipedrive) and file I/O, which is ideal for async.
3. **Event loop reuse** — FastAPI already runs in an async event loop; we leverage it directly.
4. **Status tracking via DB** — Job status is tracked by Document.status + DocumentVersion existence. The UI polls via HTMX.
5. **Trade-off accepted** — Jobs don't survive server restarts. For V1, this is acceptable since generation is fast (seconds) and can be re-triggered.

If V2 requires durable jobs, we'd add ARQ (async Redis queue) with minimal code changes since the generation function is already async.
