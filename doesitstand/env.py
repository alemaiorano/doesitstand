import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_root = Path(__file__).parent.parent
load_dotenv(_root / ".env")

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set in environment or .env")

ARXIV_BASE_URL: str = os.environ.get(
    "ARXIV_BASE_URL", "http://export.arxiv.org/api/query"
)
ARXIV_USER_AGENT: str = os.environ.get("ARXIV_USER_AGENT", "paperreview/0.1.0")

GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
GEMINI_MODEL_FLASH: str = os.environ.get("GEMINI_MODEL_FLASH", "gemini-2.5-flash")
GEMINI_TEMPERATURE: float = float(os.environ.get("GEMINI_TEMPERATURE", "0.2"))
