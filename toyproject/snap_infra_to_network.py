"""
2단계: 보행자 도로망 그래프화 + 인프라 스냅
==========================================
목적
----
1단계에서 모은 인프라(병원, 카페 등) 좌표를 실제 보행자 도로망 그래프에 붙인다.
(자세한 설명은 step2_도로망_스냅_설명.md 참고)

이 스크립트는 두 가지 일을 한다.
1. osmnx로 대상 bbox(정문 반경 1km, collect_infra_places.TARGET_BBOX와 동일)의
   보행자 도로망을 받아 그래프로 만든다.
2. kakao_places_infra.jsonl의 각 인프라 좌표를 그래프에서 가장 가까운 노드에
   스냅하고, 원래 좌표-노드 사이 거리(스냅 거리, m)를 같이 기록한다.

사용법
------
python snap_infra_to_network.py
결과:
- data/pedestrian_graph.graphml  (도로망 그래프)
- data/infra_snapped.csv         (인프라 + 스냅된 노드 id + 스냅 거리)
"""

import json
from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd

import collect_infra_places as infra_collect

DATA_DIR = Path(__file__).parent / "data"
GRAPH_PATH = DATA_DIR / "pedestrian_graph.graphml"
SNAPPED_PATH = DATA_DIR / "infra_snapped.csv"

NETWORK_TYPE = "walk"


def fetch_graph(bbox=infra_collect.TARGET_BBOX, network_type=NETWORK_TYPE):
    """대상 bbox의 보행자 도로망을 osmnx(Overpass API)로 받아 그래프로 만든다."""
    ox.settings.timeout = 120
    return ox.graph_from_bbox(bbox, network_type=network_type)


def load_infra(path=infra_collect.OUT_PATH):
    """1단계 산출물(jsonl)을 읽어 id 기준 중복을 제거한 DataFrame으로 돌려준다."""
    records = [json.loads(line) for line in open(path, encoding="utf-8")]
    df = pd.DataFrame(records).drop_duplicates(subset="id")
    df["x"] = df["x"].astype(float)  # 경도
    df["y"] = df["y"].astype(float)  # 위도
    return df


def snap_infra(df, G):
    """각 인프라 좌표를 그래프에서 가장 가까운 노드에 스냅한다.
    거리를 정확히(미터 단위로) 재기 위해 그래프와 좌표를 먼저 투영(project)한다."""
    G_proj = ox.project_graph(G)
    gdf_points = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["x"], df["y"]), crs="EPSG:4326"
    ).to_crs(G_proj.graph["crs"])

    nearest, dist = ox.distance.nearest_nodes(
        G_proj, X=gdf_points.geometry.x, Y=gdf_points.geometry.y, return_dist=True
    )
    df = df.copy()
    df["snapped_node_id"] = nearest
    df["snap_distance_m"] = dist
    return df


def main():
    DATA_DIR.mkdir(exist_ok=True)

    print("보행자 도로망 그래프를 받는 중...")
    G = fetch_graph()
    print(f"그래프: 노드 {len(G.nodes):,}개, 엣지 {len(G.edges):,}개")
    ox.save_graphml(G, GRAPH_PATH)
    print(f"저장: {GRAPH_PATH}")

    print("\n인프라 불러오는 중...")
    df = load_infra()
    print(f"인프라: {len(df):,}건")

    print("\n인프라를 도로망 노드에 스냅하는 중...")
    df_snapped = snap_infra(df, G)
    df_snapped.to_csv(SNAPPED_PATH, index=False, encoding="utf-8-sig")
    print(f"저장: {SNAPPED_PATH}")

    print(
        f"\n스냅 거리 평균: {df_snapped['snap_distance_m'].mean():.1f}m, "
        f"최대: {df_snapped['snap_distance_m'].max():.1f}m"
    )


if __name__ == "__main__":
    main()
