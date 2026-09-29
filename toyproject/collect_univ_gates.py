"""서울 전체 대학·출입문 수집 (카카오 로컬 API)

H7(서울 대학 전체, 같은 학교 안 출입문별 음향신호기 설치개수 격차) 검증을 위한 선행 데이터 수집.

1단계: 키워드검색 "대학교"를 서울 bbox 전역에 격자탐색으로 수집하고, 카테고리가
       "교육,학문 > 학교 > 대학교"인 것만 남긴다 (부속기관·대학병원 등 걸러내기 위함).
2단계: 각 대학마다 "<학교명> <문종류>" 키워드로 출입구(교통,수송 > 입출구) 카테고리
       결과를 찾는다. 문종류는 정문/후문/동문/서문/남문/북문/중문 7가지를 시도한다.

collect_infra_places.py와 같은 재귀 4분할 + 재시작 패턴을 쓰되, category search가
아니라 keyword search를 쓴다는 점이 다르다.

사용법
------
1. .env에 KAKAO_REST_API_KEY 필요 (.env.example 참고, 이미 있음).
2. python collect_univ_gates.py
3. 결과: data/h7/seoul_universities.csv, data/h7/seoul_univ_gates.csv
"""

import json
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
import os

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

DATA_DIR = PROJECT_DIR / "data" / "h7"
UNIV_OUT = DATA_DIR / "seoul_universities.csv"
GATE_OUT = DATA_DIR / "seoul_univ_gates.csv"

API_URL_KEYWORD = "https://dapi.kakao.com/v2/local/search/keyword.json"
REQUEST_DELAY_SEC = 0.15
MAX_RETRIES = 5

# 서울시 전체를 넉넉히 덮는 bbox (행정구역 경계보다 살짝 크게)
SEOUL_BBOX = (126.734, 37.413, 127.269, 37.715)  # (min_lon, min_lat, max_lon, max_lat)
INITIAL_STEP_DEG = 0.02  # 약 2km. "대학교"는 밀집도가 낮아 crosswalk 수집보다 크게 잡음
MIN_RECT_SIZE_DEG = 0.003  # 약 300m까지만 쪼갬

GATE_TYPES = ["정문", "후문", "동문", "서문", "남문", "북문", "중문"]


def initial_grid(bbox, step_deg):
    min_lon, min_lat, max_lon, max_lat = bbox
    lon = min_lon
    cells = []
    while lon < max_lon:
        lat = min_lat
        next_lon = min(lon + step_deg, max_lon)
        while lat < max_lat:
            next_lat = min(lat + step_deg, max_lat)
            cells.append((lon, lat, next_lon, next_lat))
            lat = next_lat
        lon = next_lon
    return cells


def split_rect(rect):
    min_lon, min_lat, max_lon, max_lat = rect
    mid_lon = (min_lon + max_lon) / 2
    mid_lat = (min_lat + max_lat) / 2
    return [
        (min_lon, min_lat, mid_lon, mid_lat),
        (mid_lon, min_lat, max_lon, mid_lat),
        (min_lon, mid_lat, mid_lon, max_lat),
        (mid_lon, mid_lat, max_lon, max_lat),
    ]


def rect_is_too_small(rect, min_size=MIN_RECT_SIZE_DEG):
    min_lon, min_lat, max_lon, max_lat = rect
    return (max_lon - min_lon) < min_size or (max_lat - min_lat) < min_size


