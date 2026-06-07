"""General helper utilities."""
import json
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, default=str)
