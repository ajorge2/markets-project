import json
from pathlib import Path


def read_jsonl(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # truncated last line from a crash
    return rows


def append_jsonl(path: str | Path, row: dict):
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")


def count_valid_lines(path: str | Path) -> int:
    return len(read_jsonl(path))
