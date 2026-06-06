"""Natural language constraint parser for LLM constraint editor.

Parses教务自然语言描述 into structured llm_overrides format.

Patterns supported:
  - "周三下午尽量不排课"          → slot_penalty, normal
  - "张老师的课完全禁止周三下午"    → slot_penalty, critical, teacher scoped
  - "大班课优先用多媒体教室"       → classroom_preference, strong
  - "英语课和数学课不要排在同一天" → task_relation, normal
  - "上午尽量排数学课"            → slot_penalty, normal, course scoped
"""

from __future__ import annotations
import re
import uuid
from datetime import date, timedelta
from typing import Any

# ── Weekday mapping ───────────────────────────────────────

WEEKDAY_MAP: dict[str, int] = {
    "周一": 1, "周二": 2, "周三": 3, "周四": 4, "周五": 5,
    "星期六": 6, "星期日": 7, "周六": 6, "周日": 7,
}

PERIOD_MAP: dict[str, tuple[int, ...]] = {
    "上午": (1, 2),
    "下午": (3, 4),
    "晚上": (5,),
    "早八": (1,),
    "第一节": (1,), "第二节": (2,), "第三节": (3,),
    "第四节": (4,), "第五节": (5,),
    "全天": (1, 2, 3, 4, 5),
}

SEVERITY_KEYWORDS: dict[str, str] = {
    "完全禁止": "critical",
    "绝对不能": "critical",
    "禁止": "critical",
    "千万不要": "critical",
    "绝对不要": "critical",
    "千万不要": "critical",
    "尽量": "normal",
    "尽量不": "normal",
    "最好": "normal",
    "优先": "strong",
    "优先安排": "strong",
    "可以的话": "mild",
    "倾向": "mild",
    "稍微": "mild",
}

TYPE_KEYWORDS: dict[str, str] = {
    "教室": "classroom_preference",
    "多媒体": "classroom_preference",
    "实验室": "classroom_preference",
    "机房": "classroom_preference",
    "排课": "slot_penalty",
    "排": "slot_penalty",
    "安排": "slot_penalty",
    "一起": "task_relation",
    "同一天": "task_relation",
    "分开": "task_relation",
    "错开": "task_relation",
}


def parse_constraint_text(text: str) -> list[dict[str, Any]]:
    """Parse natural language constraint text into structured overrides.

    Returns list of override dicts matching llm_overrides schema:
    {
        "id": "ovr_xxx",
        "type": "slot_penalty|classroom_preference|task_relation",
        "scope": {"type": "all|teacher|course|student_count", ...},
        "params": {"slot_ids": [...], "priority": "critical|strong|normal|mild"},
        "source": "original text fragment",
        "expires_at": "YYYY-MM-DD",
        "active": true
    }
    """
    constraints: list[dict[str, Any]] = []

    # Split by common delimiters (逗号, 句号, 分号)
    segments = re.split(r"[，。；、]", text)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        constraint = _parse_single_constraint(segment)
        if constraint:
            constraints.append(constraint)

    return constraints


def _parse_single_constraint(text: str) -> dict[str, Any] | None:
    """Parse a single constraint segment."""
    constraint: dict[str, Any] = {
        "id": f"ovr_{uuid.uuid4().hex[:8]}",
        "source": text,
        "params": {},
        "active": True,
    }
    expires = date.today() + timedelta(days=180)  # 6 months default

    # 1. Detect constraint type
    constraint["type"] = _detect_type(text)

    # 2. Detect severity
    severity = _detect_severity(text)
    constraint["params"]["priority"] = severity

    # 3. Build scope
    scope = _build_scope(text)
    if scope:
        constraint["scope"] = scope
    else:
        constraint["scope"] = {"type": "all"}

    # 4. Extract slot_ids for time-related constraints
    if constraint["type"] == "slot_penalty":
        slot_ids = _extract_slot_ids(text)
        if slot_ids:
            constraint["params"]["slot_ids"] = slot_ids

    # 5. Extract room info for classroom_preference
    if constraint["type"] == "classroom_preference":
        room_type = _extract_room_type(text)
        if room_type:
            constraint["params"]["room_type"] = room_type
            constraint["params"]["mode"] = "avoid" if severity in ("critical", "strong") else "prefer"

    # 6. Extract task relation info
    if constraint["type"] == "task_relation":
        courses = _extract_course_names(text)
        if courses:
            constraint["params"]["course_types"] = courses
            constraint["params"]["relation_type"] = "separate_day"

    constraint["expires_at"] = expires.isoformat()
    return constraint


def _detect_type(text: str) -> str:
    """Detect constraint type from keywords."""
    for keyword, ctype in TYPE_KEYWORDS.items():
        if keyword in text:
            return ctype
    # Default: slot_penalty for scheduling constraints
    if any(w in text for w in ["排", "课", "节", "上午", "下午", "周"]):
        return "slot_penalty"
    return "slot_penalty"


def _detect_severity(text: str) -> str:
    """Detect severity level from keywords."""
    for keyword, severity in SEVERITY_KEYWORDS.items():
        if keyword in text:
            return severity
    # Default: normal for neutral descriptions
    return "normal"


def _build_scope(text: str) -> dict | None:
    """Build constraint scope from entities detected in text."""
    # Teacher detection
    for prefix in ["老师", "教师", "教授"]:
        match = re.search(rf"([\u4e00-\u9fa5]{{1,3}}){prefix}", text)
        if match:
            return {"type": "teacher", "teacher_name": match.group(1)}

    # Course detection
    course_types = _extract_course_names(text)
    if course_types:
        return {"type": "course", "course_types": course_types}

    # Student count detection
    match = re.search(r"大班|小班|(\d+)人", text)
    if match:
        if "大班" in text:
            return {"type": "student_count", "min": 40}
        elif "小班" in text:
            return {"type": "student_count", "max": 30}
        elif match.group(1):
            return {"type": "student_count", "min": int(match.group(1))}

    return None


def _extract_slot_ids(text: str) -> list[int] | None:
    """Extract time slot IDs from text.
    
    Converts natural language like "周三下午" to slot IDs.
    Slot ID = (day_of_week - 1) × 5 + (period_index - 1), 0-24.
    """
    days: set[int] = set()
    periods: set[int] = set()

    for day_name, day_num in WEEKDAY_MAP.items():
        if day_name in text:
            days.add(day_num)

    for period_name, period_nums in PERIOD_MAP.items():
        if period_name in text:
            periods.update(period_nums)

    # Fallback: if no specific day/period, return None (apply to all)
    if not days and not periods:
        return None

    # If day specified but no period → all periods
    if days and not periods:
        periods = {1, 2, 3, 4, 5}
    # If period specified but no day → all weekdays
    if periods and not days:
        days = {1, 2, 3, 4, 5}

    slot_ids = [(d - 1) * 5 + (p - 1) for d in days for p in periods]
    return sorted(slot_ids)


def _extract_room_type(text: str) -> str | None:
    """Extract room type from text."""
    if "多媒体" in text:
        return "多媒体"
    if "实验室" in text:
        return "实验室"
    if "机房" in text:
        return "机房"
    if "普通" in text:
        return "普通"
    return None


def _extract_course_names(text: str) -> list[str]:
    """Extract course names from text (simplified)."""
    courses: list[str] = []
    # Match common course names
    known_courses = ["数学", "英语", "语文", "体育", "音乐", "美术",
                     "物理", "化学", "生物", "历史", "地理", "政治"]
    for course in known_courses:
        if course in text:
            courses.append(course)
    return courses
