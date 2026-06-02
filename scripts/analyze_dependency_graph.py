"""Analyze dependency graph connectivity for V3 community-detection feasibility.

Builds a bipartite dependency graph from clean timetable data:
- Nodes: teaching tasks (identified by course_code + class_group)
- Edges: two tasks share a teacher OR a class_group
- Finds connected components and reports decomposability.

Also tests a critical scenario: after pre-scheduling public courses (Pass 1),
do the remaining professional courses (Pass 2) naturally decompose?
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "real-dataset"

# ── helpers ──────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── graph construction ───────────────────────────────────────────────

def build_task_dependency_graph(
    teaching_tasks: list[dict],
    public_course_codes: set[str] | None = None,
) -> tuple[dict[str, set[str]], dict[str, dict], int]:
    """Build an undirected graph where nodes are task keys and edges
    represent shared teachers or shared class_groups.

    If `public_course_codes` is provided, only non-public tasks are included
    (simulating post-Pass-1 decomposition).

    Returns (adjacency, node_info, total_tasks).
    """
    # node key = f"{course_code}|{class_group}"
    adjacency: dict[str, set[str]] = defaultdict(set)
    node_info: dict[str, dict] = {}

    # Index: which tasks share a teacher? which share a class_group?
    teacher_to_nodes: dict[str, set[str]] = defaultdict(set)
    cg_to_nodes: dict[str, set[str]] = defaultdict(set)

    valid_tasks = []
    for t in teaching_tasks:
        cc = t.get("course_code", "").strip()
        if public_course_codes is not None and cc in public_course_codes:
            continue
        if not cc:
            continue
        cg = t.get("class_group", "").strip()
        if not cg:
            continue
        teacher = t.get("teacher", "").strip()
        node_key = f"{cc}|{cg}"
        valid_tasks.append((node_key, cc, cg, teacher))

    # Build reverse indexes
    for node_key, cc, cg, teacher in valid_tasks:
        node_info[node_key] = {"course_code": cc, "class_group": cg, "teacher": teacher}
        teacher_to_nodes[teacher].add(node_key)
        cg_to_nodes[cg].add(node_key)

    # Connect nodes that share a teacher
    for nodes in teacher_to_nodes.values():
        node_list = list(nodes)
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                adjacency[node_list[i]].add(node_list[j])
                adjacency[node_list[j]].add(node_list[i])

    # Connect nodes that share a class_group
    for nodes in cg_to_nodes.values():
        node_list = list(nodes)
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                adjacency[node_list[i]].add(node_list[j])
                adjacency[node_list[j]].add(node_list[i])

    return adjacency, node_info, len(valid_tasks)


def find_connected_components(
    adjacency: dict[str, set[str]],
) -> list[list[str]]:
    """Return connected components sorted by size (largest first)."""
    visited: set[str] = set()
    components: list[list[str]] = []

    for node in adjacency:
        if node in visited:
            continue
        comp: list[str] = []
        queue = [node]
        visited.add(node)
        while queue:
            cur = queue.pop(0)
            comp.append(cur)
            for neighbor in adjacency.get(cur, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        components.append(comp)

    components.sort(key=len, reverse=True)
    return components


# ── reporting ────────────────────────────────────────────────────────

def report_components(
    title: str,
    components: list[list[str]],
    node_info: dict[str, dict],
    total_tasks: int,
) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)
    print(f"总任务数: {total_tasks}")
    print(f"连通分量数: {len(components)}")

    # Size distribution
    size_dist = Counter()
    for comp in components:
        s = len(comp)
        if s <= 5:
            bucket = "≤5"
        elif s <= 20:
            bucket = "6-20"
        elif s <= 100:
            bucket = "21-100"
        elif s <= 500:
            bucket = "101-500"
        elif s <= 1000:
            bucket = "501-1000"
        else:
            bucket = ">1000"
        size_dist[bucket] += 1

    print("\n分量大小分布:")
    for bucket in ["≤5", "6-20", "21-100", "101-500", "501-1000", ">1000"]:
        cnt = size_dist.get(bucket, 0)
        bar = "█" * max(1, cnt)
        print(f"  {bucket:>10}: {cnt:>3} 个 {bar}")

    # Largest components
    print("\n前 10 大分量:")
    node_count = sum(len(c) for c in components)
    for i, comp in enumerate(components[:10]):
        pct = len(comp) / node_count * 100
        # Show sample teacher/course diversity in this component
        teachers_in_comp = set()
        cgs_in_comp = set()
        courses_in_comp = set()
        for node in comp[:200]:  # sample to avoid slow
            info = node_info.get(node, {})
            if info.get("teacher"):
                teachers_in_comp.add(info["teacher"])
            if info.get("class_group"):
                cgs_in_comp.add(info["class_group"])
            if info.get("course_code"):
                courses_in_comp.add(info["course_code"])
        print(
            f"  #{i+1}: {len(comp):>5} 任务 ({pct:5.1f}%) "
            f"— {len(teachers_in_comp)}教师, {len(cgs_in_comp)}班级, {len(courses_in_comp)}课程"
        )

    # Largest component dominance
    if components:
        largest = len(components[0])
        dominated_pct = largest / node_count * 100
        print(f"\n最大分量占比: {largest}/{node_count} = {dominated_pct:.1f}%")
        if dominated_pct > 80:
            print("⚠️  结论：图高度连通，社区检测/分组求解不可行。")
        elif dominated_pct > 50:
            print("⚠️  结论：图偏连通，分组效果有限。")
        elif len(components) >= 8:
            print("✅ 结论：图可分解为多个独立分量，分组求解可行。")
        else:
            print("⚡ 结论：分量较少但非单一大块，可尝试分组 + 人工拆桥。")


def identify_bridge_courses(
    adjacency: dict[str, set[str]],
    node_info: dict[str, dict],
    components: list[list[str]],
    top_n: int = 10,
) -> None:
    """Identify which courses act as bridges connecting the graph."""
    if len(components) < 2:
        print("\n(无桥接分析：图只有 1 个分量)")
        return

    # For each course, compute the component diversity it touches
    node_to_comp = {}
    for ci, comp in enumerate(components):
        for node in comp:
            node_to_comp[node] = ci

    course_comp_diversity: dict[str, set[int]] = defaultdict(set)
    for node, info in node_info.items():
        cc = info.get("course_code", "")
        if cc and node in node_to_comp:
            course_comp_diversity[cc].add(node_to_comp[node])

    # Courses that span multiple components (in the post-Pass-1 graph)
    bridge_courses = [
        (cc, len(comps))
        for cc, comps in course_comp_diversity.items()
        if len(comps) > 1
    ]
    bridge_courses.sort(key=lambda x: -x[1])

    if bridge_courses:
        print(f"\n桥接课程 Top {min(top_n, len(bridge_courses))} (跨多个分量):")
        for cc, n_comp in bridge_courses[:top_n]:
            print(f"  {cc}: 跨 {n_comp} 个分量")
    else:
        print("\n无桥接课程 — 分量间完全独立。")


# ── main ─────────────────────────────────────────────────────────────

def main() -> None:
    print("加载数据...")

    teaching_tasks = load_jsonl(DATA_DIR / "teaching_tasks_clean.jsonl")
    if not teaching_tasks:
        print("错误: teaching_tasks_clean.jsonl 为空或不存在")
        sys.exit(1)

    # Also load cross-major counts for public course identification
    course_major_counts: dict[str, int] = {}
    if (DATA_DIR / "v3_placement_direct_training_samples_clean.csv").exists():
        direct_samples = load_csv(DATA_DIR / "v3_placement_direct_training_samples_clean.csv")
        # Count unique source_keys per course_code (proxy for cross-major)
        course_source_count: Counter[str] = Counter()
        for row in direct_samples:
            course_code = row.get("course_code", "").strip()
            if course_code:
                course_source_count[course_code] += 1
        course_major_counts = dict(course_source_count)

    # Identify public courses (cross > 10 in training data or known pattern)
    public_codes: set[str] = set()
    for cc, cnt in course_major_counts.items():
        if cnt > 200:  # heuristic: appears very frequently in training data
            public_codes.add(cc)

    # Also add known public course prefixes
    known_public = {"毛927", "智01", "大002", "中019", "大004", "大003", "习736", "思040", "沟048"}
    public_codes |= known_public

    print(f"公共课({len(public_codes)}): {sorted(public_codes)}")

    # ── Scenario A: ALL tasks (pre-Pass-1) ──
    adj_all, info_all, total_all = build_task_dependency_graph(teaching_tasks)
    comps_all = find_connected_components(adj_all)

    # Add isolated tasks that have no edges
    all_node_keys = set(info_all.keys())
    nodes_in_comps = set()
    for comp in comps_all:
        nodes_in_comps.update(comp)
    for node in all_node_keys - nodes_in_comps:
        comps_all.append([node])

    report_components(
        "场景 A：全部任务 (Pass 1 + Pass 2 混在一起)",
        comps_all,
        info_all,
        total_all,
    )

    # ── Scenario B: Only professional courses (post-Pass-1) ──
    adj_pro, info_pro, total_pro = build_task_dependency_graph(
        teaching_tasks, public_course_codes=public_codes
    )
    comps_pro = find_connected_components(adj_pro)

    # Add isolated tasks
    pro_node_keys = set(info_pro.keys())
    nodes_in_comps_pro = set()
    for comp in comps_pro:
        nodes_in_comps_pro.update(comp)
    for node in pro_node_keys - nodes_in_comps_pro:
        comps_pro.append([node])

    report_components(
        "场景 B：仅专业课 (剔除公共课后)",
        comps_pro,
        info_pro,
        total_pro,
    )
    identify_bridge_courses(adj_pro, info_pro, comps_pro)

    # ── Summary ──
    print()
    print("=" * 70)
    print("总结")
    print("=" * 70)

    if len(comps_all) == 1:
        print("场景 A: 全图连通 → 不拆。")
    else:
        print(
            f"场景 A: {len(comps_all)} 分量，最大 {len(comps_all[0])} 任务 "
            f"({len(comps_all[0])/total_all*100:.0f}%)"
        )

    if len(comps_pro) == 1:
        print("场景 B: 剔除公共课后仍然连通 → 不拆。")
    elif len(comps_pro[0]) > total_pro * 0.7:
        print(
            f"场景 B: 最大分量仍占 {len(comps_pro[0])/total_pro*100:.0f}%，"
            "分组效果有限。"
        )
    else:
        top_sizes = [len(c) for c in comps_pro[:5]]
        print(
            f"场景 B: {len(comps_pro)} 分量，前5: {top_sizes} — "
            f"可考虑分组求解。"
        )

    print()
    print("策略建议:")
    if len(comps_pro) > 5 and len(comps_pro[0]) < total_pro * 0.5:
        print(
            "  → Pass 1 排公共课 → Pass 2 各分量独立并行，"
            "每个分量 200-500 任务可承载 GA/CSP。"
        )
    else:
        print(
            "  → 社区检测不可行。需两遍排（Pass 1 公共课锁槽位，"
            "Pass 2 全局贪心/beam search），或改用 CSP/ILP。"
        )


if __name__ == "__main__":
    main()
