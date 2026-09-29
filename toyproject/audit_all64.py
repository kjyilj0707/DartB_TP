"""H7 출입문 재조사를 64개 캠퍼스 전체로 확장한다 (Codex 46곳 작업의 이어받기).

- 기존 46곳 산출물(data/h7/gate_audit_20260922/*.csv)은 건드리지 않고, 결과는 all64/ 하위에 따로 쓴다.
- 기준은 Codex가 사용자와 합의한 것과 같다: 캠퍼스 경계에서 외부 보행로와 내부 보행로가 이어지는 지점만 문으로
  인정하고, 건물 출입구·차량 전용·중복은 제외, 불확실하면 미확정. 모든 행은 analysis_ready=False.

실행:
  python -X utf8 audit_all64.py --fetch-paths   # 기존 18곳 경계의 OSM 보행로를 캠퍼스별로 작게 받는다
  python -X utf8 audit_all64.py                 # 64곳 검토표·출입문 정의표·지도 생성 (네트워크 불필요)
"""

import argparse
import html
import json
import time
from collections import Counter

import folium
import requests

from audit_all_campuses import ALL_BOUNDARIES
from audit_univ_gates import AUDIT_DIR, read_rows, targets, write_rows
from build_gate_audit import BOUNDARIES, crossing_candidates, spatial_candidates
from collect_univ_gates import core_name, haversine_m
from gate_audit_evidence import SELECTED_KAKAO
from gate_evidence_all64 import ALL_EVIDENCE, NAMED_GATE_EVIDENCE

OUT_DIR = AUDIT_DIR / "all64"
PATH_CACHE = AUDIT_DIR / "osm_paths_group2"
MERGED_PATHS = AUDIT_DIR / "osm_paths_all64.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HIGHWAY = "^(footway|path|pedestrian|steps|service|residential|unclassified|living_street)$"
DEDUP_M = 50

# 한 캠퍼스 안의 여러 문을 대학 비교에서 따로 다뤄야 하는 경우(지하철 연결 등).
SEPARATE_LAYER = {"애지문": "지하접근_별도층_보류"}
# 이름에 학교명·문 이름이 들어가도 캠퍼스 보행 출입문이 아닌 것(주차장, 부속학교, 병원 등).
EXCLUDE_WORDS = ("주차장", "부속", "초등학교", "중학교", "고등학교", "병원", "ATM")
# '…문'·'게이트' 키워드 추가 탐색(audit_gate_keywords.py)에서 사용자가 채택한 후보. 공식 명칭 대응이 없어 B 등급.
KEYWORD_ADDITIONS = {"11369827": {"17569302": "키워드추가_보행미검증", "1045105981": "키워드추가_보행미검증"}}
# 캠퍼스 단위 자체가 먼저 결정돼야 하는 상태(Codex 근거표의 review_status).
UNIT_HOLD = {"표본단위검토", "공유부지검토", "주소불일치검토", "경계확인필요"}


def fetch_group2_paths():
    """기존 46곳 경계에 없던 17곳만 캠퍼스별로 요청한다. 한 번에 64곳을 요청하면 Overpass가 504를 낸다."""
    PATH_CACHE.mkdir(parents=True, exist_ok=True)
    campus_elements = json.loads((AUDIT_DIR / "osm_campuses.json").read_text(encoding="utf-8"))["elements"]
    kinds = {element["id"]: element["type"] for element in campus_elements if element["type"] != "node"}
    for univ_id, osm_ids in ALL_BOUNDARIES.items():
        if univ_id in BOUNDARIES:
            continue
        cache = PATH_CACHE / f"{univ_id}.json"
        if cache.exists():
            continue
        selectors = "".join(f"{'rel' if kinds[i] == 'relation' else 'way'}({i});" for i in osm_ids)
        query = (f'[out:json][timeout:60];({selectors})->.c;.c map_to_area->.a;'
                 f'way(area.a)["highway"~"{HIGHWAY}"];out geom;')
        for attempt in range(3):
            try:
                response = requests.post(OVERPASS_URL, data={"data": query},
                                         headers={"User-Agent": "dartb-accessibility-study/0.1"}, timeout=90)
                response.raise_for_status()
                payload = response.json()
                if payload.get("remark"):
                    raise RuntimeError(payload["remark"])
                cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                print(f"{univ_id}: {len(payload['elements'])} ways", flush=True)
                break
            except Exception as error:
                print(f"{univ_id}: attempt {attempt + 1} failed ({type(error).__name__})", flush=True)
                time.sleep(5 * (attempt + 1))
        time.sleep(2)
    missing = [u for u in ALL_BOUNDARIES if u not in BOUNDARIES and not (PATH_CACHE / f"{u}.json").exists()]
    print(f"missing path caches: {missing}", flush=True)


