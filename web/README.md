# lite-rag web

Frontend workbench for local Lite-RAG API.

## Quick Start

```bash
cp .env.example .env
npm install
npm run dev
```

Default URL:

```txt
http://127.0.0.1:5173
```

## Environment

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Build

```bash
npm run build
npm run preview
```

## Screens / Routes

- `/kbs` knowledge base list + create/delete
- `/kbs/:kbRef` knowledge base details + file upload/delete
- `/search` query testing page with vector/fts/hybrid mode switch and rerank override selector
