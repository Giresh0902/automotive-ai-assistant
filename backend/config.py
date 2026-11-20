import os
from dotenv import load_dotenv
load_dotenv()
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5-5")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
BUCKET = "brochures"
