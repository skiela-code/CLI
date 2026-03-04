# ADR-003: UI Approach

## Status
Accepted

## Context
The platform needs a web GUI testable in a browser. Options:

1. **React/Vite SPA** — Rich UX, but adds build toolchain, CORS, state management
2. **Jinja2 + vanilla JS** — Simple but no interactivity
3. **Jinja2 + HTMX + Bootstrap** — Server-rendered with dynamic updates, zero build step
4. **Svelte/Vue + FastAPI** — Middle ground but still needs build toolchain

## Decision
**Jinja2 + HTMX + Bootstrap 5** — server-rendered HTML with HTMX for dynamic interactions.

## Rationale

| Criterion | React SPA | Jinja2+HTMX | Svelte |
|-----------|----------|-------------|--------|
| Build toolchain | Yes (Vite) | None | Yes |
| Bundle size | Large | Zero | Medium |
| Learning curve | High | Low | Medium |
| SEO/SSR | Needs setup | Native | Needs setup |
| API design | JSON API needed | No separate API | JSON API needed |
| Deployment | Static + API | Single server | Static + API |
| Interactivity | Full SPA | HTMX partial updates | Full SPA |

For V1:
- **Zero build step**: No node_modules, no webpack, no Vite, no npm scripts
- **Single deployment**: FastAPI serves both HTML and processes forms
- **HTMX**: Provides partial page updates for polling (generation status), form submissions, and dynamic content without JavaScript
- **Bootstrap 5**: Provides professional look with zero CSS writing
- **CDN delivery**: Bootstrap and HTMX loaded from CDN — no assets to manage

## Consequences
- No complex client-side state management
- All logic stays in Python (single language)
- Limited rich interactivity (no drag-and-drop, no real-time collaboration)
- Easy to replace with SPA in V2 since routes already serve data

## HTMX Usage
- Auto-polling for generation status (`hx-trigger="every 3s"`)
- Future: inline editing, dynamic form updates
