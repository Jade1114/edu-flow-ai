"""排课 pipeline：创建 AllocationTask → 枚举模板集 → GA 进化 → 输出"""

from __future__ import annotations
import random, json
from collections import Counter
from typing import Any

from ml.scheduling.assignment_scorer import AssignmentScorer
from ml.scheduling.enumerator import enumerate_template_sets
from ml.scheduling.ga import evolve
from ml.scheduling.teacher_profiles import (
    hard_unavailable_slots,
    normalize_profiles,
    profile_explanation,
    profile_penalty,
)
from ml.scheduling.types import (
    AllocationTask, TemplateSet,
    slot_to_day_period, weeks_to_mask, mask_count,
)


def generate_scheme(
    tasks_data: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    teacher_profiles: dict | None = None,
    *,
    rng: random.Random,
    population_size: int = 60,
    generations: int = 60,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """生成排课方案。

    输入：
      tasks_data: DB 拉取的教学任务
      classrooms: DB 拉取的教室
      time_slots: DB 拉取的时间段（已按 config 过滤）

    返回：
      rows: 兼容 Java 解析格式的 rows
      metrics: 方案质量指标
    """

    # ── 1. 提取可用周/天/节 ────────────────────────────
    available_weeks = sorted(set(int(s["week_number"]) for s in time_slots))
    available_week_mask = weeks_to_mask(available_weeks)
    time_slot_id_by_coord = {
        (int(s["week_number"]), int(s["day_of_week"]), int(s["period_index"])): int(s["id"])
        for s in time_slots
    }

    slot_set: set[tuple[int, int]] = set()
    for s in time_slots:
        slot_set.add((int(s["day_of_week"]), int(s["period_index"])))
    from ml.scheduling.types import day_period_to_slot
    candidate_slot_ids = [day_period_to_slot(d, p) for d, p in sorted(slot_set)]
    profile_by_teacher_id = normalize_profiles(teacher_profiles)

    # ── 2. 构建 AllocationTask ──────────────────────────
    alloc_tasks: list[AllocationTask] = []
    infeasible_task_ids: list[int] = []
    for td in tasks_data:
        tid = int(td.get("teaching_task_id") or 0)
        teacher_id = int(td.get("teacher_id") or 0)
        total_lessons = int(td.get("total_hours") or 0) // 2  # 48h→24次课
        student_count = int(td.get("total_student_count") or 0)
        class_group_ids = _parse_id_tuple(td.get("class_group_ids"))
        cg_id = class_group_ids[0] if class_group_ids else 1
        teacher_profile = profile_by_teacher_id.get(teacher_id)

        if tid <= 0:
            continue
        if total_lessons <= 0:
            infeasible_task_ids.append(tid)
            continue

        # 教室过滤
        required_type = str(td.get("required_room_type") or "")
        candidate_room_ids = [
            int(r["id"]) for r in classrooms
            if int(r.get("capacity") or 0) >= student_count
            and (not required_type or required_type.strip().lower() == str(r.get("classroom_type") or "").strip().lower())
        ]
        if not candidate_room_ids:
            infeasible_task_ids.append(tid)
            continue

        hard_unavailable = hard_unavailable_slots(teacher_profile)
        task_candidate_slot_ids = [
            sid for sid in candidate_slot_ids
            if slot_to_day_period(sid) not in hard_unavailable
        ]
        if not task_candidate_slot_ids:
            infeasible_task_ids.append(tid)
            continue

        # 枚举模板集
        template_sets = enumerate_template_sets(total_lessons, available_weeks)
        if not template_sets:
            infeasible_task_ids.append(tid)
            continue

        alloc_tasks.append(AllocationTask(
            task_id=tid, teacher_id=teacher_id, class_group_id=cg_id,
            student_count=student_count, total_lessons=total_lessons,
            available_week_mask=available_week_mask,
            candidate_slot_ids=task_candidate_slot_ids,
            candidate_room_ids=candidate_room_ids,
            template_sets=template_sets,
            class_group_ids=class_group_ids,
            teacher_profile=teacher_profile,
        ))

    if infeasible_task_ids:
        ids = ", ".join(str(tid) for tid in infeasible_task_ids)
        raise ValueError(f"排课失败：教学任务缺少可行候选资源或模板集：{ids}")

    if not alloc_tasks:
        raise ValueError("无可行教学任务")

    task_data_by_id = {int(td.get("teaching_task_id") or 0): td for td in tasks_data}
    classroom_by_id = {int(room.get("id") or 0): room for room in classrooms}
    scorer = AssignmentScorer(task_data_by_id=task_data_by_id, classroom_by_id=classroom_by_id)

    # ── 3. GA 进化 ──────────────────────────────────────
    best_ind, metrics = evolve(
        alloc_tasks, rng,
        pop_size=population_size, generations=generations,
        scorer=scorer,
    )
    if int(metrics.get("missing_task_count") or 0) > 0:
        raise ValueError(f"排课失败：有 {metrics['missing_task_count']} 个教学任务未被排入方案")
    if int(metrics.get("hard_conflicts") or 0) > 0:
        raise ValueError(f"排课失败：最终方案仍有 {metrics['hard_conflicts']} 个硬冲突")

    # ── 4. 展开为输出行 ─────────────────────────────────
    rows = _to_rows(best_ind, alloc_tasks, tasks_data, time_slot_id_by_coord, scorer)
    week_dist = Counter(int(r.get("week_number", 0)) for r in rows)
    metrics["weeks_covered"] = len(week_dist)
    metrics["task_count"] = len(alloc_tasks)
    metrics["lightgbm"] = scorer.model_status

    return rows, metrics


def _to_rows(
    chromosome,
    alloc_tasks,
    tasks_data,
    time_slot_id_by_coord: dict[tuple[int, int, int], int],
    scorer: AssignmentScorer | None = None,
) -> list[dict[str, Any]]:
    task_map = {t.task_id: t for t in alloc_tasks}
    task_data_map = {int(td.get("teaching_task_id") or 0): td for td in tasks_data}
    rows = []
    seq = 0

    for gene in chromosome:
        task = task_map.get(gene.task_id)
        td = task_data_map.get(gene.task_id, {})
        if not task:
            continue

        tss = task.template_sets
        ts = tss[gene.template_set_id] if gene.template_set_id < len(tss) else None
        if not ts:
            continue

        for ai, a in enumerate(gene.assignments):
            tmpl = ts.templates[a.template_id] if a.template_id < len(ts.templates) else None
            if not tmpl:
                continue
            day, period = slot_to_day_period(a.slot_id)
            predicted_score = scorer.score(task, tmpl, a.slot_id, a.classroom_id) if scorer else 0.0
            teacher_profile_penalty, teacher_profile_breakdown = profile_penalty(task.teacher_profile, a.slot_id)

            for wn in tmpl.weeks_list:
                time_slot_id = time_slot_id_by_coord.get((wn, day, period))
                if time_slot_id is None:
                    raise ValueError(f"排课失败：生成了不可用时间片 week={wn}, day={day}, period={period}")
                seq += 1
                rows.append({
                    "sequence": seq,
                    "teaching_task_id": gene.task_id,
                    "teacher_id": task.teacher_id,
                    "teacher_name": td.get("teacher_name") or "",
                    "fragment_index": ai,
                    "classroom_id": a.classroom_id,
                    "time_slot_id": time_slot_id,
                    "week_number": wn,
                    "day_of_week": day,
                    "period_index": period,
                    "predicted_score": predicted_score,
                    "rule_score": 0.0,
                    "has_hard_conflict": 0,
                    "reject_reason": "",
                    "teacher_profile_penalty": teacher_profile_penalty,
                    "teacher_profile_penalty_explanation": profile_explanation(teacher_profile_breakdown),
                    "teacher_profile_penalty_breakdown": json.dumps(teacher_profile_breakdown, ensure_ascii=False),
                })

    return rows


def _parse_id_tuple(value: Any) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        raw_parts = value
    else:
        raw_parts = str(value).strip().strip("[]").replace(" ", "").split(",")

    ids: list[int] = []
    for part in raw_parts:
        if part in ("", None):
            continue
        try:
            parsed = int(part)
        except (TypeError, ValueError):
            continue
        if parsed and parsed not in ids:
            ids.append(parsed)
    return tuple(ids)
