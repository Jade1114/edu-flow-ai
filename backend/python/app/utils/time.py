"""Time-related utilities."""
from datetime import datetime


def now_str() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"
