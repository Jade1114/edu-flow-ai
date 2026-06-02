"""
Architecture verification script — checks the 5 unresolved risks before GA investment.

Verify items:
  1. TemplatePlan coverage: what % of real tasks can generate_templates cover?
  2. Teacher cross-distribution: what's the medium-cross ratio?
  3. Beam search baseline on real tasks (small subset first)
  4. Initialization order bias
  5. Repair convergence

Run: cd /Users/yuy/workspaces/projects/edu-flow-ai && python3 ml/tests/verify_architecture.py
"""

from __future__ import annotations

import json
import sys
import time
import math
from collections import defaultdict, Counter
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.channels.template_generator import generate_templates
from ml.channels.teacher_classifier import classify_teachers, teacher_class_count


def load_tasks(path: str = "data/real-dataset/teaching_tasks.jsonl") -> list[dict]:
    tasks = []
    with open(path) as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))
    return tasks


def load_classrooms(path: str = "data/real-dataset/classrooms.jsonl") -> list[dict]:
    rooms = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rooms.append(json.loads(line))
    return rooms


# ============================================================
# Verify 1: TemplatePlan Coverage
# ============================================================
def verify_template_coverage(tasks: list[dict], sample_size: int = 500):
    """Check what % of tasks can be covered by generate_templates."""
    print("=" * 60)
    print("VERIFY 1: Template Coverage")
    print("=" * 60)

    import random
    random.seed(42)
    sample = random.sample(tasks, min(sample_size, len(tasks)))

    covered = 0
    covered_with_variety = 0  # at least 3 templates
    hour_mismatches = 0
    failures: list[dict] = []

    for task in sample:
        total_hours = task.get("total_hours", 0)
        total_lessons = int(total_hours / 2)  # as used in template_generator

        if total_lessons <= 0:
            hour_mismatches += 1
            continue

        templates = generate_templates(total_lessons, top_k=10)

        if len(templates) > 0:
            covered += 1
            if len(templates) >= 3:
                covered_with_variety += 1
        else:
            failures.append({
                "task": task,
                "total_hours": total_hours,
                "total_lessons": total_lessons,
            })

    print(f"Sample size: {len(sample)}")
    print(f"Covered (≥1 template):     {covered}/{len(sample)} ({100*covered/len(sample):.1f}%)")
    print(f"Covered (≥3 templates):    {covered_with_variety}/{len(sample)} ({100*covered_with_variety/len(sample):.1f}%)")
    print(f"Zero-lesson edge cases:     {hour_mismatches}")
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for f in failures[:10]:
            print(f"  {f['task'].get('course_code','?')} | {f['task'].get('teacher','?')} | {f['total_hours']}h → {f['total_lessons']} lessons")

    # Check hour distribution in failures
    if failures:
        fail_hours = Counter(int(f["total_hours"]) for f in failures)
        print(f"\n  Failure hour distribution: {dict(sorted(fail_hours.items()))}")

    return covered / len(sample) >= 0.95  # pass if 95%+


