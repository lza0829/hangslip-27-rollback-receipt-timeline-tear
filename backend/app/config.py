import os
from pathlib import Path

PROJECT_NAME = "衣票墙"
ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("HANGSLIP_DB", ROOT / "data" / "hangslip.db"))
API_PORT = 11200
