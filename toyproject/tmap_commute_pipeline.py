"""TMAP 보행경로를 OSM 엣지 분석에 연결하는 통학로 검증 파이프라인.

TMAP 원본 경로는 약관상 24시간 이상 저장하지 않는다. 이 모듈은 기본적으로 응답을
메모리에서만 처리하며, 영구 산출물은 출발지·문 정의와 OSM 엣지 분석 코드이다.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import osmnx as ox
from dotenv import load_dotenv
from shapely.geometry import LineString, Point

import chungang_config
import soongsil_config


ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
PROJ = "EPSG:5186"
WGS84 = "EPSG:4326"
TMAP_URL = os.getenv("TMAP_PEDESTRIAN_URL", "https://apis.openapi.sk.com/tmap/routes/pedestrian")

SCHOOLS = {
    "숭실대": {
        "center": (soongsil_config.CENTER_LAT, soongsil_config.CENTER_LON),
        "gate_file": DATA_DIR / "soongsil_kakao_gates.csv",
        "network_file": DATA_DIR / "soongsil_network.gpkg",
    },
    "중앙대": {
        "center": (chungang_config.CENTER_LAT, chungang_config.CENTER_LON),
        "gate_file": DATA_DIR / "chungang_kakao_gates.csv",
        "network_file": DATA_DIR / "chungang_network.gpkg",
    },
}


def _kakao_key() -> str:
    load_dotenv(ROOT / ".env")
    key = os.getenv("KAKAO_REST_API_KEY")
    if not key:
        raise RuntimeError(".env에 KAKAO_REST_API_KEY가 필요합니다.")
    return key


def _tmap_key() -> str:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.tmap")
    key = os.getenv("TMAP_APP_KEY")
    if not key:
        raise RuntimeError(".env에 TMAP_APP_KEY를 추가한 뒤 다시 실행하세요.")
    return key


def kakao_keyword(query: str, lat: float, lon: float, radius_m: int = 800) -> list[dict]:
    """반경 내 Kakao 키워드 결과를 끝 페이지까지 가져온다."""
    headers = {"Authorization": f"KakaoAK {_kakao_key()}"}
    docs = []
    for page in range(1, 4):
        response = requests.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            headers=headers,
            params={"query": query, "x": lon, "y": lat, "radius": radius_m,
                    "size": 15, "page": page, "sort": "distance"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        docs.extend(payload.get("documents", []))
        if payload.get("meta", {}).get("is_end", True):
            break
    return docs


def kakao_category(code: str, lat: float, lon: float, radius_m: int = 800) -> list[dict]:
    headers = {"Authorization": f"KakaoAK {_kakao_key()}"}
    response = requests.get(
        "https://dapi.kakao.com/v2/local/search/category.json",
        headers=headers,
        params={"category_group_code": code, "x": lon, "y": lat, "radius": radius_m,
                "size": 15, "sort": "distance"}, timeout=20,
    )
    response.raise_for_status()
    return response.json().get("documents", [])


def collect_origin_candidates(save: bool = True) -> pd.DataFrame:
    """각 학교 800m 안의 지하철 출구·OSM 버스정류장을 초기 출발지로 수집한다."""
    rows = []
    for school, spec in SCHOOLS.items():
        lat, lon = spec["center"]
        # Kakao는 역 대표점은 안정적이나 개별 출구 POI가 불완전해 OSM subway_entrance를 쓴다.
        subway = ox.features_from_point((lat, lon), tags={"railway": "subway_entrance"}, dist=800)
        if len(subway):
            station_docs = kakao_category("SW8", lat, lon)
            station_points = gpd.GeoSeries(
                [Point(float(d["x"]), float(d["y"])) for d in station_docs], crs=WGS84,
            ).to_crs(PROJ) if station_docs else gpd.GeoSeries([], crs=PROJ)
            subway = subway.to_crs(PROJ)
            center = gpd.GeoSeries([Point(lon, lat)], crs=WGS84).to_crs(PROJ).iloc[0]
            subway = subway[subway.geometry.distance(center) <= 800].to_crs(WGS84)
            for idx, feature in subway.iterrows():
                point = feature.geometry if feature.geometry.geom_type == "Point" else feature.geometry.centroid
                exit_ref = feature.get("ref") if pd.notna(feature.get("ref")) else "번호 미상"
                point_proj = gpd.GeoSeries([point], crs=WGS84).to_crs(PROJ).iloc[0]
                if len(station_points):
                    station_name = station_docs[int(np.argmin([point_proj.distance(p) for p in station_points]))]["place_name"].split(" ")[0]
                else:
                    station_name = feature.get("name") if pd.notna(feature.get("name")) else "지하철역"
                rows.append({"학교": school, "출발지유형": "지하철출구",
                             "출발지명": f"{station_name} {exit_ref}번 출구",
                             "lat": point.y, "lon": point.x,
                             "중심점거리_m": round(point_proj.distance(center), 1),
                             "source": "OSM", "source_id": f"{idx[0]}/{idx[-1]}", "주소": ""})
        # Kakao 키워드 검색은 일반명 '버스정류장'을 반환하지 않아 OSM 정류장 점을 보완한다.
        bus = ox.features_from_point((lat, lon), tags={"highway": "bus_stop"}, dist=800)
        if len(bus):
            bus = bus.to_crs(PROJ)
            center = gpd.GeoSeries([Point(lon, lat)], crs=WGS84).to_crs(PROJ).iloc[0]
            bus = bus[bus.geometry.distance(center) <= 800].to_crs(WGS84)
            for idx, feature in bus.iterrows():
                point = feature.geometry if feature.geometry.geom_type == "Point" else feature.geometry.centroid
                rows.append({
                    "학교": school, "출발지유형": "버스정류장",
                    "출발지명": feature.get("name") if pd.notna(feature.get("name")) else f"OSM 버스정류장 {idx[-1]}",
                    "lat": point.y, "lon": point.x,
                    "중심점거리_m": round(gpd.GeoSeries([point], crs=WGS84).to_crs(PROJ).iloc[0].distance(center), 1),
                    "source": "OSM", "source_id": f"{idx[0]}/{idx[-1]}", "주소": "",
                })
    result = pd.DataFrame(rows)
    if len(result):
        result = (result.sort_values(["학교", "출발지유형", "중심점거리_m"])
                  .drop_duplicates(["학교", "source", "source_id"]).reset_index(drop=True))
    if save:
        result.to_csv(DATA_DIR / "commute_origin_candidates.csv", index=False, encoding="utf-8-sig")
    return result


def load_gates() -> pd.DataFrame:
    rows = []
    for school, spec in SCHOOLS.items():
        frame = pd.read_csv(spec["gate_file"])
        frame.insert(0, "학교", school)
        rows.append(frame[["학교", "문", "lat", "lon"]])
    return pd.concat(rows, ignore_index=True)


def request_pedestrian_route(origin: pd.Series, gate: pd.Series) -> dict:
    """출발지 하나와 문 하나 사이의 TMAP 보행경로를 메모리에서 반환한다."""
    payload = {
        "startX": str(origin["lon"]), "startY": str(origin["lat"]),
        "endX": str(gate["lon"]), "endY": str(gate["lat"]),
        "startName": str(origin["출발지명"]), "endName": f"{gate['학교']} {gate['문']}",
        "reqCoordType": "WGS84GEO", "resCoordType": "WGS84GEO",
    }
    response = requests.post(
        TMAP_URL, params={"version": 1, "format": "json"},
        headers={"appKey": _tmap_key(), "Content-Type": "application/x-www-form-urlencoded"},
        data=payload, timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    features = data.get("features", [])
    lines = [f["geometry"]["coordinates"] for f in features if f.get("geometry", {}).get("type") == "LineString"]
    if not lines:
        raise ValueError("TMAP 응답에 보행 경로 LineString이 없습니다.")
    coordinates = [tuple(xy) for part in lines for xy in part]
    properties = features[0].get("properties", {}) if features else {}
    return {
        "학교": gate["학교"], "origin_id": f"{origin['source']}:{origin['source_id']}",
        "출발지명": origin["출발지명"], "출발지유형": origin["출발지유형"],
        "문": gate["문"], "distance_m": properties.get("totalDistance"),
        "time_s": properties.get("totalTime"), "geometry": LineString(coordinates),
        "queried_at": datetime.now(timezone.utc),
    }


def run_all_routes(origins: pd.DataFrame | None = None) -> gpd.GeoDataFrame:
    """각 출발지에서 같은 학교의 모든 문으로 요청한다. 원본은 저장하지 않는다."""
    origins = collect_origin_candidates() if origins is None else origins.copy()
    gates = load_gates()
    rows = []
    for _, origin in origins.iterrows():
        for _, gate in gates[gates["학교"].eq(origin["학교"])].iterrows():
            try:
                rows.append(request_pedestrian_route(origin, gate))
            except Exception as exc:
                rows.append({"학교": origin["학교"], "출발지명": origin["출발지명"],
                             "origin_id": f"{origin['source']}:{origin['source_id']}",
                             "출발지유형": origin["출발지유형"], "문": gate["문"],
                             "distance_m": np.nan, "time_s": np.nan, "geometry": None,
                             "queried_at": datetime.now(timezone.utc), "오류": str(exc)})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=WGS84)


def choose_nearest_gate(routes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """출발지별 성공한 경로 중 TMAP 보행거리 최솟값을 통학로로 채택한다."""
    ok = routes.dropna(subset=["geometry", "distance_m"]).copy()
    idx = ok.groupby(["학교", "origin_id"])["distance_m"].idxmin()
    chosen = ok.loc[idx].copy().reset_index(drop=True)
    chosen["expires_at"] = chosen["queried_at"] + timedelta(hours=24)
    return chosen


def _sample_line(line: LineString, spacing_m: float = 10) -> list[Point]:
    length = line.length
    return [line.interpolate(d) for d in np.arange(0, length + spacing_m, spacing_m)]


def match_routes_to_osm(chosen: gpd.GeoDataFrame, max_distance_m: float = 20) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """TMAP 경로를 10m 간격으로 표본화해 가장 가까운 OSM 엣지에 매칭한다."""
    matched, summary = [], []
    for school, group in chosen.groupby("학교"):
        edges = gpd.read_file(SCHOOLS[school]["network_file"], layer="edges").to_crs(PROJ).reset_index(names="edge_row")
        routes = group.to_crs(PROJ)
        for route_idx, route in routes.iterrows():
            sampled = _sample_line(route.geometry)
            points = gpd.GeoDataFrame(
                {"route_idx": [route_idx] * len(sampled), "sample_id": range(len(sampled))},
                geometry=sampled, crs=PROJ,
            )
            joined = gpd.sjoin_nearest(points, edges[["edge_row", "geometry"]], how="left", distance_col="match_distance_m")
            valid = joined[joined["match_distance_m"] <= max_distance_m]
            matched_point_count = valid["sample_id"].nunique()
            edge_rows = valid["edge_row"].dropna().astype(int).drop_duplicates()
            hit = edges.loc[edge_rows].copy()
            hit["학교"] = school; hit["origin_id"] = route["origin_id"]
            hit["출발지명"] = route["출발지명"]; hit["문"] = route["문"]
            matched.append(hit)
            summary.append({"학교": school, "origin_id": route["origin_id"], "출발지명": route["출발지명"], "문": route["문"],
                            "TMAP거리_m": route["distance_m"], "표본점수": len(points),
                            "20m이내매칭점수": matched_point_count,
                            "매칭률_pct": round(matched_point_count / len(points) * 100, 1),
                            "매칭OSM엣지수": len(edge_rows)})
    matched_gdf = gpd.GeoDataFrame(pd.concat(matched, ignore_index=True), crs=PROJ) if matched else gpd.GeoDataFrame(crs=PROJ)
    return matched_gdf, pd.DataFrame(summary)