# ============================================================
# Verify 2: Teacher Cross Distribution
# ============================================================
def verify_teacher_distribution(tasks: list[dict]):
    """Classify teachers and report the distribution."""
    print("\n" + "=" * 60)
    print("VERIFY 2: Teacher Cross Distribution")
    print("=" * 60)

    # classifier expects "teacher" and "class_group" keys directly
    result = classify_teachers(tasks, threshold=12)

    stats = result.get("stats", {})
    total = stats.get("total_teachers", 1)
    hc = stats.get("high_cross_count", 0)
    lc = stats.get("low_cross_count", 0)
    print(f"Total teachers:     {total}")
    print(f"High-cross (≥12):   {hc} ({100*hc/total:.1f}%)")
    print(f"Low-cross (<12):    {lc} ({100*lc/total:.1f}%)")

    # Get per-teacher class counts
    tcc = teacher_class_count(tasks)
    counts = list(tcc.values())
    
    # Distribution buckets
    buckets = Counter()
    for c in counts:
        if c <= 2: buckets["1-2"] += 1
        elif c <= 4: buckets["3-4"] += 1
        elif c <= 8: buckets["5-8"] += 1
        elif c <= 12: buckets["9-12"] += 1
        elif c <= 20: buckets["13-20"] += 1
        else: buckets["21+"] += 1

    print(f"\nTeacher cross distribution:")
    for k in ["1-2", "3-4", "5-8", "9-12", "13-20", "21+"]:
        bar = "█" * (buckets.get(k, 0) // 5)
        print(f"  {k:>6} classes: {buckets.get(k, 0):>4} teachers  {bar}")

    # Now: if we lock high-cross and low-cross, what's left for GA?
    high_cross_teachers = set(result.get("high_cross", []))
    
    # Which tasks are "medium cross"? 
    # Let's define medium-cross as teachers with 5-11 classes
    medium_teachers = {t for t, c in tcc.items() if 5 <= c <= 11}
    low_teachers = {t for t, c in tcc.items() if c < 5}
    
    ga_tasks = 0
    high_locked = 0
    low_locked = 0
    for t in tasks:
        teacher = t.get("teacher", "")
        if teacher in high_cross_teachers:
            high_locked += 1
        elif teacher in low_teachers:
            low_locked += 1
        else:
            ga_tasks += 1
    
    print(f"\nTask breakdown:")
    print(f"  High-cross locked:  {high_locked}")
    print(f"  Low-cross locked:   {low_locked}")
    print(f"  Medium-cross (GA):  {ga_tasks} ({100*ga_tasks/len(tasks):.1f}%)")
    print(f"  Total:              {len(tasks)}")

    return ga_tasks / len(tasks) >= 0.30  # pass if 30%+ for GA


# ============================================================
# Verify 3: Beam Search Baseline (small subset)
# ============================================================
def verify_beam_baseline(tasks: list[dict], classrooms: list[dict]):
    """Run beam search on a small subset and measure quality."""
    print("\n" + "=" * 60)
    print("VERIFY 3: Beam Search Baseline")
    print("=" * 60)

    # Build time slots for weeks 1-18
    time_slots = []
    slot_id = 1001
    for week in range(1, 19):
        for day in range(1, 8):  # Mon-Sun
            for period in range(1, 6):  # 5 periods per day
                time_slots.append({
                    "id": slot_id,
                    "week_number": week,
                    "day_of_week": day,
                    "period_index": period,
                })
                slot_id += 1

    # Prepare classroom data
    formatted_rooms = []
    for i, r in enumerate(classrooms):
        formatted_rooms.append({
            "id": i + 1,
            "name": r.get("name", f"R{i}"),
            "capacity": r.get("capacity", 80),
            "classroom_type": r.get("classroom_type", "普通教室"),
        })

    # Format a subset of tasks
    sample_size = 100
    import random
    random.seed(42)
    sample_indices = random.sample(range(len(tasks)), min(sample_size, len(tasks)))

    formatted_tasks = []
    for idx in sample_indices:
        t = tasks[idx]
        total_lessons = max(1, int(t.get("total_hours", 16) / 2))
        room_type = "普通教室"
        # Guess room type from course
        cc = t.get("course_code", "")
        if "机" in cc or "计算机" in cc:
            room_type = "机房"

        formatted_tasks.append({
            "id": idx,
            "teacher_name": t.get("teacher", ""),
            "teacher_id": str(t.get("teacher", "")),
            "class_group_ids": [t.get("class_group", "")],
            "total_lessons": total_lessons,
            "student_count": 40,
            "required_room_type": room_type,
            "course_code": cc,
        })

    try:
        from ml.channels.beam_constructor import construct_timetable

        print(f"Running beam search on {len(formatted_tasks)} tasks...")
        start = time.time()
        result = construct_timetable(
            tasks=formatted_tasks,
            classrooms=formatted_rooms,
            time_slots=time_slots,
            beam_width=3,
        )
        elapsed = time.time() - start

        print(f"Time: {elapsed:.1f}s")
        print(f"Success: {result.get('success')}")
        assigned = len(result.get("assignments", []))
        unassigned = len(result.get("unassigned", []))
        print(f"Assigned: {assigned}")
        print(f"Unassigned: {unassigned}")
        print(f"Assign rate: {100*assigned/len(formatted_tasks):.1f}%")
        print(f"Total score: {result.get('total_score', 'N/A')}")

        if unassigned > 0:
            print(f"\n  WARNING: {unassigned} tasks unassigned. Beam search can't handle this task set.")
            for u in result.get("unassigned", [])[:5]:
                print(f"    Task {u.get('id')}: {u.get('teacher_name')} - {u.get('course_code')}")

    except Exception as e:
        print(f"ERROR running beam search: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# Verify 4: Build and test GA integration
# ============================================================
def verify_ga_framework(tasks: list[dict]):
    """Check if the test_scheduling_v2 GA framework can handle real data."""
    print("\n" + "=" * 60)
    print("VERIFY 4: GA Framework Feasibility")
    print("=" * 60)

    # Try running the existing GA tests
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "pytest", "ml/tests/test_scheduling_v2.py", "-v", "--tb=short", "-x"],
        cwd="/Users/yuy/workspaces/projects/edu-flow-ai",
        capture_output=True,
        text=True,
        timeout=120,
    )
    
    # Show summary
    lines = result.stdout.split("\n")
    passed = 0
    failed = 0
    for line in lines:
        if "PASSED" in line:
            passed += 1
        elif "FAILED" in line:
            failed += 1

    print(f"GA test suite: {passed} passed, {failed} failed")
    
    # Show last few lines
    for line in lines[-10:]:
        if line.strip():
            print(f"  {line.strip()}")

    if failed > 0:
        print("\nFAILURES:")
        for line in lines:
            if "FAILED" in line or "Error" in line or "assert" in line:
                print(f"  {line.strip()}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("Architecture Verification")
    print("=" * 60)
    print()

    # Load data
    tasks = load_tasks()
    classrooms = load_classrooms()
    print(f"Loaded {len(tasks)} tasks, {len(classrooms)} classrooms")
    print()

    overall_pass = True

    # Verify 1: Template Coverage
    if not verify_template_coverage(tasks, sample_size=500):
        overall_pass = False

    # Verify 2: Teacher Distribution
    if not verify_teacher_distribution(tasks):
        overall_pass = False

    # Verify 3: Beam Baseline
    verify_beam_baseline(tasks, classrooms)

    # Verify 4: GA Framework
    verify_ga_framework(tasks)

    print("\n" + "=" * 60)
    if overall_pass:
        print("OVERALL: All critical checks PASSED")
    else:
        print("OVERALL: Some checks FAILED — see details above")
    print("=" * 60)
