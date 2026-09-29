"""출입문 재조사 근거와 경계 근접 후보를 정리한다. 분석용 원본은 변경하지 않는다."""

import html
import json
from collections import Counter

import folium
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import polygonize, transform, unary_union

from audit_univ_gates import AUDIT_DIR, DATA_DIR, read_rows, targets, write_rows
from gate_audit_evidence import EVIDENCE, SELECTED_KAKAO


BOUNDARIES = {
    "17384594": [416468238], "10148561": [804478563, 804478564, 804478565, 804483798],
    "8262964": [381500241], "11333604": [462886441], "8356870": [221502708],
    "7946584": [380851207], "9108449": [380910936], "9879420": [380920082],
    "7949668": [965940829], "7813439": [20613615], "11244281": [7027282],
    "11272875": [223434839, 1160652007, 1160652009, 1160683105],
    "8132452": [223434841], "8138835": [768481829], "11025307": [241449401],
    "12840668": [26281749], "8917867": [649380298], "7940291": [228171769],
    "7939462": [463180987], "11137164": [223434837], "8139895": [249854000],
    "20599241": [183847196], "12817755": [475332792], "11237653": [367420004],
    "8135259": [223434838], "17010755": [173167199], "8644095": [330535350],
    "11219441": [415026013], "10942308": [187354397],
}
PROJECTION = Transformer.from_crs(4326, 5186, always_xy=True).transform


def geometry(element):
    if element["type"] == "way":
        coordinates = [(node["lon"], node["lat"]) for node in element["geometry"]]
        if len(coordinates) < 4 or coordinates[0] != coordinates[-1]:
            raise ValueError(f"Not a closed campus polygon: {element['id']}")
        return Polygon(coordinates).buffer(0)
    outer_lines, inner_lines = [], []
    for member in element["members"]:
        if member["type"] != "way" or "geometry" not in member:
            continue
        points = [(node["lon"], node["lat"]) for node in member["geometry"]]
        destination = inner_lines if member.get("role") == "inner" else outer_lines
        destination.append(LineString(points))
    outer = unary_union(list(polygonize(unary_union(outer_lines))))
    if inner_lines:
        outer = outer.difference(unary_union(list(polygonize(unary_union(inner_lines)))))
    if outer.is_empty:
        raise ValueError(f"Empty campus polygon: {element['id']}")
    return outer.buffer(0)


def spatial_candidates(selected=None, boundaries=None, output_dir=AUDIT_DIR):
    default_selected, old_gates = targets()
    selected = default_selected if selected is None else selected
    boundaries = BOUNDARIES if boundaries is None else boundaries
    elements = json.loads((AUDIT_DIR / "osm_campuses.json").read_text(encoding="utf-8"))["elements"]
    lookup = {element["id"]: element for element in elements if element["type"] != "node"}
    nodes = json.loads((AUDIT_DIR / "osm_barriers.json").read_text(encoding="utf-8"))["elements"]
    entrance_nodes = json.loads((DATA_DIR / "osm_seoul_named_entrances.json").read_text(encoding="utf-8"))
    nodes = list({node["id"]: node for node in nodes + entrance_nodes}.values())
    projected_nodes = [(node, transform(PROJECTION, Point(node["lon"], node["lat"]))) for node in nodes]
    features, candidates = [], []
    for university in selected:
        ids = boundaries.get(university["id"], [])
        if not ids:
            continue
        polygon = unary_union([geometry(lookup[identity]) for identity in ids])
        projected = transform(PROJECTION, polygon)
        features.append({"type": "Feature", "properties": {"univ_id": university["id"],
                         "univ_name": university["place_name"], "osm_ids": ids}, "geometry": mapping(polygon)})
        existing = [transform(PROJECTION, Point(float(gate["lon"]), float(gate["lat"])))
                    for gate in old_gates if gate["univ_id"] == university["id"]]
        for node, point in projected_nodes:
            distance = point.distance(projected.boundary)
            if distance > 20:
                continue
            tags = node.get("tags", {})
            candidates.append({"univ_id": university["id"], "univ_name": university["place_name"],
                               "old_count": university["old_count"], "osm_id": node["id"],
                               "name": tags.get("name", "이름 없는 경계 후보"), "lat": node["lat"],
                               "lon": node["lon"], "boundary_distance_m": round(distance, 1),
                               "nearest_old_gate_m": round(min(point.distance(old) for old in existing), 1) if existing else "",
                               "foot": tags.get("foot", ""), "access": tags.get("access", ""),
                               "barrier": tags.get("barrier", ""), "entrance": tags.get("entrance", ""),
                               "source_url": f"https://www.openstreetmap.org/node/{node['id']}",
                               "status": "경계근접_보행연결미검증", "tags": json.dumps(tags, ensure_ascii=False)})
    (output_dir / "campus_boundaries.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8")
    fields = ["univ_id", "univ_name", "old_count", "osm_id", "name", "lat", "lon", "boundary_distance_m",
              "nearest_old_gate_m", "foot", "access", "barrier", "entrance", "source_url", "status", "tags"]
    write_rows(output_dir / "osm_boundary_candidates.csv", candidates, fields)
    print(f"Campus boundaries: {len(features)}; boundary candidates: {len(candidates)}")
    for university in selected:
        matches = [candidate for candidate in candidates if candidate["univ_id"] == university["id"]]
        print(university["place_name"], [(row["osm_id"], row["name"], row["nearest_old_gate_m"], row["foot"], row["access"]) for row in matches])
    return features, candidates


