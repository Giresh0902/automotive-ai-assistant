"""PDF -> pages -> chunks -> Gemini embeddings -> pgvector.
Also extracts vehicle variants using Groq.
"""

import json
import re
import os
import pymupdf as fitz

from config import BUCKET
from db import sb, embed, llm

CHUNK, OVERLAP = 900, 150


def split(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()

    if len(text) <= CHUNK:
        return [text] if text else []

    parts, i = [], 0

    while i < len(text):
        end = min(i + CHUNK, len(text))

        if end < len(text):
            cut = max(
                text.rfind("\n", i, end),
                text.rfind(". ", i, end)
            )

            if cut > i + CHUNK // 2:
                end = cut + 1

        parts.append(text[i:end].strip())

        if end >= len(text):
            break

        i = end - OVERLAP

    return [p for p in parts if p]


def extract_variants(
    vehicle_id: str,
    label: str,
    pages: list[str]
):
    sample = "\n".join(pages)[:14000]

    try:
        response = llm.chat.completions.create(
            model=os.getenv(
                "GROQ_MODEL",
                "openai/gpt-oss-120b"
            ),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract car variants from brochure text. "
                        "Reply with ONLY a JSON array of objects "
                        "with keys: name, engine, transmission, "
                        "fuel, price (strings or null). "
                        "Only include variants explicitly named "
                        "in the text. Return [] if none."
                    )
                },
                {
                    "role": "user",
                    "content": f"Vehicle: {label}\n\n{sample}"
                }
            ],
            max_completion_tokens=1500,
            temperature=0
        )

        txt = response.choices[0].message.content or ""

        txt = re.sub(
            r"^```(?:json)?|```$",
            "",
            txt.strip(),
            flags=re.M
        ).strip()

        variants = json.loads(txt)

        for v in variants:
            if v.get("name"):
                sb.table("variants").upsert(
                    {
                        "vehicle_id": vehicle_id,
                        **{
                            k: v.get(k)
                            for k in (
                                "name",
                                "engine",
                                "transmission",
                                "fuel",
                                "price"
                            )
                        }
                    },
                    on_conflict="vehicle_id,name"
                ).execute()

    except Exception as e:
        print("Variant extraction skipped:", e)


def process_document(
    doc_id: str,
    vehicle_id: str,
    label: str
):
    try:
        # Get PDF storage path
        document = (
            sb.table("documents")
            .select("storage_path")
            .eq("id", doc_id)
            .single()
            .execute()
            .data
        )

        path = document["storage_path"]

        # Download PDF from Supabase
        pdf_data = sb.storage.from_(BUCKET).download(path)

        # Extract PDF pages
        pdf = fitz.open(
            stream=pdf_data,
            filetype="pdf"
        )

        pages = [
            page.get_text("text")
            for page in pdf
        ]

        pdf.close()

        if not any(text.strip() for text in pages):
            raise ValueError(
                "No extractable text (scanned PDF?). OCR is not enabled."
            )

        # Split pages into chunks
        rows = []
        texts = []

        for page_number, page_text in enumerate(pages, 1):
            for chunk in split(page_text):

                rows.append({
                    "page": page_number,
                    "content": chunk
                })

                texts.append(
                    f"{label} | page {page_number}\n{chunk}"
                )

        if not texts:
            raise ValueError("No text chunks generated from PDF.")

        # Generate Gemini document embeddings
        vectors = embed(
            texts,
            task_type="RETRIEVAL_DOCUMENT"
        )

        if len(vectors) != len(rows):
            raise ValueError("Embedding count does not match chunk count.")

        # Prepare database records
        batch = [
            {
                "document_id": doc_id,
                "vehicle_id": vehicle_id,
                "page_number": row["page"],
                "content": row["content"],
                "embedding": vector,
                "metadata": {
                    "label": label
                }
            }
            for row, vector in zip(rows, vectors)
        ]

        # Remove old chunks only after embeddings succeed
        sb.table("document_chunks").delete().eq(
            "document_id",
            doc_id
        ).execute()

        # Insert chunks in batches
        for i in range(0, len(batch), 100):
            sb.table("document_chunks").insert(
                batch[i:i + 100]
            ).execute()

        # Extract vehicle variants using Groq
        extract_variants(
            vehicle_id,
            label,
            pages
        )

        # Update document status
        sb.table("documents").update(
            {
                "status": "ready",
                "page_count": len(pages),
                "error": None
            }
        ).eq("id", doc_id).execute()

        print(
            f"Document processed successfully: {label} "
            f"({len(pages)} pages, {len(batch)} chunks)"
        )

    except Exception as e:

        print("Document processing failed:", e)

        sb.table("documents").update(
            {
                "status": "failed",
                "error": str(e)[:500]
            }
        ).eq("id", doc_id).execute()