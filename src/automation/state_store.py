from __future__ import annotations

import json
from pathlib import Path


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"campaigns": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"campaigns": {}}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def compute_fingerprint(paths: list[Path], root: Path) -> str:
    chunks: list[str] = []
    for p in sorted(paths, key=lambda x: str(x).lower()):
        stat = p.stat()
        rel = str(p.relative_to(root)).replace("\\", "/")
        chunks.append(f"{rel}|{int(stat.st_mtime)}|{stat.st_size}")
    return "\n".join(chunks)
