"""지표별 경로 안내 (codex&claude.md §16.37).

1. 반경 안 전체 보행망(all_edges)에 지표 A·B·C를 통학로 망과 같은 함수로 계산한다.
2. 경로 모드 4가지. A·B·C는 합치지 않고, 사용자가 고른 지표 하나만 쓴다.
   - 최단: 거리만
   - A: 지나는 교차 지점의 A 점수 합이 가장 작은 경로 (위험 미확인 지점은 지원 점수만)
   - B: 경사 '위험'(>8.3%) 구간 길이 + 계단 구간 길이가 가장 짧은 경로
   - C: 판단 이벤트(급한 전환 + 횡단 이벤트 일단1/이단2/삼단3)가 가장 적은 경로
   A·B·C 모드는 거리가 최단 경로의 CAP배 이하인 경로 중에서 고른다. 방법: 비용 = 거리 + λ×지표를
   λ 여러 값으로 최단경로를 구해, 거리 상한을 지키는 것 중 지표가 가장 작은 경로(같으면 짧은 것).
3. 목적지 = 그 학교의 문 전체(어느 문이든 도착하면 됨).
"""
import heapq
import json
from pathlib import Path

import numpy as np
import pandas as pd

import crosswalk_deficiency as cd
import h5_master
import risk_a_crossing as ra
import risk_b_slope as rb
import risk_c_complexity as rc

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "route"
PROJ = "EPSG:5186"
LAYER = "all_edges"
CAP = 1.3
LAMBDAS = (0, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 5000, 20000)
MODES = ("최단", "A", "B", "C")


# ---------------------------------------------------------------- 1. 전체 보행망 지표
def build_network(save=True):
    master, _, _ = h5_master.build_master()
    acc = cd.load_accidents()
    cw, acc, q = ra.seoul_crosswalks(ra.RADIUS_M, master, acc)
    nets = {}
    for school in ra.SCHOOLS:
        _, _, full = ra.load_school(school, LAYER)
        nets[school] = full.to_crs(PROJ)
    area = rb.study_area(nets)
    samples = rb.load_elevation_samples(area)
    out = {}
    for school in ra.SCHOOLS:
        pts, _ = ra.crossing_points(school, cw, acc, q, layer=LAYER)
        e = rb.score_b(nets[school], samples)
        an, _, cn = rc.score_c(school, pts, layer=LAYER)
        e["급한전환"] = an["급한전환"].to_numpy()
        pts["node"] = pts["node"].astype(str)
        out[school] = {"edges": e, "points": pts}
        if save:
            OUT.mkdir(parents=True, exist_ok=True)
            cols = ["u", "v", "key", "highway", "name", "validation_status", "length_m", "최대경사_pct", "B등급",
                    "기준선_근처", "계단", "급한전환", "geometry"]
            e[cols].to_crs(4326).to_file(OUT / f"{school}_edges.geojson", driver="GeoJSON")
            pts.to_csv(OUT / f"{school}_points.csv", index=False, encoding="utf-8-sig")
    return out


def load_network(school):
    import geopandas as gpd
    e = gpd.read_file(OUT / f"{school}_edges.geojson").to_crs(PROJ)
    e["u"], e["v"] = e["u"].astype(str), e["v"].astype(str)
    p = pd.read_csv(OUT / f"{school}_points.csv", encoding="utf-8-sig", dtype={"node": str})
    return e, p


# ---------------------------------------------------------------- 2. 그래프와 경로
def node_penalties(points):
    """교차 지점 노드의 A 벌점(A 점수, 미확인이면 지원 점수)과 C 횡단 이벤트."""
    a = points["A점수"].fillna(points["지원점수_최대"]).astype(float)
    c = points["횡단단수_최대"].fillna(1).astype(float)
    return dict(zip(points["node"], a)), dict(zip(points["node"], c)), dict(zip(points["node"], points["A점수"]))


def build_graph(edges, points):
    """무방향 그래프 -> 양방향 인접 리스트. 간선 속성: 길이, B 벌점(m), C 급한 전환 수."""
    a_pen, c_node, a_raw = node_penalties(points)
    adj = {}
    for i, r in enumerate(edges.itertuples()):
        b_pen = r.length_m if (r.B등급 == "위험" or bool(r.계단)) else 0.0
        for s, t in ((r.u, r.v), (r.v, r.u)):
            adj.setdefault(s, []).append((t, i, r.length_m, b_pen, float(r.급한전환)))
    return {"adj": adj, "a_pen": a_pen, "c_node": c_node, "a_raw": a_raw, "edges": edges}


