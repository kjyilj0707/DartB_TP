"""기존 출입문 1개, 0개 캠퍼스 순서로 추가 좌표 후보를 수집한다."""

import argparse
import csv
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from collect_univ_gates import API_URL_KEYWORD, DATA_DIR, core_name, haversine_m


AUDIT_DIR = DATA_DIR / "gate_audit_20260922"
TERMS = ["정문", "후문", "동문", "서문", "남문", "북문", "중문", "출입구", "입구", "쪽문"]
EXTRA_TERMS = {
    "서울과학기술대학교": ["창의문", "협동문"],
    "건국대학교 서울캠퍼스": ["건국문", "상허문", "일감문", "새천년관 출입구"],
    "서울대학교 연건캠퍼스": ["연건캠퍼스 정문", "연건캠퍼스 후문"],
    "서울시립대학교": ["미래문", "이음문", "하늘문"],
    "동국대학교 서울캠퍼스": ["혜화문"],
    "경희대학교 서울캠퍼스": ["등용문"],
    "한양대학교 서울캠퍼스": ["애지문", "사근동출입로", "건축관출입로"],
    "이화여자대학교": ["북아현문", "공학관문"],
}
ALIASES = {
    "KAIST 서울캠퍼스": ["카이스트 서울캠퍼스", "한국과학기술원 서울캠퍼스", "고등과학원"],
    "KAIST 도곡캠퍼스": ["카이스트 도곡캠퍼스"],
    "한국외국어대학교 서울캠퍼스": ["한국외대", "외대 서울캠퍼스"],
    "서울과학기술대학교": ["서울과기대"],
    "덕성여자대학교": ["덕성여대"],
    "서울여자대학교 서울캠퍼스": ["서울여대"],
    "숙명여자대학교": ["숙명여대"],
}


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_rows(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def targets(all_campuses=False):
    universities = read_rows(DATA_DIR / "seoul_universities.csv")
    gates = read_rows(DATA_DIR / "seoul_univ_gates_kakao.csv")
    counts = {}
    for gate in gates:
        counts[gate["univ_id"]] = counts.get(gate["univ_id"], 0) + 1
    selected = [dict(university, old_count=counts.get(university["id"], 0))
                for university in universities if all_campuses or counts.get(university["id"], 0) < 2]
    return sorted(selected, key=lambda row: (-row["old_count"], row["place_name"])), gates


def fetch_query(session, headers, university, query):
    params = {"query": query, "x": university["lon"], "y": university["lat"],
              "radius": 3000, "size": 15, "sort": "accuracy"}
    digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:24]
    cache = AUDIT_DIR / "kakao_cache" / f"{digest}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    pages = []
    for page in range(1, 4):
        for attempt in range(3):
            try:
                response = session.get(API_URL_KEYWORD, headers=headers,
                                       params=dict(params, page=page), timeout=20)
                if response.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 * (attempt + 1))
                    continue
                response.raise_for_status()
                payload = response.json()
                break
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
        else:
            raise RuntimeError(f"Query failed after retries: {query}")
        pages.append(payload)
        time.sleep(0.15)
        if payload["meta"]["is_end"]:
            break
    result = {"query": query, "univ_id": university["id"], "params": params,
              "retrieved_at": datetime.now(timezone.utc).isoformat(), "pages": pages}
    cache.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def collect(group=None):
    selected, old_gates = targets(all_campuses=group == 2)
    if group is not None:
        selected = [university for university in selected
                    if (university["old_count"] >= 2 if group == 2 else university["old_count"] == group)]
    (AUDIT_DIR / "kakao_cache").mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    headers = {"Authorization": "KakaoAK " + os.environ["KAKAO_REST_API_KEY"]}
    all_rows, query_rows = [], []
    for university in selected:
        name = university["place_name"]
        prefixes = list(dict.fromkeys([name, core_name(name)] + ALIASES.get(name, [])))
        queries = [f"{prefix} {term}" for prefix in prefixes for term in TERMS]
        queries += [f"{core_name(name)} {term}" for term in EXTRA_TERMS.get(name, [])]
        found = {}
        for query in dict.fromkeys(queries):
            result = fetch_query(session, headers, university, query)
            documents = [document for page in result["pages"] for document in page["documents"]]
            query_rows.append({"univ_id": university["id"], "query": query,
                               "results": len(documents),
                               "truncated": not result["pages"][-1]["meta"]["is_end"]})
            for document in documents:
                place = document["place_name"]
                category = document.get("category_name", "")
                if "입출구" not in category and not re.search(r"(?:[가-힣0-9]+문|출입구|쪽문|입구)(?:\s|$)", place):
                    continue
                identity = document["id"]
                if identity in found:
                    found[identity]["queries"].append(query)
                    continue
                distance = haversine_m(float(university["lat"]), float(university["lon"]),
                                       float(document["y"]), float(document["x"]))
                previous = [gate for gate in old_gates if gate["univ_id"] == university["id"]]
                nearest = min((haversine_m(float(gate["lat"]), float(gate["lon"]),
                                          float(document["y"]), float(document["x"]))
                               for gate in previous), default=None)
                found[identity] = {
                    "univ_id": university["id"], "univ_name": name,
                    "old_count": university["old_count"], "kakao_id": identity,
                    "place_name": place, "category_name": category,
                    "lat": document["y"], "lon": document["x"],
                    "campus_distance_m": round(distance, 1),
                    "nearest_old_gate_m": round(nearest, 1) if nearest is not None else "",
                    "place_url": document["place_url"], "address_name": document["address_name"],
                    "status": "candidate_unverified", "queries": [query],
                }
        for candidate in found.values():
            candidate["queries"] = " | ".join(candidate["queries"])
            all_rows.append(candidate)
        print(f"old={university['old_count']} {name}: {len(found)} candidates", flush=True)
    fields = ["univ_id", "univ_name", "old_count", "kakao_id", "place_name", "category_name",
              "lat", "lon", "campus_distance_m", "nearest_old_gate_m", "place_url", "address_name",
              "status", "queries"]
    suffix = "all" if group is None else str(group)
    write_rows(AUDIT_DIR / f"kakao_candidates_{suffix}.csv", all_rows, fields)
    write_rows(AUDIT_DIR / f"query_log_{suffix}.csv", query_rows,
               ["univ_id", "query", "results", "truncated"])
    print(f"Saved {len(all_rows)} unverified candidates; {len(query_rows)} queries", flush=True)


