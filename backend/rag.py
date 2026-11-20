import re
import os

from config import BUCKET
from db import sb, embed, llm


SYSTEM = """You are an automotive assistant answering ONLY from the brochure excerpts provided.

Rules:
- Use only facts in the excerpts. If something is missing, say "not found in the uploaded brochures". Never guess specs or prices.
- Cite every factual claim with its source tag like [S1], [S2].
- For comparisons, return a markdown table (one column per vehicle/variant) followed by a 2-3 sentence summary. If one side lacks data, mark it "Not in brochure".
- For feature lists, use concise bullet points grouped by category (safety, comfort, tech, powertrain).
- Be concise and exact with numbers and units."""


COMPARE = re.compile(
    r"\b(compare|comparison|versus|difference|differ|better)\b",
    re.I
)


def _vehicles():
    return sb.table("vehicles").select("id,brand,model").execute().data


def _mentioned(question, vehicles):
    q = question.lower()

    return [
        v for v in vehicles
        if v["model"].lower() in q
        or f'{v["brand"]} {v["model"]}'.lower() in q
    ]


def _retrieve(qvec, vehicle_id, k):
    return sb.rpc(
        "match_chunks",
        {
            "query_embedding": qvec,
            "match_count": k,
            "filter_vehicle": vehicle_id
        }
    ).execute().data or []


def answer(question: str, history: list[dict]):

    vehicles = _vehicles()
    named = _mentioned(question, vehicles)

    comparing = bool(COMPARE.search(question))
    k = 10 if comparing else 7

    # Short follow-ups borrow the previous user question for retrieval
    prev = [
        h["content"]
        for h in history
        if h["role"] == "user"
    ][-1:]

    ctx_q = (
        question
        if len(question) > 40 or not prev
        else f"{prev[0]} {question}"
    )

    qvec = embed([ctx_q])[0]

    # Follow-up: reuse vehicles from the last user turn
    if not named:
        for h in reversed(history):
            if h["role"] == "user":
                named = _mentioned(h["content"], vehicles)
                if named:
                    break

    hits = []

    if named:
        # Separate retrieval per vehicle
        for v in named:
            hits += _retrieve(qvec, v["id"], k)
    else:
        hits = _retrieve(qvec, None, k + 3)

    seen = set()
    sources = []
    blocks = []

    for h in hits:
        if h["id"] in seen:
            continue

        seen.add(h["id"])
        n = len(sources) + 1

        url = sb.storage.from_(BUCKET).get_public_url(
            h["storage_path"]
        )

        sources.append({
            "tag": f"S{n}",
            "filename": h["filename"],
            "page": h["page_number"],
            "vehicle": h["model"],
            "url": url,
            "score": round(h["similarity"], 3)
        })

        blocks.append(
            f"[S{n}] ({h['model']} - {h['filename']}, "
            f"page {h['page_number']})\n{h['content']}"
        )

    if not blocks:
        return (
            "I couldn't find anything in the uploaded brochures. "
            "Ask an admin to upload the relevant brochure.",
            []
        )

    msgs = [
        {
            "role": h["role"],
            "content": h["content"]
        }
        for h in history[-6:]
    ]

    msgs.append({
        "role": "user",
        "content": (
            "Brochure excerpts:\n\n"
            + "\n\n".join(blocks)
            + f"\n\nQuestion: {question}"
        )
    })

    # Groq LLM response
    response = llm.chat.completions.create(
        model=os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-120b"
        ),
        messages=[
            {"role": "system", "content": SYSTEM},
            *msgs
        ],
        max_completion_tokens=1600,
        temperature=0.1
    )

    answer_text = response.choices[0].message.content or ""

    # Extract cited source numbers
    cited = set(
        re.findall(r"\[S(\d+)\]", answer_text)
    )

    selected_sources = [
        s for s in sources
        if s["tag"][1:] in cited
    ]

    return answer_text, selected_sources or sources[:3]