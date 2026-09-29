"""통학로규정.ipynb에 TMAP 실제 도보 경로 검증 파이프라인을 추가한다."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).parent
PATH = ROOT / "통학로규정.ipynb"


def md(cell_id, source):
    cell = nbformat.v4.new_markdown_cell(source); cell["id"] = cell_id; return cell


def code(cell_id, source):
    cell = nbformat.v4.new_code_cell(source); cell["id"] = cell_id; return cell


cells = [
    md("tmap-intro", """---
# D. TMAP 실제 도보 경로 검증 파이프라인

통학로를 다음과 같이 최종 규정한다.

> **반경 800m 안의 실제 통학 출발지에서, 같은 학교의 검증된 모든 출입문까지 TMAP 보행경로를 조회하고, 도보거리가 가장 짧은 문으로 향하는 경로를 해당 출발지의 통학로로 채택한다.**

TMAP은 실제 추천 도보 경로를 선택·검증하는 역할, OSM은 경로를 엣지 단위로 나누어 경사·횡단보도·음향신호기·사고위험을 붙이는 역할로 분리한다."""),
    md("tmap-origin-md", """## D-1. 출발지 지정

1차 출발지는 반경 800m 안의 **지하철 출구와 버스정류장**으로 정한다.

- 지하철 출구: OSM `railway=subway_entrance`; 가까운 Kakao 역명으로 이름 보정
- 버스정류장: OSM `highway=bus_stop`
- 정류장 도로 양쪽은 서로 다른 승하차 위치이므로 별도 출발지로 유지
- 향후 주거 밀집지·주요 횡단보도 등을 추가할 수 있도록 출발지 표를 독립 CSV로 관리

이 목록은 TMAP 데이터가 아니므로 지속 저장할 수 있다."""),
    code("tmap-origin-code", """import os
from pathlib import Path
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
from dotenv import load_dotenv
import tmap_commute_pipeline as tcp

origin_path = Path('data/commute_origin_candidates.csv')
origins = pd.read_csv(origin_path) if origin_path.exists() else tcp.collect_origin_candidates()
gates_tmap = tcp.load_gates()
display(origins.groupby(['학교', '출발지유형']).size().rename('출발지수').to_frame())
display(origins.sort_values(['학교', '출발지유형', '중심점거리_m']).head(15))
print(f'전체 출발지 {len(origins)}개, 문 {len(gates_tmap)}개')"""),
    code("tmap-origin-map", """fig, axes = plt.subplots(1, 2, figsize=(14, 7))
colors = {'버스정류장': '#2563eb', '지하철출구': '#f59e0b'}
for ax, school in zip(axes, ['숭실대', '중앙대']):
    spec = tcp.SCHOOLS[school]
    edge = gpd.read_file(spec['network_file'], layer='edges')
    edge.plot(ax=ax, color='#d1d5db', linewidth=.5)
    sub = gpd.GeoDataFrame(origins[origins['학교'].eq(school)].copy(),
                           geometry=gpd.points_from_xy(origins.loc[origins['학교'].eq(school), 'lon'], origins.loc[origins['학교'].eq(school), 'lat']), crs='EPSG:4326')
    for kind, group in sub.groupby('출발지유형'):
        group.plot(ax=ax, color=colors[kind], markersize=20 if kind == '버스정류장' else 55,
                   marker='o' if kind == '버스정류장' else 's', label=f'{kind} {len(group)}개')
    gate = gates_tmap[gates_tmap['학교'].eq(school)]
    ax.scatter(gate['lon'], gate['lat'], marker='^', s=90, color='#dc2626', edgecolor='black', label=f'출입문 {len(gate)}개', zorder=5)
    for r in gate.itertuples(): ax.annotate(r.문, (r.lon, r.lat), xytext=(4,4), textcoords='offset points')
    ax.set_title(f'{school}: TMAP 검증 출발지와 목적지 문'); ax.set_aspect('equal'); ax.legend(); ax.set_axis_off()
plt.tight_layout(); plt.show()"""),
    md("tmap-flow-md", """## D-2. 경로 선택·검증·OSM 연결

