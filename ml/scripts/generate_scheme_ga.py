"""GA 排课入口 — 读取 DB → 生成方案 → 写 schemes.json"""

from __future__ import annotations
import json, logging, os, random, sys
from pathlib import Path
from datetime import datetime as dt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.db.config import connect, load_db_config
from ml.db.repositories import (
    fetch_tasks, fetch_classrooms, fetch_time_slots,
    fetch_teacher_profiles, fetch_allocation_task,
    fetch_generation_config, fetch_task_teaching_task_ids,
)
from ml.ga_config import resolve_ga_params
from ml.scheduling.pipeline import generate_scheme
from ml.scheduling.infra.constants import PROJECT_LOG_DIR
from ml.scheduling.teacher_profiles import load_teacher_profiles_jsonl

LOG_FILE = PROJECT_LOG_DIR / "ga-algorithm.log"


def _setup_logger():
    logger = logging.getLogger("ga")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8", mode="a")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    # Also log to console
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("[GA] %(message)s"))
    logger.addHandler(console)
    return logger


logger = _setup_logger()


def run(task_id: int, teacher_profiles_jsonl: str | None = None):
    db = load_db_config()
    with connect(db) as conn:
        at = fetch_allocation_task(conn, task_id)
        if not at:
            raise ValueError(f"task {task_id} not found")
        teaching_task_ids = fetch_task_teaching_task_ids(conn, task_id)
        raw_config = fetch_generation_config(conn, task_id)
        tasks = fetch_tasks(conn)
        classrooms = fetch_classrooms(conn)
        time_slots = fetch_time_slots(conn)
        teacher_profiles = fetch_teacher_profiles(conn)

    # 按 config 过滤时间片
    if raw_config:
        aw = raw_config.get("allowed_weeks", "")
        aw_set = parse_int_set(str(aw)) if aw else None
        ad = parse_int_set(str(raw_config.get("allowed_weekdays", "")))
        ap = parse_int_set(str(raw_config.get("allowed_periods", "")))
        if aw_set:
            time_slots = [s for s in time_slots if int(s["week_number"]) in aw_set]
        if ad:
            time_slots = [s for s in time_slots if int(s["day_of_week"]) in ad]
        if ap:
            time_slots = [s for s in time_slots if int(s["period_index"]) in ap]

    # 筛选跟 task 绑定的教学任务
    tid_set = set(teaching_task_ids)
    tasks = [t for t in tasks if int(t.get("teaching_task_id") or 0) in tid_set]

    scheme_count = _resolve_scheme_count(raw_config)
    ga_params = resolve_ga_params(logger)
    profile_jsonl_path = teacher_profiles_jsonl or os.environ.get("TEACHER_PROFILES_JSONL")
    if profile_jsonl_path:
        teacher_profiles = load_teacher_profiles_jsonl(profile_jsonl_path)

    schemes = []
    summaries = []
    logger.info(
        "GA effective params for allocation_task_id=%s: profile=%s pop=%s generations=%s elite=%s tournament=%s mutation=%s",
        task_id,
        ga_params.get("profile"),
        ga_params["population_size"],
        ga_params["generations"],
        ga_params["elite_size"],
        ga_params["tournament_size"],
        ga_params["mutation_rate"],
    )
    for index in range(scheme_count):
        logger.info("Generating GA scheme %s/%s for allocation_task_id=%s", index + 1, scheme_count, task_id)
        rng = random.Random((task_id * 1_000_003 + index * 9_176 + 17) % 2_147_483_647)
        rows, metrics = generate_scheme(
            tasks, classrooms, time_slots, teacher_profiles,
            rng=rng,
            population_size=int(ga_params["population_size"]),
            generations=int(ga_params["generations"]),
            elite_size=int(ga_params["elite_size"]),
            tournament_size=int(ga_params["tournament_size"]),
            mutation_rate=float(ga_params["mutation_rate"]),
            init_candidate_top_n=int(ga_params["candidate_top_n"]),
        )
        schemes.append({"items": rows})
        summaries.append({"scheme_index": index + 1, "ga_profile": ga_params.get("profile"), **metrics})

    # 写输出
    ts = dt.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    out = Path(__file__).resolve().parents[1] / "data" / "generated" / f"task_{task_id}_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "schemes.json").write_text(json.dumps(schemes, ensure_ascii=False, default=str))
    (out / "ga_summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2))
    return {"output_dir": str(out), "scheme_count": len(schemes), "timings_ms": {}}


def _resolve_scheme_count(raw_config: dict | None) -> int:
    if not raw_config:
        return 1
    try:
        value = int(raw_config.get("scheme_count") or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, min(value, 5))


def parse_int_set(v: str) -> set[int] | None:
    if not v or not v.strip():
        return None
    v = v.strip().strip("[]").replace(" ", "")
    result = set()
    for part in v.split(","):
        part = part.strip()
        if part:
            try:
                result.add(int(part))
            except ValueError:
                pass
    return result or None
