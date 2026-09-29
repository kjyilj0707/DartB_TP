"""
2단계: 숭실대 학교 밖 보행 그래프 + 출입문별 통학 구간
=====================================================
- 문 좌표: 카카오 API (data/soongsil_kakao_gates.csv)
- 학교 범위·보행망: OSM (캠퍼스 폴리곤, walk 네트워크)
- 800m 원(직선) 안 학교 밖 보행망에서, 각 노드가 보행거리로 가장 가까운 출입문을 찾는다.

절차
1. build_walk_graph      : 800m 원보다 MARGIN_M 넓은 OSM 보행망 (EPSG:5186, 무방향)
2. remove_school_interior: 학교 폴리곤 안에 50% 이상 들어간 엣지를 지운다
3. connect_gates         : 문마다 남은 그래프의 가장 가까운 노드에 가상 연결선(직선거리)을 붙인다
4. route_from_gates      : 문별 보행 최단경로 -> 노드별 가장 가까운 문, 문까지 거리, 엣지 최단경로 중첩수
"""

from collections import Counter
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString, Point

import soongsil_config as cfg
import viz_campus_definition as viz
from collect_infra_places import bbox_from_center

DATA_DIR = Path(__file__).parent / "data"
PROJ = "EPSG:5186"         # 계산용 (미터)
OUTPUT_CRS = "EPSG:4326"   # 결과물 저장용 (카카오 기준 위경도)
MARGIN_M = 150       # 원 밖 우회 경로를 계산에 쓰기 위한 여유. 결과 표시는 원 안만.
INSIDE_FRAC = 0.5    # 엣지 길이의 이 비율 이상이 학교 폴리곤 안이면 학교 내부 엣지
CONNECT_WARN_M = 25  # 문-노드 연결선이 이보다 길면 경고
GATE_PREFIX = "gate:"


def load_gates():
    """카카오 문 좌표 -> {문 이름: Point(EPSG:5186)}."""
    df = pd.read_csv(DATA_DIR / "soongsil_kakao_gates.csv")
    return {r["문"]: viz.to_proj(Point(r["lon"], r["lat"])) for _, r in df.iterrows()}


def build_walk_graph():
    G0 = ox.graph_from_bbox(bbox_from_center(cfg.CENTER_LAT, cfg.CENTER_LON, cfg.RADIUS_M + MARGIN_M), network_type="walk")
    # 투영을 먼저 해야 한다: project_graph가 무방향 그래프를 방향 그래프로 되돌리기 때문
    return ox.convert.to_undirected(ox.project_graph(G0, to_crs=PROJ))


def remove_school_interior(G, campus):
    """학교 폴리곤 안에 INSIDE_FRAC 이상 들어간 엣지 제거. (G, 제거된 엣지 GeoDataFrame) 반환."""
    edges = ox.graph_to_gdfs(G, nodes=False)
    length = edges.geometry.length
    frac = edges.geometry.intersection(campus).length / length
    removed = edges[frac >= INSIDE_FRAC].copy()
    G = G.copy()
    G.remove_edges_from(list(removed.index))
    G.remove_nodes_from(list(nx.isolates(G)))
    return G, removed


def connect_gates(G, gates):
    """문마다 남은 그래프의 최근접 노드에 가상 연결선을 붙인다. (G, 문 표) 반환."""
    G = G.copy()
    ids = np.array(list(G.nodes))
    xy = np.array([[G.nodes[n]["x"], G.nodes[n]["y"]] for n in ids])
    rows = []
    for name, p in gates.items():
        d = np.hypot(xy[:, 0] - p.x, xy[:, 1] - p.y)
        i = int(d.argmin())
        gid = GATE_PREFIX + name
        G.add_node(gid, x=p.x, y=p.y, gate=name)
        G.add_edge(gid, ids[i], length=float(d[i]), highway="gate_connector", virtual=True,
                   geometry=LineString([(p.x, p.y), (xy[i, 0], xy[i, 1])]))
        rows.append({"문": name, "연결_노드": int(ids[i]), "연결선_m": round(float(d[i]), 1),
                     "경고": bool(d[i] > CONNECT_WARN_M)})
    return G, pd.DataFrame(rows)


def _min_key(G, u, v):
    return min(G[u][v], key=lambda k: G[u][v][k].get("length", np.inf))


