"""통학로규정 노트북에 최종 Option A 구조와 준비 결과를 반영한다."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).parent
PATH = ROOT / "통학로규정.ipynb"
PREFIX = "option-a-"


def cells():
    return [
        nbformat.v4.new_markdown_cell(
            """# F. 최종 구조 수정 — OSM 후보 엣지를 TMAP 실제 경로로 필터링

앞의 D·E는 **대중교통 출발지로 TMAP→OSM 정합 가능성을 확인한 예비 실험**이다. 최종 분석의 목적은 TMAP으로 출발지를 정의하는 것이 아니라, **OSM이 만든 후보 도로 중 실제 TMAP 도보경로에서 관측되는 엣지만 남기는 것**이다.

최종 기준은 다음과 같다.

1. 학교 범위: OSM 캠퍼스 폴리곤
2. 출입문 좌표: OSM 보행로와 캠퍼스 경계의 교차점
3. 출발지: 800m 학교 밖 영역의 층화 임의 좌표
4. 임의 좌표를 `ox.distance.nearest_nodes`로 OSM 보행 노드에 스냅
5. 스냅된 출발 노드에서 OSM 보행거리상 최근접 문을 결정
6. 동일 출발 노드·OSM 문으로 TMAP 실제 보행경로 요청
7. TMAP 경로를 OSM 엣지에 매칭하고 `validated` / `unobserved`로 분류
8. 본 분석은 `validated` 엣지와 15m 이하 간격을 OSM으로 이은 `bridged` 엣지를 사용하고, `unobserved`는 검토용으로 보존

> TMAP에 한 번도 선택되지 않은 엣지는 ‘보행 불가’로 단정하지 않고 ‘현재 표본에서 미관측’으로 기록한다.
""",
            id="option-a-intro",
        ),
        nbformat.v4.new_code_cell(
            """import pandas as pd
from IPython.display import display

osm_gates = pd.concat([
    pd.read_csv('data/soongsil_osm_gates.csv').assign(학교='숭실대'),
    pd.read_csv('data/chungang_osm_gates.csv').assign(학교='중앙대'),
], ignore_index=True)
option_a = pd.read_csv('data/option_a_origins_with_osm_gate.csv')

display(osm_gates[['학교', '문', 'lat', 'lon', 'osm_way_id', 'highway', 'seed_distance_m']])
display(option_a.groupby(['학교', 'OSM_최근접_문']).agg(
    표본수=('node', 'size'), 평균스냅거리_m=('snap_distance_m', 'mean'),
    최대스냅거리_m=('snap_distance_m', 'max'), 평균문거리_m=('OSM_문까지_m', 'mean')
).round(1))
print(f'중복 제거 후 총 표본 노드: {len(option_a)}개')
print(f'기본 TMAP 호출: {len(option_a)}회 (2026-09-23 실행 완료, 아래 F-2)')""",
            id="option-a-summary",
        ),
        nbformat.v4.new_code_cell(
            """from IPython.display import Image, display
display(Image(filename='figures/option_a/option_a_random_origins_osm_gates.png'))""",
            id="option-a-map",
        ),
        nbformat.v4.new_markdown_cell(
            """## F-1. 준비 결과와 실행 경계

- OSM 출입문: 숭실대 5개, 중앙대 3개
- 150m 격자별 임의점 생성 후 OSM 노드 중복 제거: 숭실대 79개, 중앙대 74개, 총 153개
- 문 진입 노드: 2단계 네트워크의 `gate_connector` 노드를 사용한다. 단순 최근접 노드로 붙이면 숭실대 정문이 1.6m 차이로 389m 막다른 footway 끝 노드에 붙어(실제 진입 노드와 보행망상 840m) 정문 배정이 0개가 되는 오류가 있었다(2026-09-23 수정). 수정 후 숭실대 24개 표본이 북문 10·중문 14에서 정문으로 옮겨졌고, 중앙대 배정은 변화 없음
- 기본 실행: 출발 노드당 OSM 최근접 문 1개를 TMAP으로 검증하므로 153회 호출
- TMAP 요청 한 건이 실패해도 전체 실행이 멈추지 않고 오류를 기록한 뒤 계속 진행
- 모든 문 비교 모드는 617회가 필요하지만 엣지 필터 목적에는 기본 모드를 우선 사용
- 실제 API 호출은 `run_option_a_tmap_filter.py --execute --confirm-calls 153`처럼 호출 수를 명시적으로 확인해야만 가능
- 원본 TMAP geometry는 저장하지 않고 OSM 엣지별 관측 경로 수와 집계만 저장

이 섹션의 셀은 저장된 로컬 자료만 읽으며 TMAP·Kakao·OSM API를 호출하지 않는다.
""",
            id="option-a-status",
        ),
        nbformat.v4.new_markdown_cell(
            """## F-2. TMAP 필터 실행 결과 (153회, 2026-09-23)

사용자 승인 후 `run_option_a_tmap_filter.py --execute --confirm-calls 153`으로 153회를 요청했고 153건 모두 성공했다. 원본 TMAP geometry는 저장하지 않았고 경로별 매칭 요약과 OSM 엣지별 관측 경로 수만 남겼다.

