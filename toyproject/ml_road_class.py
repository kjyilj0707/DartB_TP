"""서울 교차로에 OSM 도로 등급을 붙인다 (트리모델.ipynb 10절: '차도 제외' 검증용).

팀원 의견: "경사가 가파를수록 사고다발지 확률이 낮게 나오는 것은, 사고가 주로 나는 차도가 평평해서일 수 있다."
이를 확인하려고 교차로 중심 반경 R m 안에 있는 OSM 도로 중 가장 높은 등급을 붙인다.

등급(OSM highway 값)
  1 간선   : motorway, trunk, primary, secondary (+ _link)
  2 보조간선: tertiary (+ _link)
  3 그 밖  : 위 등급이 반경 안에 없음(residential, service, unclassified 등이거나 자료에 없음)
residential 이하는 서울 전체를 받으면 자료가 너무 커서 받지 않았다. 그래서 '3 그 밖'은 "간선·보조간선이 근처에 없다"는 뜻이다.
"""
import json
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from shapely.geometry import LineString
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "tree_model"
ROADS_PATH = OUT_DIR / "osm_roads_major_seoul.gpkg"
PROJ = "EPSG:5186"
OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "DartB-TOYPROJECT-research/1.0 (student project; road class of Seoul intersections)"

MAJOR = {"motorway", "trunk", "primary", "secondary"}
MINOR = {"tertiary"}
HIGHWAY_RE = "^(motorway|trunk|primary|secondary|tertiary)(_link)?$"
LEVEL_LABEL = {1: "간선", 2: "보조간선", 3: "그 밖"}


def _tiles(bounds_ll, n=3):
    s, w, nn, e = bounds_ll
    lat = np.linspace(s, nn, n + 1)
    lon = np.linspace(w, e, n + 1)
    return [(lat[i], lon[j], lat[i + 1], lon[j + 1]) for i in range(n) for j in range(n)]


def fetch_roads(intersections_xy, margin_m=600, force=False):
    """교차로 좌표(EPSG:5186)를 덮는 영역의 간선·보조간선 도로를 Overpass에서 받아 gpkg로 저장한다."""
    if ROADS_PATH.exists() and not force:
        return gpd.read_file(ROADS_PATH)
    x, y = intersections_xy[:, 0], intersections_xy[:, 1]
    to_ll = Transformer.from_crs(PROJ, "EPSG:4326", always_xy=True)
    w, s = to_ll.transform(x.min() - margin_m, y.min() - margin_m)
    e, n = to_ll.transform(x.max() + margin_m, y.max() + margin_m)
    rows = {}
    for k, (s0, w0, n0, e0) in enumerate(_tiles((s, w, n, e))):
        q = f'[out:json][timeout:240];way["highway"~"{HIGHWAY_RE}"]({s0:.5f},{w0:.5f},{n0:.5f},{e0:.5f});out tags geom;'
        for attempt in range(4):
            r = requests.post(OVERPASS, data={"data": q}, headers={"User-Agent": UA}, timeout=300)
            if r.status_code == 200:
                break
            time.sleep(15 * (attempt + 1))
        r.raise_for_status()
        for el in r.json()["elements"]:
            if el.get("type") != "way" or "geometry" not in el:
                continue
            rows[el["id"]] = {"osm_id": el["id"], "highway": el["tags"]["highway"], "name": el["tags"].get("name", ""),
                              "geometry": LineString([(p["lon"], p["lat"]) for p in el["geometry"]])}
        print(f"tile {k + 1}/9 ok, ways so far {len(rows):,}")
        time.sleep(3)
    gdf = gpd.GeoDataFrame(list(rows.values()), geometry="geometry", crs="EPSG:4326").to_crs(PROJ)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gdf.to_file(ROADS_PATH, driver="GPKG")
    return gdf


def add_road_class(g, roads, radii=(20, 30, 50)):
    """교차로 표(g, x·y는 EPSG:5186)에 반경별 최고 도로 등급('도로등급_{R}m', 1~3)과 최근접 간선 거리를 붙인다."""
    base = roads["highway"].str.replace("_link", "", regex=False)
    level = np.where(base.isin(MAJOR), 1, np.where(base.isin(MINOR), 2, 3))
    geoms = roads.geometry.to_numpy()
    pts = gpd.points_from_xy(g["x"], g["y"])
    out = {}
    for lv in (1, 2):
        tree = STRtree(geoms[level == lv])
        for R in radii:
            idx_pt, _ = tree.query(pts, predicate="dwithin", distance=R)
            hit = np.zeros(len(g), bool)
            hit[np.unique(idx_pt)] = True
            out[(lv, R)] = hit
        # 최근접 거리
        nearest = tree.query_nearest(pts, all_matches=False, return_distance=True)
        d = np.full(len(g), np.nan)
        d[nearest[0][0]] = nearest[1]
        g[f"최근접{LEVEL_LABEL[lv]}_m"] = d
    for R in radii:
        g[f"도로등급_{R}m"] = np.where(out[(1, R)], 1, np.where(out[(2, R)], 2, 3))
    return g


def label_accident_road_class(acc_xy, roads, radius=30):
    """사고다발지 좌표(EPSG:5186 Nx2) 각각의 최고 도로 등급."""
    tmp = pd.DataFrame({"x": acc_xy[:, 0], "y": acc_xy[:, 1]})
    tmp = add_road_class(tmp, roads, radii=(radius,))
    return tmp[f"도로등급_{radius}m"].to_numpy()
