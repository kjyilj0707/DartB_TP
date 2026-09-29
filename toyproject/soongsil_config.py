"""
숭실대 분석 영역 설정 (1단계: 대학가 규정)
==========================================
팀 합의(2026-09-21): 카카오맵에서 '숭실대학교'를 검색하면 나오는 지점(캠퍼스 대표점)을
기준점으로 하고, 반경 800m를 대학가로 본다. 네이버 기준점은 비교하지 않기로 함.

값의 출처: 카카오 로컬 API 키워드 검색 "숭실대학교" 1순위 (place_name=숭실대학교,
category=교육,학문 > 학교 > 대학교, 서울 동작구 상도로 369). 좌표계 EPSG:4326.
참고: 같은 검색어의 '숭실대학교 정문' 지점은 이 기준점에서 서쪽으로 약 293m 떨어져 있음
(data/soongsil_center_candidates.csv).
"""

from collect_infra_places import bbox_from_center

CENTER_LAT = 37.495853033944364
CENTER_LON = 126.95781764313084
RADIUS_M = 800

BBOX = bbox_from_center(CENTER_LAT, CENTER_LON, RADIUS_M)  # (min_lon, min_lat, max_lon, max_lat)
