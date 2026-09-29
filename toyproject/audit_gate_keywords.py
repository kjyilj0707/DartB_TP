"""H7 출입문 추가 기준 탐색: 이름에 '…문'/'게이트'/'gate'가 들어간 지점을 찾는다 (카테고리 제한 없음).

결과는 후보 목록일 뿐이며 gate_definition_all64.csv에는 합치지 않는다.
  python -X utf8 audit_gate_keywords.py --fetch   # 64곳 x ('게이트','gate','문') 카카오 추가 검색 (캐시 사용)
  python -X utf8 audit_gate_keywords.py           # 기존+추가 검색 결과에서 새 후보를 추려 CSV로 저장
"""

import argparse
import json
import os
import re

import pandas as pd
import requests
from dotenv import load_dotenv

from audit_univ_gates import ALIASES, AUDIT_DIR, DATA_DIR, fetch_query, targets
from collect_univ_gates import PROJECT_DIR, core_name, haversine_m

load_dotenv(PROJECT_DIR / ".env")

NEW_TERMS = ["게이트", "gate", "문"]
OUT = AUDIT_DIR / "all64" / "keyword_gate_candidates.csv"
NEW_RAW = AUDIT_DIR / "kakao_candidates_keyword.csv"
# 이름 끝이 '…문'인 단어, 또는 게이트/gate
GATE_TOKEN = re.compile(r"(?:[가-힣A-Za-z0-9]*문)(?=\s|$|\(|\))|게이트|gate", re.I)
# '…문'으로 끝나지만 출입문이 아닌 흔한 단어
NOT_GATE_WORDS = ("신문", "전문", "인문", "학문", "주문", "방문", "논문", "질문", "소문", "창문", "문문")
# 가게·교통수단·금융 등 출입문이 아닌 분류
BAD_CATEGORY = ("음식점", "카페", "편의점", "금융", "부동산", "카셰어링", "주차장", "자전거", "학원",
                "병원", "숙박", "미용", "이발", "세탁", "인쇄", "문구")
BAD_NAME = ("아파트", "빌라", "오피스텔", "부속", "초등학교", "중학교", "고등학교", "병원", "ATM", "주차장", "투루카")
DEDUP_M = 50


def name_keys(name):
    keys = [core_name(name)] + ALIASES.get(name, [])
    return list(dict.fromkeys(keys + [k.replace("대학교", "대") for k in keys]))


def fetch():
    universities, _ = targets(all_campuses=True)
    session = requests.Session()
    headers = {"Authorization": "KakaoAK " + os.environ["KAKAO_REST_API_KEY"]}
    rows = []
    for university in universities:
        for key in name_keys(university["place_name"]):
            for term in NEW_TERMS:
                result = fetch_query(session, headers, university, f"{key} {term}")
                for page in result["pages"]:
                    for doc in page["documents"]:
                        rows.append({"univ_id": university["id"], "univ_name": university["place_name"],
                                     "kakao_id": doc["id"], "place_name": doc["place_name"],
                                     "category_name": doc.get("category_name", ""), "lat": doc["y"], "lon": doc["x"],
                                     "place_url": doc["place_url"], "query": f"{key} {term}"})
        print(university["place_name"], flush=True)
    pd.DataFrame(rows).drop_duplicates(["univ_id", "kakao_id"]).to_csv(NEW_RAW, index=False, encoding="utf-8-sig")
    print("saved", NEW_RAW)


def is_gate_name(place):
    tokens = GATE_TOKEN.findall(place)
    return any(t.lower() in ("게이트", "gate") or not t.endswith(NOT_GATE_WORDS) for t in tokens)


def select():
    universities = {u["id"]: u for u in targets(all_campuses=True)[0]}
    old = pd.concat([pd.read_csv(AUDIT_DIR / f"kakao_candidates_{g}.csv", dtype=str) for g in (0, 1, 2)])
    old["source"] = "기존검색"
    new = pd.read_csv(NEW_RAW, dtype=str) if NEW_RAW.exists() else pd.DataFrame()
    if len(new):
        new["source"] = "게이트·문 추가검색"
    raw = pd.concat([old, new], ignore_index=True).drop_duplicates(["univ_id", "kakao_id"])
    defn = pd.read_csv(AUDIT_DIR / "all64" / "gate_definition_all64.csv", dtype=str)
    have = defn[defn["lat"].notna()]
    rows = []
    for _, r in raw.iterrows():
        place, category = r["place_name"], str(r["category_name"])
        if not GATE_TOKEN.search(place) or not is_gate_name(place):
            continue
        if any(w in category for w in BAD_CATEGORY) or any(w in place for w in BAD_NAME):
            continue
        u = universities[r["univ_id"]]
        if not any(k in place for k in name_keys(u["place_name"])):
            continue
        lat, lon = float(r["lat"]), float(r["lon"])
        existing = have[have["univ_id"] == r["univ_id"]]
        nearest = min((haversine_m(lat, lon, float(a), float(b)) for a, b in zip(existing["lat"], existing["lon"])),
                      default=None)
        if nearest is not None and nearest <= DEDUP_M:
            continue
        rows.append({"univ_id": r["univ_id"], "univ_name": u["place_name"], "place_name": place,
                     "category_name": category, "lat": lat, "lon": lon,
                     "campus_distance_m": round(haversine_m(float(u["lat"]), float(u["lon"]), lat, lon), 1),
                     "nearest_existing_gate_m": round(nearest, 1) if nearest is not None else "",
                     "source": r["source"], "place_url": r["place_url"]})
    out = pd.DataFrame(rows).sort_values(["univ_name", "campus_distance_m"])
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"new candidates: {len(out)} (campuses: {out['univ_name'].nunique()}) -> {OUT}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true")
    fetch() if parser.parse_args().fetch else select()