def merge_paths():
    ways = {way["id"]: way for way in json.loads((AUDIT_DIR / "osm_paths.json").read_text(encoding="utf-8"))["elements"]}
    for cache in PATH_CACHE.glob("*.json"):
        for way in json.loads(cache.read_text(encoding="utf-8"))["elements"]:
            ways[way["id"]] = way
    MERGED_PATHS.write_text(json.dumps({"elements": list(ways.values())}, ensure_ascii=False), encoding="utf-8")
    return len(ways)


def select_group2(universities, baseline):
    """기존 2개 이상 18곳: 공식 문 이름 + 학교 이름이 모두 들어간 카카오 POI만 추가 좌표로 고른다(수동 선택 대신 규칙)."""
    raw = read_rows(AUDIT_DIR / "kakao_candidates_2.csv")
    rows = []
    for university in universities:
        identity = university["id"]
        if university["old_count"] < 2:
            continue
        official = NAMED_GATE_EVIDENCE.get(identity, [])
        core = core_name(university["place_name"])
        existing = [gate for gate in baseline if gate["univ_id"] == identity]
        for candidate in raw:
            if candidate["univ_id"] != identity or core not in candidate["place_name"]:
                continue
            gate_name = next((name for name in official if name in candidate["place_name"]), None)
            if gate_name is None:
                continue
            if any(word in candidate["place_name"] for word in EXCLUDE_WORDS):
                continue
            if "입출구" not in candidate["category_name"] and gate_name not in SEPARATE_LAYER:
                continue
            lat, lon = float(candidate["lat"]), float(candidate["lon"])
            if any(haversine_m(lat, lon, float(g["lat"]), float(g["lon"])) <= DEDUP_M for g in existing):
                continue
            rows.append({"univ_id": identity, "univ_name": university["place_name"], "name": candidate["place_name"],
                         "lat": candidate["lat"], "lon": candidate["lon"], "coordinate_source": "Kakao",
                         "source_id": candidate["kakao_id"], "source_url": candidate["place_url"],
                         "status": SEPARATE_LAYER.get(gate_name, "명명문_현행보행미검증"),
                         "analysis_ready": False, "evidence_url": ALL_EVIDENCE[identity][2]})
    return rows