def crossing_candidates(features, path_file=None, output_dir=AUDIT_DIR):
    path_file = AUDIT_DIR / "osm_paths.json" if path_file is None else path_file
    ways = json.loads(path_file.read_text(encoding="utf-8"))["elements"]
    projected_ways = [(way, transform(PROJECTION, LineString([
        (node["lon"], node["lat"]) for node in way["geometry"]])))
        for way in ways if way["type"] == "way" and len(way.get("geometry", [])) >= 2]
    inverse = Transformer.from_crs(5186, 4326, always_xy=True).transform
    rows = []
    for feature in features:
        polygon = transform(PROJECTION, shape(feature["geometry"]))
        for way, line in projected_ways:
            if not line.intersects(polygon.boundary):
                continue
            intersection = line.intersection(polygon.boundary)
            points = [intersection] if intersection.geom_type == "Point" else [
                part for part in getattr(intersection, "geoms", []) if part.geom_type == "Point"]
            if line.intersection(polygon.buffer(-1)).length < 1:
                continue
            crosses = line.difference(polygon.buffer(1)).length > 1
            tags = way.get("tags", {})
            restricted = tags.get("foot") in ("no", "private") or (
                tags.get("access") in ("no", "private") and tags.get("foot") not in ("yes", "designated", "permissive"))
            for point in points:
                coordinate = transform(inverse, point)
                rows.append({"univ_id": feature["properties"]["univ_id"],
                             "univ_name": feature["properties"]["univ_name"], "osm_way_id": way["id"],
                             "lat": coordinate.y, "lon": coordinate.x, "highway": tags.get("highway", ""),
                             "foot": tags.get("foot", ""), "access": tags.get("access", ""),
                             "geometry_evidence": "경계양측교차" if crosses else "경계접점_외부연결미확인",
                             "status": "접근제한태그_보류" if restricted else "기하후보_출입문미검증",
                             "source_url": f"https://www.openstreetmap.org/way/{way['id']}"})
    fields = ["univ_id", "univ_name", "osm_way_id", "lat", "lon", "highway", "foot", "access", "geometry_evidence", "status", "source_url"]
    write_rows(output_dir / "osm_path_boundary_candidates.csv", rows, fields)
    return rows