**간격 보정(bridged):** 10m 표본이 짧은 연결 엣지를 건너뛰거나 평행 엣지에 붙어 validated 엣지가 숭실대 14조각, 중앙대 13조각으로 끊겼다. 대부분 0.6–13m 간격이었으므로, 다른 조각까지 OSM 보행망 최단거리가 **15m 이하**인 경우만 그 경로 엣지를 `bridged`로 추가했다. 분석망 = `validated` + `bridged`. 15m를 넘는 간격(숭실대 18.9·67.5m, 중앙대 42.7·105.2m 등)은 TMAP이 OSM에 없는 길을 썼을 가능성이 있어 잇지 않고 한계로 남긴다.
""",
            id="option-a-result-intro",
        ),
        nbformat.v4.new_code_cell(
            """import geopandas as gpd
import networkx as nx

route_summary = pd.read_csv('data/option_a_tmap_route_match_summary.csv')
display(route_summary.groupby('학교').agg(
    경로수=('origin_id', 'size'), TMAP거리_중앙값_m=('TMAP거리_m', 'median'),
    매칭률_평균=('매칭률_pct', 'mean'), 매칭률_최소=('매칭률_pct', 'min'),
    매칭률90미만=('매칭률_pct', lambda s: int((s < 90).sum())),
).round(1))

rows = []
for school, slug in [('숭실대', 'soongsil'), ('중앙대', 'chungang')]:
    e = gpd.read_file(f'data/{slug}_tmap_validated_network.gpkg', layer='all_edges')
    status = e['validation_status'].value_counts()
    def n_comp(frame):
        return nx.number_connected_components(nx.from_pandas_edgelist(frame, 'u', 'v'))
    rows.append({
        '학교': school, '전체엣지': len(e),
        'validated': status.get('validated', 0), 'bridged': status.get('bridged', 0),
        'unobserved': status.get('unobserved', 0),
        '분석망_km': round(e.loc[e['analysis_edge'], 'length'].sum() / 1000, 1),
        '전체_km': round(e['length'].sum() / 1000, 1),
        '경로1개만_지난_엣지': int(e['tmap_hit_routes'].eq(1).sum()),
        '조각수_보정전': n_comp(e[e['validation_status'].eq('validated')]),
        '조각수_보정후': n_comp(e[e['analysis_edge']]),
    })
display(pd.DataFrame(rows).set_index('학교'))
display(pd.read_csv('data/option_a_bridged_gaps.csv'))""",
            id="option-a-result-summary",
        ),
        nbformat.v4.new_code_cell(
            """display(Image(filename='figures/option_a/option_a_tmap_validated_edges.png'))""",
            id="option-a-result-map",
        ),
        nbformat.v4.new_markdown_cell(
            """## F-3. 해석 시 주의

- `unobserved`는 153개 표본 경로에 나타나지 않았다는 뜻일 뿐 보행 불가를 뜻하지 않는다.
- 매칭은 표본점마다 20m 안의 최근접 엣지 하나를 쓰므로, 교차로에서 옆 골목의 짧은 구간이 경로 1개로 validated될 수 있다(지도에서 본선 옆 짧은 가지). 경로 1개만 지난 엣지는 숭실대 137개, 중앙대 117개다.
- 문과 거의 붙은 출발지 3개(숭실대)는 1–6m 경로라 정보가 거의 없다.
- TMAP 거리/OSM 문까지 거리 비율은 중앙값 1.05이며, 6개 경로는 0.67–1.5 밖이다.
""",
            id="option-a-caveats",
        ),
    ]


def main():
    notebook = nbformat.read(PATH, as_version=4)
    notebook.cells = [c for c in notebook.cells if not str(c.get("id", "")).startswith(PREFIX)]

    for cell in notebook.cells:
        if cell.get("id") == "commute-title":
            cell.source = cell.source.replace(
                "4. **통학 구간**: 원 안·학교 밖 노드에서 보행거리상 가장 가까운 문까지의 최단경로",
                "4. **후보 통학망**: OSM 학교 밖 보행 엣지\n5. **최종 통학 구간**: 800m 임의점을 OSM 노드에 스냅한 뒤 TMAP 실제 경로에서 관측된 OSM 엣지",
            )
        if cell.get("id") == "tmap-intro":
            cell.source = cell.source.replace(
                "# D. TMAP 실제 도보 경로 검증 파이프라인",
                "# D. 예비 실험 — 대중교통 출발지 TMAP·OSM 정합 검증",
            )
        if cell.get("id") == "commute-viz-intro":
            cell.source = cell.source.replace(
                "# E. 확보한 통학로 구간 시각화",
                "# E. 예비 실험 결과 시각화",
            )

    section = nbformat.v4.new_notebook(cells=cells(), metadata=notebook.metadata)
    NotebookClient(section, timeout=120, kernel_name="python3",
                   resources={"metadata": {"path": str(ROOT)}}).execute()
    notebook.cells.extend(section.cells)
    nbformat.validate(notebook)
    nbformat.write(notebook, PATH)
    print(f"updated {PATH} ({len(notebook.cells)} cells)")


if __name__ == "__main__":
    main()
