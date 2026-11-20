# 🚗 Automotive AI Assistant

RAG chatbot over car brochures. Admins upload PDFs; users ask questions, list features, compare cars (Alcazar vs Creta) and variants, and every answer links back to the brochure page it came from.

**Stack:** React (Vite) · FastAPI · Supabase (PostgreSQL + pgvector + Storage) · Claude (answers) · OpenAI `text-embedding-3-small` (embeddings)

## Architecture
```
React ──► FastAPI ──► Supabase Storage (PDFs)
              │──► PyMuPDF → page-aware chunks → embeddings → pgvector
              └──► question → vehicle detection → per-vehicle vector search (match_chunks)
                   → grounded prompt → Claude → answer + [S#] citations → chat_messages
```
- **Chunking:** per page, ~900 chars with 150 overlap; each chunk keeps vehicle + page number.
- **Comparisons:** retrieval runs *separately per detected vehicle* so both sides are always in context; the model returns a markdown table.
- **Grounding:** answers only from excerpts, citations `[S1]`, "not found in the uploaded brochures" when data is missing.
- **Variants:** extracted from brochure text into the `variants` table at ingest time (best effort).

## Setup
### 1. Supabase
Create a project, open **SQL Editor**, run `sql/schema.sql` (enables pgvector, creates tables, HNSW index, `match_chunks`, and a public `brochures` bucket).

### 2. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # fill in keys
uvicorn main:app --reload --port 8000
```
### 3. Frontend
```bash
cd frontend
cp .env.example .env     # VITE_API_URL=http://localhost:8000
npm install && npm run dev
```
Open http://localhost:5173 → **Documents (Admin)**, enter your `ADMIN_TOKEN`, upload the Alcazar and Creta brochures (set Brand/Model), wait for status **ready**, then use **Chat**.

## API
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/documents` | Upload PDF (admin token header) |
| GET | `/api/documents` | List documents + status |
| POST | `/api/documents/{id}/reprocess` | Re-run ingestion |
| DELETE | `/api/documents/{id}` | Delete file + chunks |
| GET | `/api/vehicles` | Vehicles and variants |
| POST | `/api/chat` | `{message, session_id?}` → `{answer, sources, session_id}` |
| GET | `/api/chat/{session_id}` | Chat history |

## Deployment
- **Backend → Render:** New Web Service from this repo (uses `render.yaml`), add env vars. Set `ALLOWED_ORIGINS` to your Vercel URL.
- **Frontend → Vercel:** root directory `frontend`, env `VITE_API_URL=<render url>`.
- Free Render instances sleep; open `/api/health` before a demo.

## Sample questions to test
- List the features of the Hyundai Alcazar
- Compare Hyundai Alcazar vs Creta
- Compare Creta SX vs SX(O)
- What is the boot space of the Alcazar? (should cite a page)
- Does the Creta have a flying-car mode? (should answer "not found")

## Notes / limitations
- Scanned (image-only) PDFs are flagged `failed`; add OCR (e.g. Tesseract) to support them.
- Upload/delete are protected by a shared `ADMIN_TOKEN` header. Replace with Supabase Auth for production.
- Embedding dimension is 1536; if you change `EMBED_MODEL`, update `vector(1536)` in the schema.

## Demo video script (2–3 min)
1. Upload both brochures, show status → ready. 2. Ask a feature question, click a source chip to open the PDF page. 3. Compare Alcazar vs Creta. 4. Compare two variants. 5. Show Supabase tables and the repo.