def build_review(features, barriers, crossings):
    universities, baseline = targets()
    assert set(EVIDENCE) == {university["id"] for university in universities}
    raw = read_rows(AUDIT_DIR / "kakao_candidates_1.csv") + read_rows(AUDIT_DIR / "kakao_candidates_0.csv")
    lookup = {(row["univ_id"], row["kakao_id"]): row for row in raw}
    reviewed = []
    for identity, selections in SELECTED_KAKAO.items():
        for kakao_id, status in selections.items():
            candidate = lookup[(identity, kakao_id)]
            reviewed.append({"univ_id": identity, "univ_name": candidate["univ_name"],
                             "name": candidate["place_name"], "lat": candidate["lat"], "lon": candidate["lon"],
                             "coordinate_source": "Kakao", "source_id": kakao_id,
                             "source_url": candidate["place_url"], "status": status,
                             "analysis_ready": False, "evidence_url": EVIDENCE[identity][2]})
    for candidate in barriers:
        if candidate["univ_id"] != "11219441":
            continue
        reviewed.append({"univ_id": candidate["univ_id"], "univ_name": candidate["univ_name"],
                         "name": candidate["name"], "lat": candidate["lat"], "lon": candidate["lon"],
                         "coordinate_source": "OSM", "source_id": candidate["osm_id"],
                         "source_url": candidate["source_url"],
                         "status": "명명문_OSM보행태그있음" if candidate["foot"] == "yes" else "명명문_보행미검증",
                         "analysis_ready": False, "evidence_url": EVIDENCE[candidate["univ_id"]][2]})
    fields = ["univ_id", "univ_name", "name", "lat", "lon", "coordinate_source", "source_id", "source_url", "status", "analysis_ready", "evidence_url"]
    write_rows(AUDIT_DIR / "reviewed_gate_candidates.csv", reviewed, fields)
    boundary_ids = {feature["properties"]["univ_id"] for feature in features}
    summary = []
    for university in universities:
        identity = university["id"]
        status, note, source = EVIDENCE[identity]
        selected = [row for row in reviewed if row["univ_id"] == identity]
        summary.append({"univ_id": identity, "univ_name": university["place_name"],
                        "old_count": university["old_count"], "review_status": status,
                        "new_coordinate_candidates": sum("보류" not in row["status"] and "중복제외" not in row["status"] for row in selected),
                        "osm_boundary_available": identity in boundary_ids,
                        "barrier_candidate_records": sum(row["univ_id"] == identity for row in barriers),
                        "path_candidate_records": sum(row["univ_id"] == identity for row in crossings),
                        "findings": note, "source_url": source, "review_date": "2026-09-22"})
    write_rows(AUDIT_DIR / "campus_audit.csv", summary, list(summary[0]))
    campus_map = folium.Map(location=[37.56, 126.99], zoom_start=11)
    folium.GeoJson({"type": "FeatureCollection", "features": features}, name="OSM 캠퍼스 경계(미검증)",
                   tooltip=folium.GeoJsonTooltip(fields=["univ_name"])).add_to(campus_map)
    layers = {name: folium.FeatureGroup(name=name, show=show).add_to(campus_map) for name, show in
              [("기존 수집 문(보행 재검증 필요)", True), ("선별한 추가 좌표", True), ("OSM 장벽 후보", False), ("도로-경계 기하 후보", False)]}
    for rows, layer_name, color in [(baseline, "기존 수집 문(보행 재검증 필요)", "blue"),
                                     (reviewed, "선별한 추가 좌표", "orange"),
                                     (barriers, "OSM 장벽 후보", "purple"), (crossings, "도로-경계 기하 후보", "gray")]:
        for row in rows:
            if row["univ_id"] not in EVIDENCE or "중복제외" in row.get("status", ""):
                continue
            label = " | ".join(str(row.get(key, "")) for key in ["univ_name", "name", "place_name", "status", "geometry_evidence", "source_url"])
            folium.CircleMarker([float(row["lat"]), float(row["lon"])], radius=4, color=color,
                                fill=True, popup=html.escape(label)).add_to(layers[layer_name])
    folium.LayerControl().add_to(campus_map)
    campus_map.save(str(AUDIT_DIR / "gate_review_map.html"))
    report = ["# H7 출입문 1개·0개 캠퍼스 재조사 (2026-09-22)", "",
              "## 읽기 전에", "",
              "- 기존 1개 12곳을 먼저 검색하고, 0개 34곳을 이어 조사했다. 원본 CSV는 변경하지 않았다.",
              "- 전수 현장 검증이 아닌 1차 자료 조사다. 검색 결과 부재는 출입문 부재가 아니다.",
              "- 공식 자료도 과거 공지·검색 색인·주차 안내가 섞여 있다. 아래 URL은 학교별 근거 또는 위치 참고이며 모든 문을 입증하지 않는다. 본문 미열람·현행 여부 등 한계는 조사 결과에 적었다.",
              "- reviewed_gate_candidates.csv의 모든 analysis_ready는 False다. 이름·좌표 확보와 현행 외부 보행 연결 검증은 다르다.",
              "- 기하 후보 행은 도로와 경계의 교차·접점 기록이다. 동일 출입점에 여러 도로가 붙을 수 있어 행 수를 문 개수로 세면 안 된다. 경계 정확도, 담장, 고저차, 운영시간을 확인해야 한다.",
              "- OSM 경계가 매칭된 29곳만 기하 후보를 만들었다. 나머지 17곳은 경계 미확정이지 출입문 0개가 아니다.",
              "- baseline의 기존 문도 검증 완료가 아니다. 이번 작업은 신호등 수·위치에 맞춰 문을 선택하지 않았고 H7 검정을 실행하지 않았다.", "",
              "## 결과", "", "| 대학 | 기존 수집 | 추가 좌표 후보¹ | 도로 경계 기록² | 판단·남은 확인 |", "|---|---:|---:|---:|---|"]
    for row in summary:
        source = f" [출처/위치 참고]({row['source_url']})" if row["source_url"] else " 공식 출처 미확보."
        report.append(f"| {row['univ_name']} | {row['old_count']} | {row['new_coordinate_candidates']} | {row['path_candidate_records']} | {row['findings']}{source} |")
    report.extend(["", "¹ 중복 2건·별도 하위캠퍼스·병원 공유부지 보류는 이 열에서 제외. 현행 보행 문 확정 수가 아님.",
                   "² 중복·접근제한·외부 연결 불명 기록 포함. 지도에서 회색 레이어를 켜고 확인.", "", "## 다음 확인 순서", "",
                   "1. 서울과기대·명지대·숙명여대의 추가 좌표를 현행 지도/거리 영상과 대조. 숙명 제2창학캠퍼스는 제1캠퍼스와 분리.",
                   "2. 건국대·서울교대·한국체대의 명명 문부터 확인. 번호 문과 쪽문은 별도 보류 가능.",
                   "3. 덕성여대·서경대·서울여대·세종대처럼 문 이름 근거가 있는 곳의 경계 후보를 대조해 좌표 확정.",
                   "4. 기하 후보만 있는 곳은 외부 인도와 내부 보행망의 실제 연결을 확인. 대학원/건물형/병원공유 시설은 표본 단위를 먼저 결정.",
                   "5. 동일 기준으로 기존 18곳도 감사한 뒤에만 분석용 문 목록과 최종 표본 수 확정.", "",
                   "## 파일", "", "- campus_audit.csv: 46곳 전부의 상태·근거·후속 확인.",
                   "- reviewed_gate_candidates.csv: 수동 선별한 좌표와 중복/보류 결정.",
                   "- gate_review_map.html: 기존 문, 추가 좌표, 경계 및 기하 후보 검토 지도(배경 타일은 인터넷 필요).",
                   "- kakao_candidates_0/1.csv: 다른 시설이 다수 섞인 검색 원자료. 분석 입력 금지.",
                   "- query_log_0/1.csv, kakao_cache, osm_*.json: 재현용 검색·수집 기록."])
    (AUDIT_DIR / "README.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Reviewed coordinates: {len(reviewed)}; path-boundary records: {len(crossings)}")
    print("Campus review statuses:", dict(Counter(row["review_status"] for row in summary)))


if __name__ == "__main__":
    boundary_features, barrier_candidates = spatial_candidates()
    path_candidates = crossing_candidates(boundary_features)
    build_review(boundary_features, barrier_candidates, path_candidates)
