"""중앙대 1·2단계: 캠퍼스 경계, 카카오 출입문, 학교 밖 보행 그래프."""

import json
from pathlib import Path
from shapely.geometry import LineString, Point
from shapely.ops import polygonize, unary_union

import geopandas as gpd
import osmnx as ox
import pandas as pd

import chungang_config as cfg
import soongsil_network as base
import viz_campus_definition as viz
from collect_infra_places import bbox_from_center

DATA_DIR = Path(__file__).parent / "data"
PROJ = "EPSG:5186"
OUTPUT_CRS = "EPSG:4326"
OSM_RELATION_ID = 284355223
MARGIN_M = 150


def load_campus_polygon():
    """OSM 중앙대 서울캠퍼스 relation을 캐시하고 EPSG:4326 geometry로 반환한다."""
    path = DATA_DIR / "chungang_campus_polygon.geojson"
    if path.exists():
        return gpd.read_file(path).geometry.iloc[0]
    # 2026-09-22 전 대학 경계 감사 때 내려받은 OSM 원본을 우선 재사용한다.
    cache = DATA_DIR / "h7" / "gate_audit_20260922" / "osm_campuses.json"
    elements = json.loads(cache.read_text(encoding="utf-8"))["elements"] if cache.exists() else []
    matches = [e for e in elements if e.get("id") == OSM_RELATION_ID]
    if not matches:
        matches = viz.overpass(f"[out:json][timeout:60];nwr({OSM_RELATION_ID});out geom;")["elements"]
    element = matches[0]
    if element["type"] == "way":
        # OSM way는 닫힌 좌표열이므로 원형을 그대로 사용한다.
        from shapely.geometry import Polygon
        poly = Polygon([(p["lon"], p["lat"]) for p in element["geometry"]]).buffer(0)
    else:
        lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                 for m in element["members"] if m.get("role") == "outer" and "geometry" in m]
        poly = unary_union(list(polygonize(unary_union(lines))))
    gpd.GeoSeries([poly], crs=OUTPUT_CRS).to_file(path, driver="GeoJSON")
    return poly


def load_gates_ll():
    """공식 안내에서 확인된 3개 문에 대응하는 카카오 입출구 POI 좌표."""
    path = DATA_DIR / "chungang_kakao_gates.csv"
    if not path.exists():
        pd.DataFrame([
            {"문": "정문", "lat": 37.5067563369528, "lon": 126.958469749756},
            {"문": "중문", "lat": 37.5059431853532, "lon": 126.957222722899},
            {"문": "후문", "lat": 37.5049202595248, "lon": 126.954064506402},
        ]).to_csv(path, index=False, encoding="utf-8-sig")
    return pd.read_csv(path)


def load_gates():
    df = load_gates_ll()
    return {r["문"]: viz.to_proj(Point(r["lon"], r["lat"])) for _, r in df.iterrows()}


def load_walk_edges():
    graph = ox.graph_from_bbox(
        bbox_from_center(cfg.CENTER_LAT, cfg.CENTER_LON, cfg.RADIUS_M + MARGIN_M),
        network_type="walk",
    )
    graph = ox.convert.to_undirected(ox.project_graph(graph, to_crs=PROJ))
    return ox.graph_to_gdfs(graph, nodes=False).reset_index(drop=True)


def run():
    campus = viz.to_proj(load_campus_polygon())
    gates = load_gates()
    center = viz.to_proj(Point(cfg.CENTER_LON, cfg.CENTER_LAT))
    circle = center.buffer(cfg.RADIUS_M)

    graph0 = ox.graph_from_bbox(
        bbox_from_center(cfg.CENTER_LAT, cfg.CENTER_LON, cfg.RADIUS_M + MARGIN_M),
        network_type="walk",
    )
    graph_full = ox.convert.to_undirected(ox.project_graph(graph0, to_crs=PROJ))
    graph_cut, removed = base.remove_school_interior(graph_full, campus)
    graph, gate_table = base.connect_gates(graph_cut, gates)
    real = [n for n in graph.nodes if not str(n).startswith(base.GATE_PREFIX)]
    origins = [n for n in real if circle.contains(Point(graph.nodes[n]["x"], graph.nodes[n]["y"]))
               and not campus.contains(Point(graph.nodes[n]["x"], graph.nodes[n]["y"]))]
    nodes, overlap = base.route_from_gates(graph, gates, origins)
    edges = base.edge_table(graph, nodes, overlap, circle)
    return dict(campus=campus, gates=gates, circle=circle, G_full=graph_full, G_cut=graph_cut,
                G=graph, removed=removed, gate_table=gate_table, nodes=nodes,
                edges=edges, overlap=overlap)


def save(res, path=DATA_DIR / "chungang_network.gpkg"):
    return base.save(res, path)
