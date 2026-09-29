"""
4단계: 엣지별 경사도 결합
=========================
목적
----
2단계에서 만든 보행자 도로망 그래프의 각 엣지(도로 한 조각)에 경사도를 붙인다.
(자세한 설명은 step4_경사도_결합_설명.md 참고)

서울시 경사도 등고선(LineString, HEIGHT 속성) + 표고점(Point, HEIGHT 속성)을
합쳐 (x, y, 높이) 산점 데이터를 만들고, 이를 보간해서 그래프의 각 노드 위치의
높이를 추정한 뒤, 엣지 양 끝 노드의 높이차 / 엣지 길이로 경사도(%)를 계산한다.

사용법
------
python compute_edge_slope.py
결과: data/pedestrian_graph_with_slope.graphml
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import osmnx as ox
from scipy.interpolate import griddata
from shapely.geometry import box

import collect_infra_places as infra_collect
import snap_infra_to_network as snap

PROJECT_DIR = Path(__file__).parent
CONTOUR_PATH = PROJECT_DIR / "서울시_경사도" / "등고선 5000" / "N3L_F001.shp"
ELEV_POINT_PATH = PROJECT_DIR / "서울시_경사도" / "표고 5000" / "N3P_F002.shp"
GRAPH_WITH_SLOPE_PATH = snap.DATA_DIR / "pedestrian_graph_with_slope.graphml"

# bbox 경계 바로 바깥의 등고선·표고점도 같이 써야 경계 근처 노드의 보간이 안정적이다.
BUFFER_M = 300


def load_elevation_samples(bbox_wgs84, target_crs, buffer_m=BUFFER_M):
    """등고선(선 위의 각 정점) + 표고점(점)을 합쳐 (x, y, height) 산점 배열로 만든다."""
    bbox_gdf = gpd.GeoDataFrame(geometry=[box(*bbox_wgs84)], crs="EPSG:4326")

    contours = gpd.read_file(CONTOUR_PATH)
    points = gpd.read_file(ELEV_POINT_PATH)

    contours_area = bbox_gdf.to_crs(contours.crs).geometry.iloc[0].buffer(buffer_m)
    points_area = bbox_gdf.to_crs(points.crs).geometry.iloc[0].buffer(buffer_m)

    contours_clip = gpd.clip(contours, contours_area).to_crs(target_crs)
    points_clip = gpd.clip(points, points_area).to_crs(target_crs)

    xs, ys, hs = [], [], []
    for geom, h in zip(contours_clip.geometry, contours_clip["HEIGHT"]):
        # bbox 경계에서 잘려 MultiLineString이 된 등고선도 있으므로 조각별로 순회한다.
        lines = geom.geoms if geom.geom_type.startswith("Multi") else [geom]
        for line in lines:
            for x, y in line.coords:
                xs.append(x)
                ys.append(y)
                hs.append(h)
    for geom, h in zip(points_clip.geometry, points_clip["HEIGHT"]):
        xs.append(geom.x)
        ys.append(geom.y)
        hs.append(h)

    return np.array(xs), np.array(ys), np.array(hs)


def estimate_node_elevations(G_proj, xs, ys, hs):
    """그래프 각 노드 위치의 높이를 주변 산점 데이터로 보간해 추정한다."""
    node_ids = list(G_proj.nodes)
    node_x = np.array([G_proj.nodes[n]["x"] for n in node_ids])
    node_y = np.array([G_proj.nodes[n]["y"] for n in node_ids])

    elev = griddata((xs, ys), hs, (node_x, node_y), method="linear")
    missing = np.isnan(elev)  # 산점 데이터 볼록껍질 바깥 노드는 선형보간이 안 됨 -> 최근접값으로 채움
    if missing.any():
        elev[missing] = griddata((xs, ys), hs, (node_x[missing], node_y[missing]), method="nearest")

    return dict(zip(node_ids, elev))


def add_slope_to_edges(G, node_elev):
    """엣지 양 끝 노드의 높이차 / 엣지 길이로 경사도(%)를 계산해 속성으로 붙인다."""
    for u, v, data in G.edges(data=True):
        h_u, h_v = node_elev[u], node_elev[v]
        length = data.get("length") or 1e-6
        data["elevation_start_m"] = round(float(h_u), 2)
        data["elevation_end_m"] = round(float(h_v), 2)
        data["slope_pct"] = round(float(abs(h_v - h_u) / length * 100), 2)
    return G


def main():
    print("2단계 그래프 불러오는 중...")
    G = ox.load_graphml(snap.GRAPH_PATH)
    G_proj = ox.project_graph(G)
    print(f"그래프: 노드 {len(G.nodes):,}개, 엣지 {len(G.edges):,}개")

    print("\n경사도 원본 데이터(등고선+표고점) 불러오는 중...")
    xs, ys, hs = load_elevation_samples(infra_collect.TARGET_BBOX, G_proj.graph["crs"])
    print(f"높이 산점 데이터: {len(xs):,}개")

    print("\n노드별 높이 추정 중...")
    node_elev = estimate_node_elevations(G_proj, xs, ys, hs)

    print("\n엣지 경사도 계산 중...")
    G_scored = add_slope_to_edges(G, node_elev)

    ox.save_graphml(G_scored, GRAPH_WITH_SLOPE_PATH)
    print(f"저장: {GRAPH_WITH_SLOPE_PATH}")

    slopes = np.array([d["slope_pct"] for _, _, d in G_scored.edges(data=True)])
    print(
        f"\n경사도(%) 요약 - 평균: {slopes.mean():.1f}, 중앙값: {np.median(slopes):.1f}, "
        f"최대: {slopes.max():.1f}, 10% 초과 엣지 수: {(slopes > 10).sum()}"
    )


if __name__ == "__main__":
    main()
