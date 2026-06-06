"""Teacher cross-class classifier for dual-channel scheduling.

Split teachers into high-cross (public/core courses, need pre-scheduling)
vs low-cross (department-specific, suitable for per-class GA).

Based on real data analysis (2026-05-31):
    - Low-cross (<=12 classes): ~96% of teachers
    - High-cross (>=12 classes): ~4% of teachers
"""

from __future__ import annotations

from collections import defaultdict


def classify_teachers(teaching_tasks, threshold=12):
    """Classify teachers into high-cross vs low-cross.

    Args:
        teaching_tasks: List of dicts with 'teacher' and 'class_group' keys.
        threshold: Number of unique class groups to qualify as high-cross.

    Returns:
        {
            "high_cross": ["张彤", ...],   # sorted by class count descending
            "low_cross":  ["王老师", ...],  # sorted by class count descending
            "stats": {
                "total_teachers": N,
                "high_cross_count": N,
                "low_cross_count": N,
                "high_cross_max_classes": N,
                "low_cross_max_classes": N,
                "threshold": N,
            },
        }
    """
    teacher_classes = defaultdict(set)
    for tt in teaching_tasks:
        cg = tt.get("class_group", "?")
        if cg:
            teacher_classes[tt["teacher"]].add(cg)

    high = []
    low = []

    for teacher, classes in teacher_classes.items():
        if len(classes) >= threshold:
            high.append(teacher)
        else:
            low.append(teacher)

    high.sort(key=lambda t: -len(teacher_classes[t]))
    low.sort(key=lambda t: -len(teacher_classes[t]))

    return {
        "high_cross": high,
        "low_cross": low,
        "stats": {
            "total_teachers": len(teacher_classes),
            "high_cross_count": len(high),
            "low_cross_count": len(low),
            "high_cross_max_classes": len(teacher_classes[high[0]]) if high else 0,
            "low_cross_max_classes": len(teacher_classes[low[0]]) if low else 0,
            "threshold": threshold,
        },
    }


def teacher_class_count(teaching_tasks):
    """Return number of unique class groups per teacher."""
    tc = defaultdict(set)
    for tt in teaching_tasks:
        tc[tt["teacher"]].add(tt.get("class_group", "?"))
    return {t: len(classes) for t, classes in tc.items()}


def teacher_class_groups(teaching_tasks):
    """Return class groups taught by each teacher."""
    tc = defaultdict(set)
    for tt in teaching_tasks:
        tc[tt["teacher"]].add(tt.get("class_group", "?"))
    return {t: sorted(classes) for t, classes in tc.items()}


def teacher_courses(teaching_tasks):
    """Return courses taught by each teacher."""
    tc = defaultdict(set)
    for tt in teaching_tasks:
        tc[tt["teacher"]].add(tt.get("course_code", ""))
    return {t: sorted(courses) for t, courses in tc.items()}


# ── Quick validation ─────────────────────────────────
if __name__ == "__main__":
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parents[2] / "data" / "real-dataset" / "teaching_tasks.jsonl"
    tasks = []
    with open(p) as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))

    for th in (4, 8, 12, 16):
        result = classify_teachers(tasks, threshold=th)
        s = result["stats"]
        pct_h = s["high_cross_count"] * 100 // s["total_teachers"]
        print(f"Threshold={th}: High={s['high_cross_count']}/{s['total_teachers']} ({pct_h}%)", end="")
        if result["high_cross"]:
            print(f"  top: {', '.join(result['high_cross'][:3])}")
        else:
            print()

    print("\n✓ Module loaded successfully.")
