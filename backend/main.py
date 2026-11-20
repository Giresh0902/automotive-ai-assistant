import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from config import BUCKET, ADMIN_TOKEN, ALLOWED_ORIGINS
from db import sb
from ingest import process_document
from rag import answer

app = FastAPI(title="Automotive AI Assistant")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])

def admin(token: str | None):
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid admin token")

@app.get("/api/health")
def health(): return {"ok": True}

@app.get("/api/documents")
def list_documents():
    docs = sb.table("documents").select("*, vehicles(brand, model)").order("uploaded_at", desc=True).execute().data
    for d in docs:
        d["url"] = sb.storage.from_(BUCKET).get_public_url(d["storage_path"])
    return docs

@app.post("/api/documents")
async def upload(bg: BackgroundTasks, file: UploadFile = File(...), brand: str = Form(...), model: str = Form(...),
                 x_admin_token: str | None = Header(None)):
    admin(x_admin_token)
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed")
    data = await file.read()
    if not data.startswith(b"%PDF"): raise HTTPException(400, "File is not a valid PDF")
    if len(data) > 50 * 1024 * 1024: raise HTTPException(413, "PDF larger than 50 MB")
    brand, model = brand.strip(), model.strip()
    veh = sb.table("vehicles").upsert({"brand": brand, "model": model}, on_conflict="brand,model").execute().data[0]
    path = f"{uuid.uuid4()}-{file.filename.replace(' ', '_')}"
    sb.storage.from_(BUCKET).upload(path, data, {"content-type": "application/pdf"})
    doc = sb.table("documents").insert({"vehicle_id": veh["id"], "filename": file.filename, "storage_path": path}).execute().data[0]
    bg.add_task(process_document, doc["id"], veh["id"], f"{brand} {model}")
    return doc

@app.post("/api/documents/{doc_id}/reprocess")
def reprocess(doc_id: str, bg: BackgroundTasks, x_admin_token: str | None = Header(None)):
    admin(x_admin_token)
    d = sb.table("documents").select("*, vehicles(brand, model)").eq("id", doc_id).single().execute().data
    sb.table("documents").update({"status": "processing", "error": None}).eq("id", doc_id).execute()
    v = d["vehicles"] or {"brand": "", "model": ""}
    bg.add_task(process_document, doc_id, d["vehicle_id"], f'{v["brand"]} {v["model"]}'.strip())
    return {"ok": True}

@app.delete("/api/documents/{doc_id}")
def delete(doc_id: str, x_admin_token: str | None = Header(None)):
    admin(x_admin_token)
    d = sb.table("documents").select("storage_path").eq("id", doc_id).single().execute().data
    sb.storage.from_(BUCKET).remove([d["storage_path"]])
    sb.table("documents").delete().eq("id", doc_id).execute()  # chunks cascade
    return {"ok": True}

@app.get("/api/vehicles")
def vehicles():
    return sb.table("vehicles").select("*, variants(*)").order("brand").execute().data

class ChatIn(BaseModel):
    message: str
    session_id: str | None = None

@app.post("/api/chat")
def chat(body: ChatIn):
    msg = body.message.strip()
    if not msg: raise HTTPException(400, "Empty message")
    sid = body.session_id or sb.table("chat_sessions").insert({}).execute().data[0]["id"]
    history = sb.table("chat_messages").select("role,content").eq("session_id", sid).order("created_at").execute().data
    sb.table("chat_messages").insert({"session_id": sid, "role": "user", "content": msg}).execute()
    text, sources = answer(msg, history)
    sb.table("chat_messages").insert({"session_id": sid, "role": "assistant", "content": text, "sources": sources}).execute()
    return {"session_id": sid, "answer": text, "sources": sources}

@app.get("/api/chat/{session_id}")
def history(session_id: str):
    return sb.table("chat_messages").select("role,content,sources,created_at").eq("session_id", session_id).order("created_at").execute().data