def reviewed_rows(universities, baseline, barriers):
    """46곳은 Codex의 수동 결정(SELECTED_KAKAO, 체대 OSM)을 그대로 쓰고, 18곳은 select_group2 규칙을 쓴다."""
    raw = read_rows(AUDIT_DIR / "kakao_candidates_1.csv") + read_rows(AUDIT_DIR / "kakao_candidates_0.csv")
    lookup = {(row["univ_id"], row["kakao_id"]): row for row in raw}
    rows = []
    for identity, selections in SELECTED_KAKAO.items():
        for kakao_id, status in selections.items():
            candidate = lookup[(identity, kakao_id)]
            rows.append({"univ_id": identity, "univ_name": candidate["univ_name"], "name": candidate["place_name"],
                         "lat": candidate["lat"], "lon": candidate["lon"], "coordinate_source": "Kakao",
                         "source_id": kakao_id, "source_url": candidate["place_url"], "status": status,
                         "analysis_ready": False, "evidence_url": ALL_EVIDENCE[identity][2]})
    for candidate in barriers:
        if candidate["univ_id"] != "11219441":
            continue
        rows.append({"univ_id": candidate["univ_id"], "univ_name": candidate["univ_name"], "name": candidate["name"],
                     "lat": candidate["lat"], "lon": candidate["lon"], "coordinate_source": "OSM",
                     "source_id": candidate["osm_id"], "source_url": candidate["source_url"],
                     "status": "명명문_OSM보행태그있음" if candidate["foot"] == "yes" else "명명문_보행미검증",
                     "analysis_ready": False, "evidence_url": ALL_EVIDENCE[candidate["univ_id"]][2]})
    by_id = {row["kakao_id"]: row for row in raw + read_rows(AUDIT_DIR / "kakao_candidates_2.csv")}
    names = {u["id"]: u["place_name"] for u in universities}
    for identity, selections in KEYWORD_ADDITIONS.items():
        for kakao_id, status in selections.items():
            candidate = by_id[kakao_id]
            rows.append({"univ_id": identity, "univ_name": names[identity], "name": candidate["place_name"],
                         "lat": candidate["lat"], "lon": candidate["lon"], "coordinate_source": "Kakao",
                         "source_id": kakao_id, "source_url": candidate["place_url"], "status": status,
                         "analysis_ready": False, "evidence_url": ALL_EVIDENCE[identity][2]})
    return rows + select_group2(universities, baseline)


