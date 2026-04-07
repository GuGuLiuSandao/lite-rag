# Frontend Specification

## Scope

This frontend is a local knowledge-base workbench for small-scale internal use.
It focuses on three main tasks:

- manage knowledge bases
- manage files inside a knowledge base
- run retrieval experiments with `vector`, `fts`, and `hybrid`

Non-goals for this phase:

- authentication and permissions
- multi-tenant support
- online document editing
- workflow orchestration
- analytics dashboards

## Routes

### `/kbs`

Purpose:

- list all knowledge bases
- create a new knowledge base
- delete an existing knowledge base
- enter a specific knowledge base detail view

States:

- loading
- empty
- error
- normal list

Primary actions:

- create knowledge base
- refresh list
- open detail page
- delete knowledge base with confirmation

### `/kbs/:kbRef`

Purpose:

- inspect and edit knowledge base metadata
- upload files into the current knowledge base
- inspect file list
- delete files

States:

- loading kb metadata
- loading file list
- empty file list
- upload in progress
- error

Primary actions:

- edit name/description
- upload file
- refresh
- delete file with confirmation

### `/search`

Purpose:

- test retrieval quality
- compare search modes
- inspect returned chunks and metadata

States:

- idle
- searching
- no results
- error
- results

Primary actions:

- choose kb scope
- set search mode
- set recall/final top-k
- run search

## API Mapping

### Knowledge Base List Page

- `GET /kb`
  - load all knowledge bases
- `POST /kb`
  - create a knowledge base
- `DELETE /kb/{kb_ref}`
  - delete a knowledge base

### Knowledge Base Detail Page

- `GET /kb/{kb_ref}`
  - load kb detail
- `PATCH /kb/{kb_ref}`
  - update kb metadata
- `GET /file?kb={kb_ref}`
  - load files in current kb
- `POST /file/upload`
  - upload a file using multipart form
- `DELETE /file/{file_id}`
  - delete file and its index data

### Search Page

- `GET /kb`
  - load kb selector options
- `POST /search`
  - run retrieval query

## Response Fields Used by Frontend

### Knowledge Base

- `id`
- `name`
- `description`
- `created_at`
- `updated_at`

### File

- `id`
- `kb_id`
- `kb_name`
- `title`
- `source_name`
- `stored_path`
- `chunk_count`
- `created_at`
- `updated_at`

### Search Result

- `chunk_id`
- `kb_id`
- `kb_name`
- `file_id`
- `file_name`
- `chunk_index`
- `score`
- `text`

## Interaction Rules

- destructive actions must use browser confirmation
- failed requests should surface backend error text directly when available
- pages should not silently fail
- empty states should always include next-step guidance
- search mode must stay explicit and visible to users

## Visual Direction

- internal workbench feel
- strong information hierarchy
- restrained dark theme
- moderate data density
- minimal decorative motion
- reusable panel-based layout

## Acceptance Criteria

The frontend is considered complete for this phase when:

- all three routes render and work against the FastAPI backend
- knowledge base creation and deletion work end-to-end
- file upload and deletion work end-to-end
- search works for `vector`, `fts`, and `hybrid`
- loading, empty, and error states are present on each route
- README includes run instructions for backend + frontend
