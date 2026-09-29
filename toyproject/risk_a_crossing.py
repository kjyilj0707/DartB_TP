"""위험도 지표 A(횡단 위험)를 통학로 망(analysis_edges)의 교차 지점마다 계산한다.

노션 "보행 위험도 지표 A·B·C 진행 방향"(codex&claude.md §16.28)의 규칙을 그대로 구현한다.

1. 교차 지점 찾기
   - 표시된 횡단: 서울시 횡단보도를 교차로관리번호로 묶어 중심점을 만들고, 가장 가까운 통학로 노드에
     붙인다(30m 이내). 큰 교차로는 OSM에서 노드 여러 개로 그려지므로, 전체 그래프 최근접 노드로 붙이면
     통학로 밖의 같은 교차로 노드에 붙어 빠지는 경우가 생긴다(숭실대 8곳). 그래서 통학로 노드에 직접 붙인다.
   - 횡단보도 없는 교차로: 통학로 노드 중 차도 엣지 끝이 3개 이상 만나는 노드(도로 교차로)인데,
     위 매칭에서 횡단보도가 붙지 않았고 30m 안에 횡단보도 점도 없는 곳.
     차도 = residential 등급 이상 + 골목(service=alley). 나머지 service 도로(주차장 통로, 세부 구분 없는 진입로 등)는
     차도로 보지 않는다(2026-09-24 사용자 결정). 민감도: service 전부 제외('none') / 전부 포함('all').
2. 점수
   - 지원 점수: 보행등+음향 0 / 보행등만 1 / 보행등 없음 2 / 횡단보도 없음 3.
     보행등 "무"인데 음향신호기가 배정된 불일치 유형은 2점(민감도: 0점).
   - 부족 점수: 반경 500m 사고건수 합 / 반경 500m 횡단보도 수가 서울 기준 상위 25% 이상이면 1.
     반경 안 사고가 0이면 "위험 미확인"으로 점수를 매기지 않는다.
   - A 점수 = 지원 + 부족 (0~4). 횡단보도가 여러 개인 교차 지점은 횡단보도별 점수의 최댓값.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

import crosswalk_deficiency as cd
import h5_master

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT_DIR = DATA / "risk_index"
PROJ = "EPSG:5186"

SCHOOLS = {
    "숭실대": {"network": DATA / "soongsil_network.gpkg", "analysis": DATA / "soongsil_tmap_validated_network.gpkg"},
    "중앙대": {"network": DATA / "chungang_network.gpkg", "analysis": DATA / "chungang_tmap_validated_network.gpkg"},
}

RADIUS_M = 500
TOP_Q = 0.75
SNAP_M = 30            # 교차로 중심점 -> OSM 노드, 그리고 "근처에 횡단보도 있음" 판정 거리
SIGNAL_COL = "음향_배정_15m"

CAR_ROADS = {
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "busway",
}
SUPPORT_LABEL = {0: "보행등+음향", 1: "보행등만", 2: "보행등 없음", 3: "횡단보도 없음"}


def _highway_set(value):
    s = str(value)
    if s.startswith("["):
        return {t.strip(" '\"") for t in s.strip("[]").split(",")}
    return {s}


def _is_car(row, service_mode):
    types = _highway_set(row["highway"])
    if types & CAR_ROADS:
        return True
    if "service" not in types or service_mode == "none":
        return False
    return service_mode == "all" or "alley" in _highway_set(row.get("service"))


def load_school(school, layer="analysis_edges"):
    """layer: 'analysis_edges'(기본, TMAP 검증 통학로 망) 또는 'all_edges'(반경 안 전체 보행망, 경로 안내용)."""
    cfg = SCHOOLS[school]
    nodes = gpd.read_file(cfg["network"], layer="nodes")
    edges = gpd.read_file(cfg["network"], layer="edges")
    edges = edges[edges["highway"].astype(str).ne("gate_connector")].copy()
    analysis = gpd.read_file(cfg["analysis"], layer=layer)
    for df in (edges, analysis):
        df["u"] = df["u"].astype(str)
        df["v"] = df["v"].astype(str)
    nodes["node"] = nodes["node"].astype(str)
    nodes = nodes.to_crs(PROJ)
    nodes["x"], nodes["y"] = nodes.geometry.x, nodes.geometry.y
    return nodes, edges, analysis


def car_degree(edges, service_mode="alley"):
    car = edges[edges.apply(_is_car, axis=1, service_mode=service_mode)]
    return pd.concat([car["u"], car["v"]]).value_counts()


def seoul_crosswalks(radius=RADIUS_M, master=None, acc=None):
    """서울 전체 정상 좌표 횡단보도 + 음향 배정 + 반경 위험·인프라 + 서울 기준 부족 플래그."""
    if master is None:
        master, _, _ = h5_master.build_master()
    cw = master[master["좌표상태"] == "정상"].reset_index(drop=True)
    if acc is None:
        acc = cd.load_accidents()
    base = cd.build(radius, cw[["x", "y", SIGNAL_COL]], acc)
    cw["인프라"] = base["인프라"].to_numpy()
    cw["위험"] = base["위험"].to_numpy()
    hot, q = cd.summarize(base, TOP_Q)
    cw["부족지수_비율"] = np.where(cw["위험"] > 0, cw["위험"] / cw["인프라"].replace(0, np.nan), np.nan)
    cw["부족"] = np.where(cw["위험"] > 0, (cw["부족지수_비율"] >= q).astype(float), np.nan)
    cw.attrs["radius"] = radius
    return cw, acc, q


def support_score(cw, mismatch_as=2):
    signal = cw["보행등유무"].eq("유")
    audible = cw[SIGNAL_COL].astype(float).eq(1)
    score = np.select([signal & audible, signal & ~audible], [0, 1], default=2)
    mismatch = ~signal & audible
    score = np.where(mismatch, mismatch_as, score)
    return pd.Series(score, index=cw.index), mismatch


def point_deficiency(xy, cw, acc, q):
    """임의 좌표(횡단보도 없는 교차로)에서 같은 식으로 부족 여부를 계산한다."""
    radius = cw.attrs.get("radius", RADIUS_M)
    infra = np.array([len(v) for v in cKDTree(cw[["x", "y"]].to_numpy()).query_ball_point(xy, radius)])
    idx = cKDTree(acc[["x", "y"]].to_numpy()).query_ball_point(xy, radius)
    counts = acc["사고건수"].to_numpy()
    risk = np.array([counts[i].sum() if len(i) else 0 for i in idx])
    ratio = np.where(risk > 0, risk / np.where(infra == 0, np.nan, infra), np.nan)
    deficient = np.where(risk > 0, (ratio >= q).astype(float), np.nan)
    return infra, risk, ratio, deficient


def crossing_points(school, cw, acc, q, service_mode="alley", mismatch_as=2, layer="analysis_edges"):
    nodes, edges, analysis = load_school(school, layer)
    route_nodes = set(analysis["u"]) | set(analysis["v"])
    route = nodes[nodes["node"].isin(route_nodes)].reset_index(drop=True)
    node_tree = cKDTree(route[["x", "y"]].to_numpy())

    # 1) 표시된 횡단: 교차로 중심 -> 가장 가까운 통학로 노드(30m 이내)
    cw = cw.copy()
    cw["지원점수"], cw["불일치"] = support_score(cw, mismatch_as)
    cw["A점수"] = np.where(cw["위험"] > 0, cw["지원점수"] + cw["부족"], np.nan)
    groups = cw.groupby("교차로관리번호")[["x", "y"]].mean()
    d, i = node_tree.query(groups.to_numpy())
    groups["node"] = route["node"].to_numpy()[i]
    groups["snap_m"] = d
    near = groups[groups["snap_m"] <= SNAP_M]
    marked_cw = cw[cw["교차로관리번호"].isin(near.index)].copy()
    marked_cw["node"] = marked_cw["교차로관리번호"].map(near["node"])

    marked_cw["횡단단수"] = marked_cw["횡단보도종류"].astype(str).map(
        lambda k: 3 if k.startswith("삼단") else 2 if k.startswith("이단") else 1)
    agg = marked_cw.groupby("node").agg(
        횡단보도수=("횡단보도관리번호", "size"),
        횡단단수_최대=("횡단단수", "max"),
        이단_수=("횡단단수", lambda s: int((s >= 2).sum())),
        교차로관리번호=("교차로관리번호", lambda s: ",".join(sorted(set(map(str, s))))),
        지원점수_최대=("지원점수", "max"),
        불일치_수=("불일치", "sum"),
        보행등없음_수=("보행등유무", lambda s: int((s != "유").sum())),
        음향_수=(SIGNAL_COL, lambda s: int(s.astype(float).eq(1).sum())),
        위험=("위험", "max"),
        인프라=("인프라", "max"),
        부족=("부족", "max"),
        A점수=("A점수", "max"),
    ).reset_index()
    agg["유형"] = "횡단보도 있음"

    # 2) 횡단보도 없는 교차로
    deg = car_degree(edges, service_mode)
    cand = route[route["node"].map(deg).fillna(0).ge(3)]
    cand = cand[~cand["node"].isin(agg["node"])]
    cw_tree = cKDTree(cw[["x", "y"]].to_numpy())
    has_cw = np.array([len(v) > 0 for v in cw_tree.query_ball_point(cand[["x", "y"]].to_numpy(), SNAP_M)])
    unmarked = cand[~has_cw].copy()
    infra, risk, ratio, deficient = point_deficiency(unmarked[["x", "y"]].to_numpy(), cw, acc, q)
    unmarked = pd.DataFrame({
        "node": unmarked["node"].to_numpy(), "횡단보도수": 0, "횡단단수_최대": 1, "이단_수": 0, "지원점수_최대": 3,
        "위험": risk, "인프라": infra, "부족": deficient,
        "A점수": np.where(risk > 0, 3 + np.nan_to_num(deficient), np.nan),
        "유형": "횡단보도 없는 교차로",
    })

    pts = pd.concat([agg, unmarked], ignore_index=True)
    pts["차도_엣지수"] = pts["node"].map(deg).fillna(0).astype(int)
    pts["지원수준"] = pts["지원점수_최대"].map(SUPPORT_LABEL)
    pts["위험미확인"] = pts["위험"].eq(0)
    pts["학교"] = school
    pts = pts.merge(nodes[["node", "x", "y", "lon", "lat"]], on="node", how="left")
    diag = {"교차로중심_스냅거리": groups["snap_m"], "근처_그룹": near, "표시횡단_횡단보도": marked_cw}
    return pts, diag


def seoul_scores(cw, mismatch_as=2):
    """서울 전체 횡단보도(위험>0)에 같은 0~3점(횡단보도 없음 제외) 점수를 매겨 비교 기준으로 쓴다."""
    s = cw.copy()
    s["지원점수"], s["불일치"] = support_score(s, mismatch_as)
    s = s[s["위험"] > 0].copy()
    s["A점수"] = s["지원점수"] + s["부족"]
    return s


def run(save=True):
    cw, acc, q = seoul_crosswalks()
    results = {}
    for school in SCHOOLS:
        main, diag = crossing_points(school, cw, acc, q)
        svc, _ = crossing_points(school, cw, acc, q, service_mode="all")
        mis0, _ = crossing_points(school, cw, acc, q, mismatch_as=0)
        results[school] = {"main": main, "diag": diag, "service": svc, "mismatch0": mis0}
    seoul = seoul_scores(cw)
    if save:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        allpts = pd.concat([r["main"] for r in results.values()], ignore_index=True)
        allpts.to_csv(OUT_DIR / "A_crossing_points.csv", index=False, encoding="utf-8-sig")
        gpd.GeoDataFrame(allpts, geometry=gpd.points_from_xy(allpts["lon"], allpts["lat"]), crs="EPSG:4326").to_file(
            OUT_DIR / "A_crossing_points.geojson", driver="GeoJSON")
    return cw, q, results, seoul


if __name__ == "__main__":
    run()
