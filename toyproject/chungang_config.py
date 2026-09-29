"""중앙대학교 서울캠퍼스 분석 영역 설정 (숭실대와 같은 비교 규칙)."""

from collect_infra_places import bbox_from_center

# 카카오 키워드 검색 "중앙대학교 서울캠퍼스" 대표점 (EPSG:4326)
CENTER_LAT = 37.50514938189445
CENTER_LON = 126.95717341298158
RADIUS_M = 800

# 기존 중앙대 파일들이 사용한 OSM 정문 기준점. 기준점 차이 확인용이다.
OLD_MAIN_GATE_LAT = 37.5070419
OLD_MAIN_GATE_LON = 126.9591522

BBOX = bbox_from_center(CENTER_LAT, CENTER_LON, RADIUS_M)
