import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "novel_studio.db")))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "data" / "exports")))
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai_compatible").strip().lower()
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "openai/gpt-oss-120b")
AI_API_KEY = os.getenv("AI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_CHAPTERS_PER_REQUEST = max(1, int(os.getenv("MAX_CHAPTERS_PER_REQUEST", "1")))