def _dijkstra(G, source, mode, lam):
    """비용 = 거리 + lam × (모드 지표). 노드 벌점은 그 노드로 들어갈 때 더한다."""
    a_pen, c_node = G["a_pen"], G["c_node"]
    dist, prev = {source: 0.0}, {}
    pq = [(0.0, source)]
    while pq:
        d, n = heapq.heappop(pq)
        if d > dist.get(n, np.inf):
            continue
        for t, ei, L, bp, turns in G["adj"].get(n, ()):
            if mode == "A":
                pen = a_pen.get(t, 0.0)
            elif mode == "B":
                pen = bp
            elif mode == "C":
                pen = turns + c_node.get(t, 0.0)
            else:
                pen = 0.0
            nd = d + L + lam * pen
            if nd < dist.get(t, np.inf):
                dist[t], prev[t] = nd, (n, ei)
                heapq.heappush(pq, (nd, t))
    return dist, prev


def _path(prev, source, target):
    nodes, eidx = [target], []
    while nodes[-1] != source:
        n, ei = prev[nodes[-1]]
        nodes.append(n)
        eidx.append(ei)
    return nodes[::-1], eidx[::-1]


def path_stats(G, nodes, eidx):
    e = G["edges"].iloc[eidx]
    crossing = [n for n in nodes[1:] if n in G["a_pen"]]
    a_raw = [G["a_raw"][n] for n in crossing]
    return {
        "거리_m": float(e["length_m"].sum()),
        "교차지점_수": len(crossing),
        "A합": float(sum(G["a_pen"][n] for n in crossing)),
        "A3이상_수": int(sum(1 for v in a_raw if pd.notna(v) and v >= 3)),
        "B위험_m": float(e.loc[(e["B등급"] == "위험") | e["계단"].astype(bool), "length_m"].sum()),
        "B주의_m": float(e.loc[e["B등급"] == "주의", "length_m"].sum()),
        "계단_수": int(e["계단"].astype(bool).sum()),
        "C이벤트": float(e["급한전환"].sum() + sum(G["c_node"][n] for n in crossing)),
    }


MODE_METRIC = {"최단": "거리_m", "A": "A합", "B": "B위험_m", "C": "C이벤트"}


def route(G, source, gates, mode, cap=CAP, lambdas=LAMBDAS):
    """source에서 문(들)까지 모드별 경로. 반환: dict(nodes, edges, stats, lam, gate)."""
    def best_for(lam, m):
        dist, prev = _dijkstra(G, source, m, lam)
        reach = [g for g in gates if g in dist]
        if not reach:
            return None
        g = min(reach, key=dist.get)
        nodes, eidx = _path(prev, source, g) if g != source else ([source], [])
        return {"nodes": nodes, "edges": eidx, "stats": path_stats(G, nodes, eidx), "lam": lam, "gate": g}

    shortest = best_for(0, "최단")
    if shortest is None or mode == "최단":
        return shortest
    limit = shortest["stats"]["거리_m"] * cap
    metric = MODE_METRIC[mode]
    best = shortest
    for lam in lambdas[1:]:
        r = best_for(lam, mode)
        if r is None or r["stats"]["거리_m"] > limit + 1e-6:
            continue
        key = (r["stats"][metric], r["stats"]["거리_m"])
        if key < (best["stats"][metric], best["stats"]["거리_m"]):
            best = r
    return best


# ---------------------------------------------------------------- 3. 출발지·문
def origins_and_gates(school):
    o = pd.read_csv(ROOT / "data/option_a_origins_with_osm_gate.csv", encoding="utf-8-sig", dtype={"node": str, "gate_node": str})
    o = o[o["학교"] == school]
    gates = o.drop_duplicates("gate_node").set_index("gate_node")["OSM_최근접_문"].to_dict()
    return o, gates


def simulate_routes(school, G=None):
    """기존 출발지 전부에서 네 모드 경로를 구해 표로 돌려준다."""
    if G is None:
        G = build_graph(*load_network(school))
    o, gates = origins_and_gates(school)
    rows = []
    for r in o.itertuples():
        for mode in MODES:
            res = route(G, r.node, list(gates), mode)
            if res is None:
                continue
            rows.append({"학교": school, "출발지": r.node, "모드": mode, "도착문": gates[res["gate"]],
                         "lam": res["lam"], **res["stats"]})
    return pd.DataFrame(rows)
