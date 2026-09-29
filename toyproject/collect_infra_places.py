"""
중앙대 정문·후문 반경 1km 인프라(상가·병원 등) 수집 (카카오 로컬 API)
========================================================
목적
----
시각장애인 보행 접근성 지도 프로젝트의 1단계: 보행 구간의 양 끝점이 될
인프라(상가, 병원, 약국, 편의점 등)의 이름·카테고리·좌표만 모은다.
(자세한 설명은 step1_인프라_수집_설명.md 참고)

MAP_Project/collect_kakao_places.py와 같은 방식(격자 + 45건 상한 시 4분할
재귀 호출 + 중단 후 이어받기)을 쓰되, 대상 지역과 카테고리를 이 프로젝트에
맞게 바꾼 독립 스크립트다.

사용법
------
1. .env 파일에 KAKAO_REST_API_KEY=<REST API 키> 를 넣는다. (.env.example 참고)
2. python collect_infra_places.py 실행
3. 결과는 data/kakao_places_infra.jsonl 에 한 줄당 장소 하나(JSON)로 쌓인다.
4. 중간에 멈춰도 다시 실행하면 이미 끝난 영역은 건너뛴다 (data/kakao_done_keys.txt).
"""

import json
import math
import os
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

# 중앙대 정문 (OSM 실측 좌표)
CENTER_LAT = 37.5070419
CENTER_LON = 126.9591522
RADIUS_M = 1000


def bbox_from_center(lat, lon, radius_m):
    """중심 좌표에서 반경 radius_m(미터)를 덮는 사각형을 만든다.
    (경도_min, 위도_min, 경도_max, 위도_max)를 돌려준다."""
    lat_delta = radius_m / 111_320  # 위도 1도 ≈ 111.32km, 위도에 따른 변화가 거의 없음
    lon_delta = radius_m / (111_320 * math.cos(math.radians(lat)))  # 경도는 위도에 따라 달라짐
    return (lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta)


TARGET_BBOX = bbox_from_center(CENTER_LAT, CENTER_LON, RADIUS_M)

# 카카오 카테고리 그룹 코드 — "보행 중 들르는 생활 인프라" 위주로 선정
# (MAP_Project는 데이트 장소 추정이 목적이라 음식점/카페/관광명소/숙박 위주였음. 이 프로젝트는 목적이 달라 재선정)
CATEGORY_GROUPS = {
    "HP8": "병원",
    "PM9": "약국",
    "CS2": "편의점",
    "MT1": "대형마트",
    "BK9": "은행",
    "SW8": "지하철역",
    "FD6": "음식점",
    "CE7": "카페",
}

# 이 정도로 쪼개지면 더 쪼개지 않고 45건까지만 취함 (밀집 상가 건물 등 예외 상황 방지)
MIN_RECT_SIZE_DEG = 0.0015  # 약 150m

DATA_DIR = Path(__file__).parent / "data"
OUT_PATH = DATA_DIR / "kakao_places_infra.jsonl"
DONE_KEYS_PATH = DATA_DIR / "kakao_done_keys_infra.txt"

API_URL = "https://dapi.kakao.com/v2/local/search/category.json"
REQUEST_DELAY_SEC = 0.15
MAX_RETRIES = 5


# ---------------------------------------------------------------------------
# 순수 함수 (네트워크 없이 테스트 가능)
# ---------------------------------------------------------------------------

def split_rect(rect):
    """사각형을 4등분한다. rect, 반환값 모두 (min_lon, min_lat, max_lon, max_lat)."""
    min_lon, min_lat, max_lon, max_lat = rect
    mid_lon = (min_lon + max_lon) / 2
    mid_lat = (min_lat + max_lat) / 2
    return [
        (min_lon, min_lat, mid_lon, mid_lat),
        (mid_lon, min_lat, max_lon, mid_lat),
        (min_lon, mid_lat, mid_lon, max_lat),
        (mid_lon, mid_lat, max_lon, max_lat),
    ]


def rect_key(category, rect):
    return f"{category}:" + ",".join(f"{v:.6f}" for v in rect)


def rect_is_too_small(rect, min_size=MIN_RECT_SIZE_DEG):
    min_lon, min_lat, max_lon, max_lat = rect
    return (max_lon - min_lon) < min_size or (max_lat - min_lat) < min_size


def initial_grid(bbox, step_deg=0.005):
    """탐색 시작점: bbox를 step_deg 크기의 격자로 미리 나눈다."""
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


