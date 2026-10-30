import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

AUDIT_LOG_FILE = LOG_DIR / "audit.log"

audit_logger = logging.getLogger("document_management.audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False

if not audit_logger.handlers:
    handler = RotatingFileHandler(
        AUDIT_LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)


def log_audit(
    action: str,
    user_id: int | None = None,
    target_id: int | None = None,
    details: dict | None = None,
):
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user_id": user_id,
        "target_id": target_id,
        "details": details or {},
    }

    audit_logger.info(json.dumps(event, default=str))