1. 출발지 하나에서 같은 학교의 모든 문으로 TMAP 보행경로 요청
2. 성공한 경로 중 TMAP 도보거리가 가장 짧은 문 선택
3. 경로를 10m 간격으로 표본화
4. 각 표본점을 20m 이내의 가장 가까운 OSM 엣지에 연결
5. 경로별 OSM 매칭률과 매칭 엣지 수 확인
6. 매칭 엣지에 경사·횡단보도·음향신호기·사고위험 결합

정문만 분석하고 싶을 때는 목적지를 정문으로 고정할 수 있다. 기본 비교에서는 특정 문을 미리 강제하지 않고 모든 문 중 실제 보행거리가 가장 짧은 문을 선택한다."""),
    code("tmap-ready-code", """load_dotenv('.env')
load_dotenv('.env.tmap')
has_tmap_key = bool(os.getenv('TMAP_APP_KEY'))
planned_calls = sum(len(origins[origins['학교'].eq(s)]) * len(gates_tmap[gates_tmap['학교'].eq(s)]) for s in tcp.SCHOOLS)
print('TMAP_APP_KEY:', '설정됨' if has_tmap_key else '미설정')
print(f'예상 API 호출: {planned_calls:,}회')
print('실행 원칙: TMAP 원본 경로는 메모리에서만 처리하고 24시간 이상 저장하지 않음')"""),
    code("tmap-run-code", """# 전체 호출은 명시적으로 True로 바꿀 때만 실행한다.
RUN_TMAP = False
if not has_tmap_key:
    print('대기: .env에 TMAP_APP_KEY를 추가해야 TMAP 보행경로 검증을 실행할 수 있습니다.')
elif not RUN_TMAP:
    print('다시 조회하려면 RUN_TMAP=True로 바꾸세요.')
else:
    routes_24h = tcp.run_all_routes(origins)              # 모든 출발지 × 모든 문
    chosen_24h = tcp.choose_nearest_gate(routes_24h)      # 출발지별 최단 보행거리 문
    matched_edges, match_summary = tcp.match_routes_to_osm(chosen_24h)
    display(chosen_24h[['학교','출발지명','문','distance_m','time_s','expires_at']].head())
    display(match_summary.groupby('학교').agg(경로수=('출발지명','size'), 평균_OSM매칭률=('매칭률_pct','mean')).round(1))"""),
    md("tmap-status", """## D-3. 현재 상태와 다음 실행

| 단계 | 상태 |
|---|---|
| 출발지 규칙·후보 CSV | 완료 |
| 학교별 출입문 좌표 | 완료 |
| TMAP 모든 문 경로 요청 코드 | 완료 |
| 최단 보행거리 문 선택 코드 | 완료 |
| TMAP 경로 → OSM 엣지 매칭 코드 | 완료 |
| 실제 TMAP 호출 | **키 입력 대기** |
| 경사·횡단보도·음향신호기·사고위험 결합 | TMAP 경로 매칭 후 진행 |

TMAP API 결과는 약관상 저장 후 24시간 이상 사용할 수 없으므로, 원본 경로 GeoJSON을 장기 산출물로 저장하지 않는다. 재현 가능한 출발지·문 정의와 OSM 위험도 데이터는 별도로 유지하고, TMAP 경로는 실행 시점의 검증 레이어로 사용한다."""),
]


def main():
    notebook = nbformat.read(PATH, as_version=4)
    notebook.cells = [c for c in notebook.cells if not str(c.get('id', '')).startswith('tmap-')]
    temp = nbformat.v4.new_notebook(cells=cells, metadata=notebook.metadata)
    NotebookClient(temp, timeout=300, kernel_name='python3', resources={'metadata': {'path': str(ROOT)}}).execute()
    notebook.cells.extend(temp.cells)
    nbformat.validate(notebook)
    nbformat.write(notebook, PATH)
    print(f'updated {PATH.name}: +{len(cells)} cells')


if __name__ == '__main__':
    main()
