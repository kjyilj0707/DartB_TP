"""위험도 지표 C(이동 인지 복잡성)를 통학로 망(analysis_edges)에 계산한다.

노션 "보행 위험도 지표 A·B·C 진행 방향"의 규칙을 구현한다.

- 이벤트 = 걷는 동안 판단하거나 방향을 다시 잡아야 하는 순간
  - 횡단: A에서 찾은 교차 지점 하나당 일단 1 / 이단 2 / 삼단 3(횡단보도 없는 교차로는 1).
    이단 = 횡단보도-중간 지점(교통섬 등)-횡단보도로 두 번에 나눠 건너는 형태(팀 확인, 2026-09-24).
    교차 지점에 횡단보도가 여러 개면 그중 가장 큰 단수를 쓴다(A의 "가장 높은 점수" 규칙과 같음).
    민감도: stage_weight=False면 모든 횡단 1.
  - 급한 방향 전환 1회 = 1: 구간 선을 2m 간격으로 다시 나눈 뒤, 10m 안에서 방향이 45° 이상 바뀌는 곳.
    연속해서 조건을 만족하는 곳은 한 번의 전환으로 센다. 교차로에서 다른 구간으로 꺾는 것은 어떤 경로로
    가느냐에 따라 달라지므로 구간 지표에 넣지 않는다.
- 갈림길(전체 보행망에서 세 갈래 이상 만나는 통학로 노드)은 따로 표시한다.
- 구간 C = 구간 안 급한 전환 수 + 끝 교차 지점 이벤트를 그 노드에 붙은 통학로 구간 수로 나눈 몫
  (교차 지점 하나를 여러 구간이 나눠 가져서, 구간 값을 모두 더하면 전체 이벤트 수와 같다).
"""

from pathlib import Path

import numpy as np
import pandas as pd

import risk_a_crossing as ra

ROOT = Path(__file__).resolve().parent
PROJ = "EPSG:5186"

RESAMPLE_M = 2
WINDOW_M = 10
ANGLE_DEG = 45


def _headings(geom, step=RESAMPLE_M):
    L = geom.length
    if L < step * 2:
        return np.array([])
    d = np.arange(0, L + 1e-9, step)
    if d[-1] < L:
        d = np.append(d, L)
    xy = np.array([geom.interpolate(t).coords[0][:2] for t in d])
    v = np.diff(xy, axis=0)
    keep = np.hypot(v[:, 0], v[:, 1]) > 1e-6
    return np.degrees(np.arctan2(v[keep, 1], v[keep, 0]))


def sharp_turns(geom, angle=ANGLE_DEG, window=WINDOW_M, step=RESAMPLE_M):
    """window m 안에서 방향이 angle° 이상 바뀌는 곳의 수(연속 구간은 1회)."""
    h = _headings(geom, step)
    k = max(1, int(round(window / step)))
    if len(h) <= k:
        return 0
    diff = (h[k:] - h[:-k] + 180) % 360 - 180
    flag = np.abs(diff) >= angle
    return int(np.sum(flag[1:] & ~flag[:-1]) + flag[0])


def score_c(school, pts, angle=ANGLE_DEG, window=WINDOW_M, stage_weight=True, layer="analysis_edges"):
    nodes, edges, an = ra.load_school(school, layer)
    an = an.to_crs(PROJ).copy()
    an["length_m"] = an.geometry.length
    an["급한전환"] = [sharp_turns(g, angle, window) for g in an.geometry]

    # 교차 지점 이벤트(일단 1 / 이단 2 / 삼단 3)를 붙은 통학로 구간 수로 나눠 배분
    p = pts[pts["학교"] == school].copy()
    p["node"] = p["node"].astype(str)
    p["횡단이벤트"] = p["횡단단수_최대"].fillna(1).astype(int) if stage_weight else 1
    cross_nodes = set(p["node"])
    ends = pd.concat([an["u"], an["v"]])
    route_deg = ends.value_counts()
    ev = p.set_index("node")["횡단이벤트"]
    share = {n: ev[n] / route_deg[n] for n in cross_nodes if n in route_deg}
    an["횡단_배분"] = an["u"].map(share).fillna(0) + an["v"].map(share).fillna(0)
    an["C이벤트"] = an["급한전환"] + an["횡단_배분"]

    # 갈림길: 전체 보행망 기준 세 갈래 이상 만나는 통학로 노드
    full_deg = pd.concat([edges["u"], edges["v"]]).value_counts()
    route_nodes = set(ends)
    junction = [n for n in route_nodes if full_deg.get(n, 0) >= 3]
    nodes = nodes.set_index("node")
    jn = nodes.loc[nodes.index.intersection(junction), ["x", "y"]].reset_index()
    cn = nodes.loc[nodes.index.intersection(list(cross_nodes)), ["x", "y"]].reset_index()
    cn["횡단이벤트"] = cn["node"].map(ev).to_numpy()
    return an, jn, cn


def summarize(an, jn, cn):
    km = an["length_m"].sum() / 1000
    turns = int(an["급한전환"].sum())
    cross = int(cn["횡단이벤트"].sum())
    return {
        "통학로 길이 (km)": km,
        "교차 지점": len(cn),
        "이단 이상 지점": int((cn["횡단이벤트"] >= 2).sum()),
        "횡단 이벤트": cross,
        "급한 전환": turns,
        "C 이벤트 합": cross + turns,
        "1km당 C 이벤트": (cross + turns) / km,
        "1km당 횡단": cross / km,
        "1km당 급한 전환": turns / km,
        "1km당 갈림길": len(jn) / km,
    }
