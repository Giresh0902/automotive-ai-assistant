import os

from supabase import create_client
from groq import Groq
from google import genai
from google.genai import types

from config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)


# -----------------------------
# Supabase connection
# -----------------------------

sb = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)


# -----------------------------
# Groq LLM connection
# -----------------------------

llm = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


# -----------------------------
# Gemini embedding connection
# -----------------------------

gemini = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

EMBED_MODEL = os.getenv(
    "GEMINI_EMBED_MODEL",
    "gemini-embedding-001"
)

EMBED_DIMENSIONS = 1536


# -----------------------------
# Generate embeddings
# -----------------------------

def embed(
    texts: list[str],
    task_type: str = "RETRIEVAL_QUERY"
) -> list[list[float]]:

    out = []

    for i in range(0, len(texts), 50):

        batch = texts[i:i + 50]

        response = gemini.models.embed_content(
            model=EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBED_DIMENSIONS,
                task_type=task_type
            )
        )

        if not response.embeddings:
            raise ValueError("Gemini returned no embeddings.")

        for embedding in response.embeddings:

            if not embedding.values:
                raise ValueError("Empty embedding returned by Gemini.")

            if len(embedding.values) != EMBED_DIMENSIONS:
                raise ValueError(
                    f"Expected {EMBED_DIMENSIONS} dimensions, "
                    f"received {len(embedding.values)}."
                )

            out.append(embedding.values)

    if len(out) != len(texts):
        raise ValueError(
            "Number of generated embeddings does not match input texts."
        )

    return out