# ---------------------------------------------------------------------------
# API 호출 (네트워크)
# ---------------------------------------------------------------------------

def fetch_page(session, headers, category, rect, page):
    params = {
        "category_group_code": category,
        "rect": ",".join(f"{v:.6f}" for v in rect),
        "page": page,
        "size": 15,
    }
    for attempt in range(MAX_RETRIES):
        resp = session.get(API_URL, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            time.sleep(1.5 * (attempt + 1))
            continue
        resp.raise_for_status()
    raise RuntimeError(f"카카오 API 재시도 초과: {category} {rect} page={page}")


def fetch_category_rect(session, headers, category, rect):
    """rect 안의 category 장소를 최대 45건까지 모두 가져온다."""
    first = fetch_page(session, headers, category, rect, page=1)
    time.sleep(REQUEST_DELAY_SEC)
    docs = list(first["documents"])
    pageable_count = first["meta"]["pageable_count"]

    page = 2
    while not first["meta"]["is_end"] and len(docs) < pageable_count and page <= 3:
        more = fetch_page(session, headers, category, rect, page=page)
        time.sleep(REQUEST_DELAY_SEC)
        docs.extend(more["documents"])
        if more["meta"]["is_end"]:
            break
        page += 1

    truncated = pageable_count >= 45  # 45건 상한에 걸렸을 가능성 -> 더 쪼개야 함
    return docs, truncated


# ---------------------------------------------------------------------------
# 수집 드라이버
# ---------------------------------------------------------------------------

def mark_done(category, rect, done_keys):
    key = rect_key(category, rect)
    done_keys.add(key)
    with open(DONE_KEYS_PATH, "a", encoding="utf-8") as f:
        f.write(key + "\n")


def collect(session, headers, category, rect, done_keys, out_f, stats):
    key = rect_key(category, rect)
    if key in done_keys:
        return

    docs, truncated = fetch_category_rect(session, headers, category, rect)

    if truncated and not rect_is_too_small(rect):
        for sub_rect in split_rect(rect):
            collect(session, headers, category, sub_rect, done_keys, out_f, stats)
        mark_done(category, rect, done_keys)
        return

    for d in docs:
        out_f.write(json.dumps(d, ensure_ascii=False) + "\n")
    stats["places"] += len(docs)
    stats["leaf_calls"] += 1
    if truncated:
        stats["truncated_at_min_size"] += 1

    mark_done(category, rect, done_keys)


def load_done_keys():
    if not DONE_KEYS_PATH.exists():
        return set()
    return set(DONE_KEYS_PATH.read_text(encoding="utf-8").splitlines())


def main():
    api_key = os.environ.get("KAKAO_REST_API_KEY")
    if not api_key:
        raise SystemExit(
            "KAKAO_REST_API_KEY가 설정되지 않았습니다. "
            "DartB_TOYPROJECT/.env 파일에 키를 넣어주세요 (.env.example 참고)."
        )

    DATA_DIR.mkdir(exist_ok=True)
    headers = {"Authorization": f"KakaoAK {api_key}"}
    session = requests.Session()
    done_keys = load_done_keys()
    stats = {"places": 0, "leaf_calls": 0, "truncated_at_min_size": 0}

    grid = initial_grid(TARGET_BBOX)
    print(f"대상 bbox: {TARGET_BBOX}")
    print(f"격자 셀 수: {len(grid)}, 카테고리 수: {len(CATEGORY_GROUPS)}")
    print(f"이미 완료된 영역: {len(done_keys)}개 (재실행 시 건너뜀)")

    with open(OUT_PATH, "a", encoding="utf-8") as out_f:
        for category in CATEGORY_GROUPS:
            print(f"\n[{category} - {CATEGORY_GROUPS[category]}] 수집 시작")
            for i, cell in enumerate(grid):
                collect(session, headers, category, cell, done_keys, out_f, stats)
                if (i + 1) % 5 == 0:
                    print(f"  격자 {i + 1}/{len(grid)} 완료, 누적 장소 {stats['places']:,}건")

    print(f"\n완료! 총 장소 {stats['places']:,}건 (leaf 호출 {stats['leaf_calls']:,}회, "
          f"최소 크기에서도 45건 이상이라 잘렸을 가능성 있는 영역 {stats['truncated_at_min_size']}곳)")
    print(f"저장 위치: {OUT_PATH}")


if __name__ == "__main__":
    main()
