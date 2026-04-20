"""
pg_dump wrapper — call dump() after any ingestion run to snapshot the DB.
Keeps the 5 most recent dumps in src/backups/.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BACKUPS_DIR = Path(__file__).parent.parent / "backups"
KEEP = 5


def dump(label: str = ""):
    BACKUPS_DIR.mkdir(exist_ok=True)

    db_name = os.getenv("DB_NAME", "markets_project")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", os.getenv("USER", ""))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    path = BACKUPS_DIR / f"{timestamp}{suffix}.dump"

    cmd = [
        "/opt/homebrew/opt/postgresql@17/bin/pg_dump",
        "-Fc",          # custom format — smaller, faster restore
        "-h", db_host,
        "-p", db_port,
        "-U", db_user,
        "-f", str(path),
        db_name,
    ]

    print(f"Backing up to {path.name} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  pg_dump failed: {result.stderr.strip()}")
        return

    print(f"  Done ({path.stat().st_size // 1024} KB)")
    _prune()


def _prune():
    dumps = sorted(BACKUPS_DIR.glob("*.dump"))
    for old in dumps[:-KEEP]:
        old.unlink()
        print(f"  Removed old backup: {old.name}")


def restore(path: str):
    """pg_restore from a .dump file — prints the command, requires manual confirmation."""
    db_name = os.getenv("DB_NAME", "markets_project")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", os.getenv("USER", ""))

    print("Run this to restore:")
    print(
        f"  pg_restore -Fc -h {db_host} -p {db_port} -U {db_user} -d {db_name} --clean {path}"
    )
