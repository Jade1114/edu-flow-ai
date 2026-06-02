"""排课 pipeline：创建 AllocationTask → 枚举模板集 → GA 进化 → 输出"""

from __future__ import annotations
import logging
import random, json
from collections import Counter
from typing import Any

logger = logging.getLogger("ga")

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
    day_period_to_slot, slot_to_day_period, weeks_to_mask, mask_count,
)


def generate_scheme(
    tasks_data: list[dict[str, Any]],
    classrooms: list[dict[str, Any]],
    time_slots: list[dict[str, Any]],
    teacher_profiles: dict | None = None,
    *,
    rng: random.Random,
    population_size: int,
    generations: int,
    elite_size: int,
    tournament_size: int,
    mutation_rate: float,
    init_candidate_top_n: int,
    scoring_config: dict[str, Any] | None = None,
    llm_overrides: list[dict] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """对一组教学任务执行 GA 进化，返回排课方案和评估指标。
    流程：
      1. 将 time_slots 转为 slot_id 坐标索引
      2. 对每个教学任务做硬过滤（教室容量/类型、教师硬不可用时间）
         构造 AllocationTask 内表示，枚举模板集
      3. 调 GA evolve() 进化指定代数，选最优个体
      4. 将 GA 结果展开为兼容 Java 解析的 rows 格式
    参数：
      tasks_data:   fetch_tasks() 返回的原始教学任务列表
      classrooms:   fetch_classrooms() 返回的教室列表
      time_slots:   已按 generation_config 的 allowed_weeks/weekdays/periods 过滤后的时间段
      teacher_profiles: normalize_profiles() 处理后的教师画像，影响硬不可用 slot 过滤
      rng:          随机数生成器，相同 task_id + scheme_index 确保可复现
      scoring_config: 由 build_scoring_config() 从 DB generation_config 构建的评分权重
      llm_overrides:  约束编辑器产生的 LLM 约束列表，影响 L5 评分层
      其余超参数对应 GA 的种群大小/代数/精英数/锦标赛大小/变异率/候选 Top-N
    返回：
      rows:    兼容 Java AllocationMlSchemeService 解析的 dict 列表
      metrics: 包含 quality_score, penalty_count, hard_conflicts 等指标
    异常：
      ValueError: 存在 infeasible 教学任务（无可用的教室或时间段或模板集）
      ValueError: GA 最终方案仍有 missing_task_count > 0 或 hard_conflicts > 0
    """

    # 1. 提取可用周/天/节
    available_weeks = sorted(set(int(s["week_number"]) for s in time_slots))
    # 采用 mask 位运算的方式比较周是否可用，降低复杂度
    available_week_mask = weeks_to_mask(available_weeks)

    # 把自然坐标跟 DB ID 绑定，这样输出的时候不用查库，降低复杂度
    time_slot_id_by_coord = {
        (int(s["week_number"]), int(s["day_of_week"]), int(s["period_index"])): int(s["id"])
        for s in time_slots
    }

    # 构建 (天，节) 内部整数编码，方便后续 GA 进行方案排布，为保证每周的稳定性，不携带周变动
    slot_set: set[tuple[int, int]] = set()
    for s in time_slots:
        slot_set.add((int(s["day_of_week"]), int(s["period_index"])))
    candidate_slot_ids = [day_period_to_slot(d, p) for d, p in sorted(slot_set)]

    # 标准化教师画像
    profile_by_teacher_id = normalize_profiles(teacher_profiles)

    # ── 2. 构建 AllocationTask ──────────────────────────
    alloc_tasks: list[AllocationTask] = []
    infeasible_reasons: dict[int, str] = {}  # tid → "no_lessons" / "no_room" / "no_slots" / "no_templates"
    profile_audit: dict[str, Any] = {
        "task_count": 0,
        "tasks_with_profile": 0,
        "tasks_with_hard_unavailable": 0,
        "hard_unavailable_slot_total": 0,
        "candidate_slot_total_before_hard_filter": 0,
        "candidate_slot_total_after_hard_filter": 0,
        "candidate_slot_removed_by_hard_filter": 0,
        "tasks": [],
    }
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
        profile_audit["task_count"] += 1
        if total_lessons <= 0:
            infeasible_reasons[tid] = "no_lessons"
            continue

        # 教室过滤
        required_type = str(td.get("required_room_type") or "")
        candidate_room_ids = [
            int(r["id"]) for r in classrooms
            if int(r.get("capacity") or 0) >= student_count
            and (not required_type or required_type.strip().lower() == str(r.get("classroom_type") or "").strip().lower())
        ]
        if not candidate_room_ids:
            infeasible_reasons[tid] = "no_room"
            continue

        hard_unavailable = hard_unavailable_slots(teacher_profile)
        task_candidate_slot_ids = [
            sid for sid in candidate_slot_ids
            if slot_to_day_period(sid) not in hard_unavailable
        ]
        before_count = len(candidate_slot_ids)
        after_count = len(task_candidate_slot_ids)
        removed_count = before_count - after_count
        if teacher_profile:
            profile_audit["tasks_with_profile"] += 1
        if hard_unavailable:
            profile_audit["tasks_with_hard_unavailable"] += 1
        profile_audit["hard_unavailable_slot_total"] += len(hard_unavailable)
        profile_audit["candidate_slot_total_before_hard_filter"] += before_count
        profile_audit["candidate_slot_total_after_hard_filter"] += after_count
        profile_audit["candidate_slot_removed_by_hard_filter"] += removed_count
        profile_audit["tasks"].append({
            "teaching_task_id": tid,
            "teacher_id": teacher_id,
            "teacher_name": td.get("teacher_name") or "",
            "has_profile": bool(teacher_profile),
            "hard_unavailable_slots": [
                {"weekday": day, "period": period}
                for day, period in sorted(hard_unavailable)
            ],
            "candidate_slots_before_hard_filter": before_count,
            "candidate_slots_after_hard_filter": after_count,
            "candidate_slots_removed_by_hard_filter": removed_count,
        })
        if not task_candidate_slot_ids:
            infeasible_reasons[tid] = "no_slots"
            continue

        # 枚举模板集
        template_sets = enumerate_template_sets(total_lessons, available_weeks)
        logger.info(
            "Task %s (teacher=%s, lessons=%s): template_sets=%s candidate_slots=%s candidate_rooms=%s",
            tid, td.get("teacher_name"), total_lessons,
            len(template_sets), len(task_candidate_slot_ids), len(candidate_room_ids),
        )
        if not template_sets:
            infeasible_reasons[tid] = "no_templates"
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

    if infeasible_reasons:
        summary = Counter(infeasible_reasons.values())
        details = ", ".join(f"{tid}({reason})" for tid, reason in infeasible_reasons.items())
        logger.error(
            "排课预处理失败: %s 个任务 infeasible — no_lessons=%s, no_room=%s, no_slots=%s, no_templates=%s | tasks=%s",
            len(infeasible_reasons),
            summary.get("no_lessons", 0),
            summary.get("no_room", 0),
            summary.get("no_slots", 0),
            summary.get("no_templates", 0),
            details,
        )
        raise ValueError(f"排课失败：教学任务缺少可行候选资源或模板集：{details}")

    if not alloc_tasks:
        raise ValueError("无可行教学任务")

    logger.info(
        "Profile audit: tasks=%s, with_profile=%s, hard_filtered=%s, "
        "slots_before=%s, slots_after=%s, slots_removed=%s",
        profile_audit["task_count"],
        profile_audit["tasks_with_profile"],
        profile_audit["tasks_with_hard_unavailable"],
        profile_audit["candidate_slot_total_before_hard_filter"],
        profile_audit["candidate_slot_total_after_hard_filter"],
        profile_audit["candidate_slot_removed_by_hard_filter"],
    )

    task_data_by_id = {int(td.get("teaching_task_id") or 0): td for td in tasks_data}
    classroom_by_id = {int(room.get("id") or 0): room for room in classrooms}
    scorer = AssignmentScorer(task_data_by_id=task_data_by_id, classroom_by_id=classroom_by_id)

    # ── 3. GA 进化（Deb 2000 可行性优先） ──────────────
    logger.info(
        "GA start: tasks=%s, pop=%s, gen=%s, elite=%s, mutation=%s",
        len(alloc_tasks), population_size, generations, elite_size, mutation_rate,
    )
    best_ind, metrics = evolve(
        alloc_tasks, rng,
        pop_size=population_size,
        generations=generations,
        elite_size=elite_size,
        tournament_size=tournament_size,
        mutation_rate=mutation_rate,
        init_candidate_top_n=init_candidate_top_n,
        scorer=scorer,
        config=scoring_config,
        llm_overrides=llm_overrides,
    )
    logger.info(
        "GA done: quality=%s, penalty=%s, missing=%s, hard_conflicts=%s",
        metrics.get("quality_score"), metrics.get("penalty_count"),
        metrics.get("missing_task_count"), metrics.get("hard_conflicts"),
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
    metrics["teacher_profile_audit"] = profile_audit
    metrics["ga_params"] = {
        "population_size": population_size,
        "generations": generations,
        "elite_size": elite_size,
        "tournament_size": tournament_size,
        "mutation_rate": mutation_rate,
        "init_candidate_top_n": init_candidate_top_n,
    }

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