def collect_osm(campuses=False, paths=False, all_paths=False):
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    output = AUDIT_DIR / ("osm_paths_all64.json" if all_paths else "osm_paths.json" if paths else "osm_campuses.json" if campuses else "osm_barriers.json")
    if output.exists():
        print("OSM cache already exists", flush=True)
        return
    query = ('[out:json][timeout:90];node["barrier"~"^(gate|lift_gate|swing_gate|entrance|kissing_gate|cycle_barrier)$"]'
             '(37.413,126.734,37.715,127.269);out body;')
    if campuses:
        query = ('[out:json][timeout:90];nwr["amenity"="university"]'
                 '(37.413,126.734,37.715,127.269);out geom;')
    if paths or all_paths:
        from build_gate_audit import BOUNDARIES
        if all_paths:
            from audit_all_campuses import ALL_BOUNDARIES as BOUNDARIES
        campus_elements = json.loads((AUDIT_DIR / "osm_campuses.json").read_text(encoding="utf-8"))["elements"]
        identities = {identity for values in BOUNDARIES.values() for identity in values}
        selectors = ''.join(f"{element['type']}({element['id']});" for element in campus_elements
                            if element['id'] in identities)
        query = ('[out:json][timeout:90];(' + selectors + ')->.campuses;'
                 '.campuses map_to_area->.areas;'
                 'way(area.areas)["highway"~"^(footway|path|pedestrian|steps|service|residential|unclassified|living_street)$"];out geom;')
    response = requests.post("https://overpass-api.de/api/interpreter", data={"data": query},
                             headers={"User-Agent": "dartb-accessibility-study/0.1"}, timeout=110)
    response.raise_for_status()
    payload = response.json()
    if payload.get("remark"):
        raise RuntimeError(payload["remark"])
    output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"OSM barrier candidates: {len(payload['elements'])}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", type=int, choices=[0, 1, 2])
    parser.add_argument("--osm", action="store_true")
    parser.add_argument("--osm-campuses", action="store_true")
    parser.add_argument("--osm-paths", action="store_true")
    parser.add_argument("--osm-paths-all", action="store_true")
    arguments = parser.parse_args()
    if arguments.osm or arguments.osm_campuses or arguments.osm_paths or arguments.osm_paths_all:
        collect_osm(campuses=arguments.osm_campuses, paths=arguments.osm_paths, all_paths=arguments.osm_paths_all)
    else:
        collect(arguments.group)