def gate_definition(universities, baseline, reviewed):
    """캠퍼스별 출입문 목록: 기존 카카오 문 + 검토 추가 좌표 + 좌표 없는 공식 명칭. 근거 등급을 붙인다.

    A = 공식 자료의 문 이름과 좌표 POI 이름이 일치 / B = 좌표만 있음(공식 명칭 대응 없음) /
    C = 공식 명칭은 있으나 좌표 없음. 보류(중복·하위캠퍼스·병원공유·지하층)는 제외 표시.
    """
    rows = []
    for university in universities:
        identity = university["id"]
        official = NAMED_GATE_EVIDENCE.get(identity, [])
        unit_status = ALL_EVIDENCE[identity][0]
        items = [{"name": g["place_name"], "lat": g["lat"], "lon": g["lon"], "coordinate_source": "Kakao(기존수집)",
                  "status": "기존수집_재검증필요"} for g in baseline if g["univ_id"] == identity]
        items += [{"name": r["name"], "lat": r["lat"], "lon": r["lon"], "coordinate_source": r["coordinate_source"],
                   "status": r["status"]} for r in reviewed if r["univ_id"] == identity]
        matched = set()  # 보류된 좌표도 포함: 좌표가 있으면 C(좌표 없음)로 다시 세지 않는다
        for item in items:
            held = any(word in item["status"] for word in ("보류", "중복제외"))
            official_name = next((name for name in official if name in item["name"]), "")
            if official_name:
                matched.add(official_name)
            tier = "제외_보류" if held else ("A_공식명칭+좌표" if official_name else "B_좌표만")
            rows.append({"univ_id": identity, "univ_name": university["place_name"], "campus_status": unit_status,
                         "gate_name": item["name"], "official_name": official_name, "tier": tier,
                         "lat": item["lat"], "lon": item["lon"], "coordinate_source": item["coordinate_source"],
                         "item_status": item["status"], "analysis_ready": False})
        for name in official:
            if name not in matched:
                rows.append({"univ_id": identity, "univ_name": university["place_name"], "campus_status": unit_status,
                             "gate_name": name, "official_name": name, "tier": "C_공식명칭_좌표없음", "lat": "", "lon": "",
                             "coordinate_source": "", "item_status": "좌표확보필요", "analysis_ready": False})
    return rows


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_ways = merge_paths()
    universities, baseline = targets(all_campuses=True)
    assert set(ALL_EVIDENCE) == {u["id"] for u in universities}
    features, barriers = spatial_candidates(selected=universities, boundaries=ALL_BOUNDARIES, output_dir=OUT_DIR)
    crossings = crossing_candidates(features, path_file=MERGED_PATHS, output_dir=OUT_DIR)
    reviewed = reviewed_rows(universities, baseline, barriers)
    fields = ["univ_id", "univ_name", "name", "lat", "lon", "coordinate_source", "source_id", "source_url",
              "status", "analysis_ready", "evidence_url"]
    write_rows(OUT_DIR / "reviewed_gate_candidates.csv", reviewed, fields)

    definition = gate_definition(universities, baseline, reviewed)
    write_rows(OUT_DIR / "gate_definition_all64.csv", definition, list(definition[0]))

    boundary_ids = {f["properties"]["univ_id"] for f in features}
    summary = []
    for university in universities:
        identity = university["id"]
        status, note, source = ALL_EVIDENCE[identity]
        gates = [row for row in definition if row["univ_id"] == identity]
        tier_a = sum(row["tier"] == "A_공식명칭+좌표" for row in gates)
        tier_b = sum(row["tier"] == "B_좌표만" for row in gates)
        summary.append({"univ_id": identity, "univ_name": university["place_name"],
                        "old_count": university["old_count"], "review_status": status,
                        "unit_hold": status in UNIT_HOLD,
                        "gates_A": tier_a, "gates_B": tier_b,
                        "gates_C_no_coordinate": sum(row["tier"] == "C_공식명칭_좌표없음" for row in gates),
                        "gates_held": sum(row["tier"] == "제외_보류" for row in gates),
                        "official_named_gates": " / ".join(NAMED_GATE_EVIDENCE.get(identity, [])),
                        "osm_boundary_available": identity in boundary_ids,
                        "barrier_candidate_records": sum(row["univ_id"] == identity for row in barriers),
                        "path_candidate_records": sum(row["univ_id"] == identity for row in crossings),
                        "findings": note, "source_url": source, "review_date": "2026-09-22"})
    write_rows(OUT_DIR / "campus_audit_all64.csv", summary, list(summary[0]))

    campus_map = folium.Map(location=[37.56, 126.99], zoom_start=11)
    folium.GeoJson({"type": "FeatureCollection", "features": features}, name="OSM 캠퍼스 경계(미검증)",
                   tooltip=folium.GeoJsonTooltip(fields=["univ_name"])).add_to(campus_map)
    colors = {"A_공식명칭+좌표": "green", "B_좌표만": "orange", "제외_보류": "gray"}
    layers = {tier: folium.FeatureGroup(name=f"출입문 {tier}", show=True).add_to(campus_map) for tier in colors}
    path_layer = folium.FeatureGroup(name="도로-경계 기하 후보", show=False).add_to(campus_map)
    for row in definition:
        if row["tier"] not in colors:
            continue
        label = " | ".join(str(row[k]) for k in ["univ_name", "gate_name", "tier", "item_status"])
        folium.CircleMarker([float(row["lat"]), float(row["lon"])], radius=5, color=colors[row["tier"]],
                            fill=True, popup=html.escape(label)).add_to(layers[row["tier"]])
    for row in crossings:
        folium.CircleMarker([float(row["lat"]), float(row["lon"])], radius=2, color="purple",
                            popup=html.escape(f"{row['univ_name']} | {row['highway']} | {row['status']}")).add_to(path_layer)
    folium.LayerControl().add_to(campus_map)
    campus_map.save(str(OUT_DIR / "gate_review_map_all64.html"))

    print(f"OSM path ways used: {n_ways}; boundaries: {len(features)}; path records: {len(crossings)}")
    print(f"reviewed coordinate rows: {len(reviewed)}; gate definition rows: {len(definition)}")
    print("tiers:", dict(Counter(row["tier"] for row in definition)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-paths", action="store_true")
    if parser.parse_args().fetch_paths:
        fetch_group2_paths()
    else:
        main()
