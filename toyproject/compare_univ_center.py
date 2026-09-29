"""
숭실대 기준점 후보 비교 (1단계: 대학가 규정)
=============================================
팀 합의: "지도에서 학교를 검색하면 나오는 지점"을 중심으로 반경 800m.
그런데 카카오는 '숭실대학교'(캠퍼스 대표점)와 '숭실대학교 정문'을 서로 다른 POI로
돌려주므로, 후보 지점들의 좌표와 서로의 거리를 표로 만든다.

- 카카오: 키워드 검색 (KAKAO_REST_API_KEY 필요, .env)
- OSM: Overpass로 숭실대 출입구(entrance) 노드 (정문/북문/중문/남문)
- 네이버: 미포함 (공식 검색 API 키 발급 후 추가 예정)

결과: data/soongsil_center_candidates.csv
"""

import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from dotenv import load_dotenv
from shapely.geometry import Point

load_dotenv(Path(__file__).parent / ".env")

DATA_DIR = Path(__file__).parent / "data"
OUT_PATH = DATA_DIR / "soongsil_center_candidates.csv"
PROJ_CRS = "EPSG:5186"  # 중부원점 TM (미터 단위 거리 계산용)

KAKAO_QUERIES = {
    "KAKAO 대표점": "숭실대학교",
    "KAKAO 정문": "숭실대학교 정문",
    "KAKAO 후문": "숭실대학교 후문",
    "KAKAO 숭실대입구역": "숭실대입구역",
}
OSM_BBOX = (37.4935, 126.951, 37.499, 126.9605)  # (S, W, N, E)


def kakao_top(query):
    """키워드 검색 1순위 결과의 (장소명, lat, lon)."""
    headers = {"Authorization": f"KakaoAK {os.environ['KAKAO_REST_API_KEY']}"}
    r = requests.get(
        "https://dapi.kakao.com/v2/local/search/keyword.json",
        headers=headers, params={"query": query, "size": 1}, timeout=15,
    )
    r.raise_for_status()
    d = r.json()["documents"][0]
    return d["place_name"], float(d["y"]), float(d["x"])


def osm_entrances():
    """숭실대 출입구 노드: {이름: (lat, lon)}."""
    s, w, n, e = OSM_BBOX
    q = f'[out:json][timeout:60];node["entrance"]["name"~"숭실대"]({s},{w},{n},{e});out;'
    r = requests.post(
        "https://overpass-api.de/api/interpreter", data={"data": q},
        headers={"User-Agent": "dartb-accessibility-study/0.1"}, timeout=90,
    )
    r.raise_for_status()
    return {f"OSM {el['tags']['name'].replace('숭실대학교 ', '')}": (el["lat"], el["lon"])
            for el in r.json()["elements"]}


def main():
    rows = []
    for label, query in KAKAO_QUERIES.items():
        name, lat, lon = kakao_top(query)
        rows.append({"후보": label, "장소명": name, "lat": lat, "lon": lon})
    for label, (lat, lon) in osm_entrances().items():
        rows.append({"후보": label, "장소명": label, "lat": lat, "lon": lon})
    df = pd.DataFrame(rows)

    pts = gpd.GeoSeries([Point(lo, la) for la, lo in zip(df["lat"], df["lon"])], crs="EPSG:4326").to_crs(PROJ_CRS)
    ref = pts[df.index[df["후보"] == "OSM 정문"][0]]
    df["OSM정문과의거리_m"] = [round(p.distance(ref)) for p in pts]

    # 반경 800m 원끼리 겹치는 비율(IoU): 기준점 선택이 분석 영역을 얼마나 바꾸는지
    base = ref.buffer(800)
    df["OSM정문_원과_IoU"] = [round(p.buffer(800).intersection(base).area / p.buffer(800).union(base).area, 3) for p in pts]

    DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(df.to_string(index=False))
    print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