def _request(session, headers, params):
    for attempt in range(MAX_RETRIES):
        resp = session.get(API_URL_KEYWORD, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            time.sleep(1.5 * (attempt + 1))
            continue
        resp.raise_for_status()
    raise RuntimeError(f"카카오 API 재시도 초과: {params}")


def keyword_search_rect(session, headers, query, rect):
    """rect 안에서 query로 키워드검색, 최대 45건까지."""
    docs, page = [], 1
    while page <= 3:
        params = {"query": query, "rect": ",".join(f"{v:.6f}" for v in rect), "page": page, "size": 15}
        d = _request(session, headers, params)
        time.sleep(REQUEST_DELAY_SEC)
        docs.extend(d["documents"])
        if d["meta"]["is_end"]:
            break
        page += 1
    truncated = d["meta"]["pageable_count"] >= 45
    return docs, truncated


def collect_universities_in_rect(session, headers, rect, seen_ids, out_rows, stats):
    docs, truncated = keyword_search_rect(session, headers, "대학교", rect)

    if truncated and not rect_is_too_small(rect):
        for sub in split_rect(rect):
            collect_universities_in_rect(session, headers, sub, seen_ids, out_rows, stats)
        return

    for d in docs:
        if d.get("category_group_code") != "SC4":
            continue
        if "대학교" not in d.get("category_name", ""):
            continue
        if d["id"] in seen_ids:
            continue
        seen_ids.add(d["id"])
        out_rows.append({
            "id": d["id"], "place_name": d["place_name"], "category_name": d["category_name"],
            "address_name": d.get("address_name"), "lat": float(d["y"]), "lon": float(d["x"]),
        })
    stats["leaf_calls"] += 1


def collect_universities():
    api_key = os.environ.get("KAKAO_REST_API_KEY")
    if not api_key:
        raise SystemExit("KAKAO_REST_API_KEY가 없습니다. .env를 확인하세요.")
    headers = {"Authorization": f"KakaoAK {api_key}"}
    session = requests.Session()

    grid = initial_grid(SEOUL_BBOX, INITIAL_STEP_DEG)
    print(f"격자 셀 수: {len(grid)}")

    seen_ids, out_rows = set(), []
    stats = {"leaf_calls": 0}
    for i, cell in enumerate(grid):
        collect_universities_in_rect(session, headers, cell, seen_ids, out_rows, stats)
        if (i + 1) % 50 == 0:
            print(f"  격자 {i + 1}/{len(grid)}, 누적 대학 {len(out_rows)}개")

    df = pd.DataFrame(out_rows).sort_values("place_name").reset_index(drop=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(UNIV_OUT, index=False, encoding="utf-8-sig")
    print(f"\n대학 {len(df)}개 수집 (API 호출 {stats['leaf_calls']}회). 저장: {UNIV_OUT}")
    return df


import math
import re


def core_name(name):
    """'건국대학교 서울캠퍼스' -> '건국대학교'. 실제 출입구 POI는 캠퍼스 접미사 없이
    등록된 경우가 많아서(§H7 디버깅에서 확인: '경희대학교 정문', '연세대학교 정문' 등),
    이 핵심명으로도 같이 검색해야 놓치지 않는다."""
    return re.sub(r"\s+\S*(캠퍼스|교정)$", "", name)


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


GATE_DIST_MAX_M = 2000      # 학교 이름이 place_name에 들어있을 때 허용하는 최대 거리
GATE_DIST_MAX_NONAME_M = 400  # 이름이 안 들어있을 때(축약형 등)는 훨씬 가까워야 인정


def collect_gates(univ_df):
    api_key = os.environ.get("KAKAO_REST_API_KEY")
    headers = {"Authorization": f"KakaoAK {api_key}"}
    session = requests.Session()

    # 다른 대학 이름이 place_name에 섞여 들어오는 오탐(예: 한국외대 검색에 "경희대학교 남문"이
    # 걸리는 것)을 막기 위해, 전체 대학 핵심명 목록을 미리 만들어 둔다.
    all_core_names = {core_name(n): n for n in univ_df["place_name"]}

    rows = []
    for i, u in univ_df.iterrows():
        name = u["place_name"]
        core = core_name(name)
        queries = {name, core}
        seen_latlon = set()
        for q in queries:
            for gate in GATE_TYPES:
                params = {"query": f"{q} {gate}", "size": 5}
                d = _request(session, headers, params)
                time.sleep(REQUEST_DELAY_SEC)
                for doc in d["documents"]:
                    place = doc["place_name"]
                    if gate not in place:
                        continue
                    if not doc.get("category_name", "").startswith("교통,수송 > 입출구"):
                        continue

                    other_hit = next((c for c, full in all_core_names.items()
                                       if c != core and c in place), None)
                    if other_hit:
                        continue  # 다른 대학 이름이 들어있음 -> 그 학교 문, 여기선 버림

                    lat, lon = float(doc["y"]), float(doc["x"])
                    dist = haversine_m(u["lat"], u["lon"], lat, lon)
                    name_matches = core in place
                    limit = GATE_DIST_MAX_M if name_matches else GATE_DIST_MAX_NONAME_M
                    if dist > limit:
                        continue

                    key = (round(lat, 5), round(lon, 5))
                    if key in seen_latlon:
                        continue  # 원본명/핵심명 쿼리에서 같은 문이 중복으로 잡히는 것 방지
                    seen_latlon.add(key)
                    rows.append({
                        "univ_id": u["id"], "univ_name": name, "gate_type": gate,
                        "place_name": place, "lat": lat, "lon": lon,
                        "대학대표점_거리_m": round(dist, 1), "이름매칭": name_matches,
                    })
        if (i + 1) % 10 == 0:
            print(f"  대학 {i + 1}/{len(univ_df)}, 누적 출입문 {len(rows)}개")

    df = pd.DataFrame(rows)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(KAKAO_GATE_CACHE, index=False, encoding="utf-8-sig")
    print(f"\n출입문 {len(df)}개 수집. 저장: {KAKAO_GATE_CACHE}")
    return df


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_CACHE = DATA_DIR / "osm_seoul_named_entrances.json"
KAKAO_GATE_CACHE = DATA_DIR / "seoul_univ_gates_kakao.csv"
DEDUP_M = 50  # 카카오 문과 이 거리 안이면 같은 문으로 보고 OSM 쪽을 버림


def fetch_seoul_osm_entrances(refresh=False):
    """서울 bbox 안의 이름 있는 entrance 노드를 한 번에 받아 캐시한다.
    대학마다 따로 요청하면(64회) 공용 서버가 자주 멈춰서, 한 번에 받고 매칭은 로컬에서 한다."""
    if OSM_CACHE.exists() and not refresh:
        return json.loads(OSM_CACHE.read_text(encoding="utf-8"))
    min_lon, min_lat, max_lon, max_lat = SEOUL_BBOX
    q = (f'[out:json][timeout:180];'
         f'node["entrance"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});out;')
    r = requests.post(OVERPASS_URL, data={"data": q},
                       headers={"User-Agent": "dartb-accessibility-study/0.1"}, timeout=240)
    r.raise_for_status()
    elements = r.json()["elements"]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OSM_CACHE.write_text(json.dumps(elements, ensure_ascii=False), encoding="utf-8")
    return elements


def guess_gate_type(osm_name):
    for g in GATE_TYPES:
        if g in osm_name:
            return g
    return "기타"


def augment_with_osm(univ_df, kakao_gates_df):
    """OSM 이름 있는 entrance로 카카오 결과를 보강한다. 매칭 규칙은 collect_gates()와 같다:
    다른 대학 이름이 들어있으면 제외, 학교 핵심명이 들어있으면 2km, 아니면 문 키워드 + 400m."""
    elements = fetch_seoul_osm_entrances()
    print(f"OSM 서울 이름 있는 entrance 노드: {len(elements)}개")

    all_core_names = {core_name(n) for n in univ_df["place_name"]}
    rows = []
    for _, u in univ_df.iterrows():
        name = u["place_name"]
        core = core_name(name)
        existing = kakao_gates_df[kakao_gates_df["univ_name"] == name]
        for el in elements:
            osm_name = el.get("tags", {}).get("name", "")
            if any(c != core and c in osm_name for c in all_core_names):
                continue
            name_matches = core in osm_name
            if not name_matches and not any(g in osm_name for g in GATE_TYPES):
                continue
            lat, lon = el["lat"], el["lon"]
            dist = haversine_m(u["lat"], u["lon"], lat, lon)
            if dist > (GATE_DIST_MAX_M if name_matches else GATE_DIST_MAX_NONAME_M):
                continue
            if any(haversine_m(lat, lon, ex["lat"], ex["lon"]) <= DEDUP_M for _, ex in existing.iterrows()):
                continue
            rows.append({
                "univ_id": u["id"], "univ_name": name, "gate_type": guess_gate_type(osm_name),
                "place_name": osm_name, "lat": lat, "lon": lon,
                "대학대표점_거리_m": round(dist, 1), "이름매칭": name_matches, "출처": "OSM",
            })

    osm_df = pd.DataFrame(rows)
    kakao = kakao_gates_df.copy()
    kakao["출처"] = "Kakao"
    merged = pd.concat([kakao, osm_df], ignore_index=True)
    merged.to_csv(GATE_OUT, index=False, encoding="utf-8-sig")
    print(f"OSM으로 {len(osm_df)}개 추가. 합계 {len(merged)}개. 저장: {GATE_OUT}")
    return merged


def main():
    if UNIV_OUT.exists():
        print(f"이미 있음, 재사용: {UNIV_OUT}")
        univ_df = pd.read_csv(UNIV_OUT)
    else:
        univ_df = collect_universities()

    print(f"\n출입문 수집 시작 ({len(univ_df)}개 대학 x {len(GATE_TYPES)}개 문종류 = 최대 {len(univ_df)*len(GATE_TYPES)}회 호출)")
    collect_gates(univ_df)


if __name__ == "__main__":
    main()
