"""ML API entry point — also works when run from the ml/ directory."""

import sys
from pathlib import Path

# 保证无论在项目根目录还是 ml/ 目录下都能找到包
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from python.api.main import app

__all__ = ["app"]
