# Frontend Architecture (lite-rag workbench)

## Goals

- Build a **local-first internal tool UI** for Lite-RAG.
- Keep backend contract unchanged as much as possible.
- Provide polished, production-like UX for:
  - knowledge base management,
  - file upload/maintenance,
  - search mode testing (`vector` / `fts` / `hybrid`).

## Stack Selection

- **Vite + React + TypeScript**
  - Fast local startup
  - Minimal configuration
  - Type-safe API integration
- **Tailwind CSS**
  - Utility-first speed
  - Easy consistency across views
  - Controlled visual language for an internal workbench
- **React Router** for route structure
- **No heavy state libraries** (simple hooks are sufficient at this scope)

## Project Structure

```txt
web/
  src/
    components/
      layout.tsx        # app shell/sidebar
      ui.tsx            # reusable visual primitives
    hooks/
      useAsync.ts       # load/refresh async resources
    lib/
      api.ts            # API client + error handling
      format.ts         # formatting helpers
      types.ts          # typed contracts
    pages/
      kb-list-page.tsx
      kb-detail-page.tsx
      search-page.tsx
    App.tsx
    main.tsx
    styles.css
```

## Route Design

- `/kbs`
  - list all KBs
  - create KB inline
  - delete KB with confirmation
- `/kbs/:kbRef`
  - KB metadata editing
  - file upload form
  - file list + delete with confirmation
- `/search`
  - query input
  - optional KB scope
  - explicit mode switch (`hybrid` recommended first)
  - top-k controls
  - result cards for chunk-level inspection

## API Mapping

Base URL is configurable through `VITE_API_BASE_URL`.

- `GET /kb` → list KBs
- `POST /kb` → create KB
- `GET /kb/{kb_ref}` → KB detail
- `PATCH /kb/{kb_ref}` → update KB
- `DELETE /kb/{kb_ref}` → delete KB
- `GET /file?kb=<ref>` → list files by KB
- `DELETE /file/{file_id}` → delete file
- `POST /search` → run retrieval

Upload UX required binary file transfer, so backend gained one additive endpoint:

- `POST /file/upload` (`multipart/form-data`)
  - fields: `kb`, `file`, optional `title`
  - server stores temp file then reuses existing `store.add_file(...)`

This keeps original JSON `/file` endpoint intact and backwards-compatible.

## UX Notes

- Distinct dark workbench aesthetic (not marketing style)
- Strong hierarchy with dedicated display/body fonts
- High-clarity loading / empty / error states
- Confirmations for destructive actions
- Reusable panels/buttons/inputs for consistency
- Staggered reveal animation for lists and sections

## Local Development

1. Start backend: `lite-rag-api`
2. In `web/`:
   - `cp .env.example .env`
   - `npm install`
   - `npm run dev`

Default frontend URL: `http://127.0.0.1:5173`