def route_from_gates(G, gates, origins):
    """문별 보행 최단경로. 모든 실제 노드에 가까운 문을 붙이고, origins(원 안·학교 밖 노드)만 출발점으로 집계.
    반환: (노드 표, 엣지 최단경로 중첩수 dict{(u,v,key): 횟수})"""
    names = list(gates)
    dist, paths = {}, {}
    for n in names:
        dist[n], paths[n] = nx.single_source_dijkstra(G, GATE_PREFIX + n, weight="length")

    origin_set = set(origins)
    rows = []
    for o in (n for n in G.nodes if not str(n).startswith(GATE_PREFIX)):
        d = {n: dist[n].get(o, np.inf) for n in names}
        order = sorted(names, key=lambda n: d[n])
        nearest = order[0] if np.isfinite(d[order[0]]) else None
        second = order[1] if len(order) > 1 and np.isfinite(d[order[1]]) else None
        p = G.nodes[o]
        eu = {n: np.hypot(p["x"] - gates[n].x, p["y"] - gates[n].y) for n in names}
        rows.append({
            "node": o, "x": p["x"], "y": p["y"], "출발노드": o in origin_set, "가까운_문": nearest,
            "문까지_보행_m": d[nearest] if nearest else np.nan,
            "2순위_문": second, "1-2순위_차이_m": (d[second] - d[nearest]) if second else np.nan,
            "직선_최근접_문": min(names, key=lambda n: eu[n]),
            **{f"보행_{n}_m": round(d[n], 1) if np.isfinite(d[n]) else np.nan for n in names},
        })
    nodes = pd.DataFrame(rows)

    overlap = Counter()
    for _, r in nodes[nodes["출발노드"]].dropna(subset=["가까운_문"]).iterrows():
        path = paths[r["가까운_문"]][r["node"]]
        for u, v in zip(path[:-1], path[1:]):
            overlap[(u, v, _min_key(G, u, v))] += 1
    return nodes, overlap


def edge_table(G, nodes_df, overlap, circle):
    """엣지 GeoDataFrame: 소속 문, 문까지 거리, 최단경로 중첩수."""
    edges = ox.graph_to_gdfs(G, nodes=False).reset_index()
    near = nodes_df.set_index("node")["가까운_문"].to_dict()
    dist = nodes_df.set_index("node")["문까지_보행_m"].to_dict()
    u_gate = edges["u"].map(near); v_gate = edges["v"].map(near)
    edges["소속_문"] = np.where(u_gate == v_gate, u_gate, "경계")
    edges.loc[u_gate.isna() | v_gate.isna(), "소속_문"] = None
    is_conn = edges["highway"].astype(str) == "gate_connector"
    edges.loc[is_conn, "소속_문"] = [str(u).replace(GATE_PREFIX, "") if str(u).startswith(GATE_PREFIX) else str(v).replace(GATE_PREFIX, "")
                                    for u, v in zip(edges.loc[is_conn, "u"], edges.loc[is_conn, "v"])]
    edges["문까지_최소_m"] = np.fmin(edges["u"].map(dist), edges["v"].map(dist)).round(1)
    edges["문까지_최대_m"] = np.fmax(edges["u"].map(dist), edges["v"].map(dist)).round(1)
    edges["최단경로_중첩수"] = [overlap.get((u, v, k), overlap.get((v, u, k), 0)) for u, v, k in zip(edges["u"], edges["v"], edges["key"])]
    edges["원_안"] = edges.geometry.interpolate(0.5, normalized=True).within(circle)
    edges["highway"] = edges["highway"].astype(str)
    return edges


def run():
    campus = viz.to_proj(viz.load_campus_polygon())
    gates = load_gates()
    center = viz.to_proj(Point(cfg.CENTER_LON, cfg.CENTER_LAT))
    circle = center.buffer(cfg.RADIUS_M)

    G_full = build_walk_graph()
    G_cut, removed = remove_school_interior(G_full, campus)
    G, gate_table = connect_gates(G_cut, gates)

    real = [n for n in G.nodes if not str(n).startswith(GATE_PREFIX)]
    origins = [n for n in real
               if circle.contains(Point(G.nodes[n]["x"], G.nodes[n]["y"])) and not campus.contains(Point(G.nodes[n]["x"], G.nodes[n]["y"]))]
    nodes_df, overlap = route_from_gates(G, gates, origins)
    edges = edge_table(G, nodes_df, overlap, circle)
    return dict(campus=campus, gates=gates, circle=circle, G_full=G_full, G_cut=G_cut, G=G, removed=removed,
                gate_table=gate_table, nodes=nodes_df, edges=edges, overlap=overlap)


def save(res, path=DATA_DIR / "soongsil_network.gpkg"):
    """결과물은 EPSG:4326(카카오 기준)으로 저장한다. 다시 읽어 거리·경사를 계산할 때는 PROJ로 바꿔서 쓴다."""
    nodes = gpd.GeoDataFrame(res["nodes"], geometry=gpd.points_from_xy(res["nodes"]["x"], res["nodes"]["y"]), crs=PROJ).to_crs(OUTPUT_CRS)
    nodes = nodes.drop(columns=["x", "y"]).assign(lon=nodes.geometry.x, lat=nodes.geometry.y)
    edges = res["edges"].copy()
    for c in edges.columns:
        if c != "geometry" and edges[c].dtype == object:
            edges[c] = edges[c].astype(str)
    edges.to_crs(OUTPUT_CRS).to_file(path, layer="edges", driver="GPKG")
    nodes.to_file(path, layer="nodes", driver="GPKG")
    return path


if __name__ == "__main__":
    r = run()
    print(r["gate_table"].to_string(index=False))
    print(save(r))
