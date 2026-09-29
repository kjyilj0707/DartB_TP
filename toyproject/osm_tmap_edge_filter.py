"""OSM 후보 보행망을 TMAP 실제 도보경로로 검증·필터링한다.

최종 규칙
1. 학교 범위와 출입문 좌표는 OSM을 사용한다.
2. 반경 800 m의 학교 밖 영역을 격자로 나누고 각 격자에서 임의 좌표를 뽑는다.
3. 임의 좌표를 OSM 보행 그래프의 최근접 노드에 스냅하고 중복 노드를 제거한다.
4. 기본 모드에서는 OSM 보행거리상 가장 가까운 문 하나로 TMAP 경로를 요청한다.
5. TMAP 경로를 OSM 엣지에 매칭해 validated / unobserved로 표시한다.

TMAP 원본 geometry는 메모리에서만 처리하며 저장하지 않는다. 저장 산출물은 임의
출발지, OSM 문, 엣지별 경로 관측 횟수와 집계표다.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import Point, box

import chungang_config
import soongsil_config
import tmap_commute_pipeline as tmap


ROOT = Path(__file__).parent
DATA = ROOT / "data"
PROJ = "EPSG:5186"
WGS84 = "EPSG:4326"

SCHOOLS = {
    "숭실대": {
        "center": (soongsil_config.CENTER_LAT, soongsil_config.CENTER_LON),
        "campus": DATA / "soongsil_campus_polygon.geojson",
        "network": DATA / "soongsil_network.gpkg",
        "gate_output": DATA / "soongsil_osm_gates.csv",
        "official_gate_seed": DATA / "soongsil_kakao_gates.csv",
    },
    "중앙대": {
        "center": (chungang_config.CENTER_LAT, chungang_config.CENTER_LON),
        "campus": DATA / "chungang_campus_polygon.geojson",
        "network": DATA / "chungang_network.gpkg",
        "gate_output": DATA / "chungang_osm_gates.csv",
        "official_gate_seed": DATA / "chungang_kakao_gates.csv",
    },
}

OSM_GATE_CANDIDATES = (
    DATA / "h7" / "gate_audit_20260922" / "all64" / "osm_path_boundary_candidates.csv"
)
UNIV_IDS = {"숭실대": 11124718, "중앙대": 11160006}


def _point_to_proj(lon: float, lat: float) -> Point:
    return gpd.GeoSeries([Point(lon, lat)], crs=WGS84).to_crs(PROJ).iloc[0]


def build_osm_gates(save: bool = True, max_seed_distance_m: float = 60) -> pd.DataFrame:
    """공식 문 이름별 최근접 OSM 경계 교차점을 문 좌표로 채택한다.

    Kakao 좌표는 이름을 붙이기 위한 seed로만 사용한다. 최종 lat/lon과 source_id는
    OSM 보행로-캠퍼스 경계 교차 후보에서 가져온다.
    """
    candidates = pd.read_csv(OSM_GATE_CANDIDATES)
    rows = []
    for school, spec in SCHOOLS.items():
        cand = candidates[candidates["univ_id"].eq(UNIV_IDS[school])].copy()
        seeds = pd.read_csv(spec["official_gate_seed"])
        used = set()
        for _, seed in seeds.iterrows():
            seed_p = _point_to_proj(seed["lon"], seed["lat"])
            distances = []
            for idx, c in cand.iterrows():
                if idx in used:
                    continue
                distance = seed_p.distance(_point_to_proj(c["lon"], c["lat"]))
                distances.append((distance, idx, c))
            if not distances:
                raise RuntimeError(f"{school} {seed['문']}: 사용할 OSM 문 후보가 없습니다.")
            distance, idx, picked = min(distances, key=lambda x: x[0])
            if distance > max_seed_distance_m:
                raise RuntimeError(
                    f"{school} {seed['문']}: 최근접 OSM 경계 교차점이 {distance:.1f}m 떨어져 있습니다."
                )
            used.add(idx)
            rows.append({
                "학교": school,
                "문": seed["문"],
                "lat": float(picked["lat"]),
                "lon": float(picked["lon"]),
                "osm_way_id": int(picked["osm_way_id"]),
                "highway": picked["highway"],
                "seed_distance_m": round(float(distance), 1),
                "coordinate_source": "OSM path-campus boundary intersection",
                "source_url": picked["source_url"],
            })
        school_rows = pd.DataFrame([r for r in rows if r["학교"] == school])
        if save:
            school_rows.drop(columns="학교").to_csv(
                spec["gate_output"], index=False, encoding="utf-8-sig"
            )
    return pd.DataFrame(rows)


def load_osm_gates() -> pd.DataFrame:
    frames = []
    for school, spec in SCHOOLS.items():
        if not spec["gate_output"].exists():
            build_osm_gates(save=True)
        frame = pd.read_csv(spec["gate_output"])
        frame.insert(0, "학교", school)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def load_network(school: str) -> tuple[nx.MultiGraph, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """저장된 OSM 노드·엣지를 WGS84 MultiGraph로 복원한다."""
    path = SCHOOLS[school]["network"]
    nodes = gpd.read_file(path, layer="nodes").copy()
    edges = gpd.read_file(path, layer="edges").copy()
    edges = edges[edges["highway"].astype(str).ne("gate_connector")].copy()
    nodes["node"] = nodes["node"].astype(str)
    edges["u"] = edges["u"].astype(str)
    edges["v"] = edges["v"].astype(str)
    edges["key"] = pd.to_numeric(edges["key"], errors="coerce").fillna(0).astype(int)

    graph = nx.MultiGraph()
    graph.graph["crs"] = WGS84
    for r in nodes.itertuples():
        graph.add_node(r.node, x=float(r.lon), y=float(r.lat))
    for r in edges.itertuples():
        if r.u not in graph or r.v not in graph:
            continue
        graph.add_edge(
            r.u, r.v, key=int(r.key), length=float(r.length),
            geometry=r.geometry, highway=str(r.highway),
        )
    return graph, nodes, edges


def _random_point_in_polygon(geom, rng: np.random.Generator) -> Point:
    minx, miny, maxx, maxy = geom.bounds
    for _ in range(1000):
        point = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if geom.covers(point):
            return point
    return geom.representative_point()


def generate_option_a_origins(
    grid_m: float = 150,
    seed: int = 20260923,
    save: bool = True,
) -> pd.DataFrame:
    """800m 학교 밖 영역의 각 격자에서 임의점 1개를 뽑아 OSM 노드에 스냅한다."""
    rng = np.random.default_rng(seed)
    rows = []
    for school, spec in SCHOOLS.items():
        graph, nodes, _ = load_network(school)
        lat, lon = spec["center"]
        center = _point_to_proj(lon, lat)
        campus = gpd.read_file(spec["campus"]).to_crs(PROJ).geometry.union_all()
        analysis = center.buffer(800).difference(campus)

        minx, miny, maxx, maxy = analysis.bounds
        raw_points = []
        cell_id = 0
        x = np.floor(minx / grid_m) * grid_m
        while x < maxx:
            y = np.floor(miny / grid_m) * grid_m
            while y < maxy:
                clipped = analysis.intersection(box(x, y, x + grid_m, y + grid_m))
                if not clipped.is_empty and clipped.area >= grid_m * grid_m * 0.08:
                    raw_points.append((cell_id, _random_point_in_polygon(clipped, rng)))
                    cell_id += 1
                y += grid_m
            x += grid_m

        raw_ll = gpd.GeoSeries([p for _, p in raw_points], crs=PROJ).to_crs(WGS84)
        # 사용자 선택 Option A: 임의 lon/lat를 OSM 그래프의 최근접 노드로 스냅한다.
        snapped = ox.distance.nearest_nodes(
            graph,
            X=raw_ll.x.to_numpy(),
            Y=raw_ll.y.to_numpy(),
        )
        node_lookup = nodes.set_index("node")
        for (cell, raw), raw_wgs, node_id in zip(raw_points, raw_ll, snapped):
            node_id = str(node_id)
            if node_id not in node_lookup.index:
                continue
            node = node_lookup.loc[node_id]
            node_proj = _point_to_proj(float(node.lon), float(node.lat))
            if not analysis.covers(node_proj):
                continue
            rows.append({
                "학교": school,
                "출발지유형": "800m층화임의점_OSM스냅",
                "출발지명": f"{school} 표본노드 {node_id}",
                "grid_cell": int(cell),
                "raw_lat": float(raw_wgs.y),
                "raw_lon": float(raw_wgs.x),
                "lat": float(node.lat),
                "lon": float(node.lon),
                "node": node_id,
                "snap_distance_m": round(float(raw.distance(node_proj)), 1),
                "source": "OptionA_random_to_OSM",
                "source_id": f"{school}:{node_id}",
            })

    result = pd.DataFrame(rows)
    result = (
        result.sort_values(["학교", "snap_distance_m", "grid_cell"])
        .drop_duplicates(["학교", "node"])
        .sort_values(["학교", "grid_cell"])
        .reset_index(drop=True)
    )
    if save:
        result.to_csv(DATA / "option_a_random_origins.csv", index=False, encoding="utf-8-sig")
    return result


def gate_nodes(school: str, school_gates: pd.DataFrame, graph: nx.MultiGraph) -> list[str]:
    """문마다 보행망 진입 노드를 정한다.

    단순 최근접 노드는 막다른 노드에 붙을 수 있다(숭실대 정문: 1.6m 차이로 389m
    막다른 footway 끝에 붙어 실제 진입 노드와 보행망상 840m 떨어짐). 그래서 2단계
    네트워크의 gate_connector가 연결한 노드를 우선 쓰고, 없으면 degree 2 이상인
    최근접 노드를 쓴다.
    """
    raw = gpd.read_file(SCHOOLS[school]["network"], layer="edges")
    connectors = raw[raw["highway"].astype(str).eq("gate_connector")]
    connector_node = {
        str(v).split(":", 1)[1]: str(u)
        for u, v in zip(connectors["u"], connectors["v"])
        if str(u) in graph
    }
    through = [n for n in graph.nodes if graph.degree(n) >= 2]
    result = []
    for gate in school_gates.itertuples():
        if gate.문 in connector_node:
            result.append(connector_node[gate.문])
            continue
        gate_p = _point_to_proj(gate.lon, gate.lat)
        result.append(min(
            through,
            key=lambda n: gate_p.distance(
                _point_to_proj(graph.nodes[n]["x"], graph.nodes[n]["y"])
            ),
        ))
    return result


def assign_osm_nearest_gate(origins: pd.DataFrame) -> pd.DataFrame:
    """스냅된 출발 노드마다 OSM 보행거리상 가장 가까운 OSM 문을 배정한다."""
    gates = load_osm_gates()
    assigned = []
    for school, group in origins.groupby("학교"):
        graph, _, _ = load_network(school)
        school_gates = gates[gates["학교"].eq(school)].copy()
        school_gates["gate_node"] = gate_nodes(school, school_gates, graph)
        lengths = {
            r.문: nx.single_source_dijkstra_path_length(
                graph, str(r.gate_node), weight="length"
            )
            for r in school_gates.itertuples()
        }
        gate_by_name = school_gates.set_index("문")
        for _, origin in group.iterrows():
            candidates = [
                (distances.get(str(origin["node"]), np.inf), name)
                for name, distances in lengths.items()
            ]
            distance, gate_name = min(candidates)
            if not np.isfinite(distance):
                continue
            gate = gate_by_name.loc[gate_name]
            row = origin.to_dict()
            row.update({
                "OSM_최근접_문": gate_name,
                "OSM_문까지_m": round(float(distance), 1),
                "gate_node": str(gate["gate_node"]),
                "gate_lat": float(gate["lat"]),
                "gate_lon": float(gate["lon"]),
                "gate_osm_way_id": int(gate["osm_way_id"]),
            })
            assigned.append(row)
    return pd.DataFrame(assigned)


def expected_calls(origins: pd.DataFrame, gate_mode: str = "osm_nearest") -> int:
    if gate_mode == "osm_nearest":
        return len(origins)
    if gate_mode == "all":
        gate_counts = load_osm_gates().groupby("학교").size()
        return int(sum(len(g) * gate_counts.loc[school] for school, g in origins.groupby("학교")))
    raise ValueError("gate_mode은 'osm_nearest' 또는 'all'이어야 합니다.")


def run_tmap_filter_routes(assigned: pd.DataFrame) -> gpd.GeoDataFrame:
    """OSM 최근접 문으로 TMAP 경로를 요청한다. 호출 여부는 실행 스크립트가 통제한다.

    한 건이 실패해도 이미 쓴 호출을 잃지 않도록 오류를 기록하고 다음으로 넘어간다.
    """
    rows = []
    for _, origin in assigned.iterrows():
        gate = pd.Series({
            "학교": origin["학교"], "문": origin["OSM_최근접_문"],
            "lat": origin["gate_lat"], "lon": origin["gate_lon"],
        })
        try:
            rows.append(tmap.request_pedestrian_route(origin, gate))
        except Exception as exc:
            rows.append({
                "학교": origin["학교"], "origin_id": f"{origin['source']}:{origin['source_id']}",
                "출발지명": origin["출발지명"], "출발지유형": origin["출발지유형"],
                "문": gate["문"], "distance_m": np.nan, "time_s": np.nan, "geometry": None,
                "오류": str(exc),
            })
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=WGS84)


def validate_edges(
    routes: gpd.GeoDataFrame,
    max_distance_m: float = 20,
) -> tuple[dict[str, gpd.GeoDataFrame], pd.DataFrame]:
    """TMAP 경로 합집합으로 OSM 엣지를 validated/unobserved로 분류한다."""
    outputs = {}
    route_summaries = []
    for school, group in routes.groupby("학교"):
        _, _, edges_wgs = load_network(school)
        edges = edges_wgs.to_crs(PROJ).reset_index(drop=True)
        edges["edge_row"] = edges.index
        hit_routes = Counter()
        failed = group[group.geometry.isna()]
        for _, route in failed.iterrows():
            route_summaries.append({
                "학교": school, "origin_id": route["origin_id"], "문": route["문"],
                "오류": route.get("오류", "geometry 없음"),
            })
        for route_idx, route in group[group.geometry.notna()].to_crs(PROJ).iterrows():
            sampled = tmap._sample_line(route.geometry, spacing_m=10)
            points = gpd.GeoDataFrame(
                {"sample_id": range(len(sampled))}, geometry=sampled, crs=PROJ
            )
            joined = gpd.sjoin_nearest(
                points,
                edges[["edge_row", "geometry"]],
                how="left",
                distance_col="match_distance_m",
            )
            valid = joined[joined["match_distance_m"] <= max_distance_m].copy()
            matched_samples = valid["sample_id"].nunique()
            edge_rows = valid["edge_row"].dropna().astype(int).unique()
            for edge_row in edge_rows:
                hit_routes[int(edge_row)] += 1
            route_summaries.append({
                "학교": school,
                "origin_id": route["origin_id"],
                "문": route["문"],
                "TMAP거리_m": route["distance_m"],
                "표본점수": len(points),
                "20m이내매칭점수": matched_samples,
                "매칭률_pct": round(100 * matched_samples / len(points), 1),
                "매칭OSM엣지수": len(edge_rows),
            })
        edges["tmap_hit_routes"] = edges["edge_row"].map(hit_routes).fillna(0).astype(int)
        edges["validation_status"] = np.where(
            edges["tmap_hit_routes"].gt(0), "validated", "unobserved"
        )
        outputs[school] = edges.drop(columns="edge_row").to_crs(WGS84)
    return outputs, pd.DataFrame(route_summaries)


def bridge_validated_gaps(
    school: str,
    edges: gpd.GeoDataFrame,
    max_gap_m: float = 15,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """validated 엣지 조각 사이의 짧은 OSM 간격을 최단경로로 잇는다.

    10m 표본이 짧은 연결 엣지를 건너뛰거나 평행 엣지에 붙으면 validated 망이 수 m
    간격으로 끊긴다. 원본 TMAP geometry는 없으므로 OSM만 사용해, 다른 조각까지의
    보행망 최단거리가 max_gap_m 이하인 경우만 그 경로 엣지를 'bridged'로 표시한다.
    TMAP이 직접 관측한 엣지(validated)와 구분하고, 분석망은 두 상태를 합친 것이다.
    """
    graph, _, _ = load_network(school)
    edges = edges.copy()
    edges["u"] = edges["u"].astype(str)
    edges["v"] = edges["v"].astype(str)
    row_of = {}
    for idx, r in edges.iterrows():
        row_of[(r.u, r.v, int(r.key))] = idx
        row_of[(r.v, r.u, int(r.key))] = idx
    in_net = edges["validation_status"].eq("validated")
    bridges = []
    while True:
        net = nx.from_pandas_edgelist(edges[in_net], "u", "v")
        comps = sorted(nx.connected_components(net), key=len, reverse=True)
        best = None
        for i, comp in enumerate(comps[1:], 1):
            others = set().union(*(c for j, c in enumerate(comps) if j != i))
            dist, paths = nx.multi_source_dijkstra(graph, comp, weight="length", cutoff=max_gap_m)
            hits = [(dist[n], n) for n in others if n in dist]
            if hits and (best is None or min(hits)[0] < best[0]):
                gap, target = min(hits)
                best = (gap, paths[target], len(comp))
        if best is None:
            break
        gap, path, comp_edges = best
        added = []
        for a, b in zip(path[:-1], path[1:]):
            key = min(graph[a][b], key=lambda k: graph[a][b][k]["length"])
            idx = row_of[(a, b, key)]
            if not in_net.loc[idx]:
                in_net.loc[idx] = True
                edges.loc[idx, "validation_status"] = "bridged"
                added.append(idx)
        bridges.append({
            "학교": school, "간격_m": round(gap, 1), "연결조각_노드수": comp_edges,
            "추가엣지수": len(added), "추가길이_m": round(float(edges.loc[added, "length"].sum()), 1),
        })
    edges["analysis_edge"] = edges["validation_status"].isin(["validated", "bridged"])
    return edges, pd.DataFrame(bridges)


def save_validated_outputs(
    edge_outputs: dict[str, gpd.GeoDataFrame],
    route_summary: pd.DataFrame,
) -> None:
    """원본 TMAP geometry 없이 OSM 엣지 관측 결과와 집계만 저장한다."""
    for school, edges in edge_outputs.items():
        slug = "soongsil" if school == "숭실대" else "chungang"
        output = DATA / f"{slug}_tmap_validated_network.gpkg"
        edges.to_file(output, layer="all_edges", driver="GPKG")
        edges[edges["validation_status"].eq("validated")].to_file(
            output, layer="validated_edges", driver="GPKG"
        )
        if "analysis_edge" in edges:
            edges[edges["analysis_edge"]].to_file(
                output, layer="analysis_edges", driver="GPKG"
            )
    route_summary.to_csv(
        DATA / "option_a_tmap_route_match_summary.csv", index=False, encoding="utf-8-sig"
    )


def prepare(grid_m: float = 150, seed: int = 20260923) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    gates = build_osm_gates(save=True)
    origins = generate_option_a_origins(grid_m=grid_m, seed=seed, save=True)
    assigned = assign_osm_nearest_gate(origins)
    assigned.to_csv(DATA / "option_a_origins_with_osm_gate.csv", index=False, encoding="utf-8-sig")
    return gates, origins, assigned


if __name__ == "__main__":
    gates, origins, assigned = prepare()
    print(gates.groupby("학교").size().rename("OSM문수"))
    print(origins.groupby("학교").size().rename("중복제거후_표본노드수"))
    print(assigned.groupby(["학교", "OSM_최근접_문"]).size().rename("표본수"))
    print(f"기본 실행 예상 TMAP 호출: {expected_calls(assigned):,}회")
    print("TMAP은 이 준비 단계에서 호출하지 않았습니다.")
