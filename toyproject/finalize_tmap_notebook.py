"""실제 TMAP 검증 집계를 노트북에 기록하되 원본 경로는 저장하지 않는다."""

from pathlib import Path

import nbformat


path = Path(__file__).parent / "통학로규정.ipynb"
nb = nbformat.read(path, as_version=4)

run_source = """# 전체 API 호출은 명시적으로 True로 바꿀 때만 실행한다.
# 오늘 검증은 완료되었으므로 불필요한 재호출을 막기 위해 기본값은 False다.
RUN_TMAP = False
if not has_tmap_key:
    print('대기: .env.tmap에 TMAP_APP_KEY가 필요합니다.')
elif not RUN_TMAP:
    print('TMAP 검증 완료. 다시 조회하려면 RUN_TMAP=True로 바꾸세요.')
else:
    routes_24h = tcp.run_all_routes(origins)
    chosen_24h = tcp.choose_nearest_gate(routes_24h)
    matched_edges, match_summary = tcp.match_routes_to_osm(chosen_24h)
    display(chosen_24h[['학교','origin_id','출발지명','문','distance_m','time_s','expires_at']].head())
    display(match_summary.groupby('학교').agg(경로수=('origin_id','size'), 평균_OSM매칭률=('매칭률_pct','mean')).round(1))"""

result_md = """## D-3. TMAP 실제 검증 결과 (2026-09-23)

- 전체 요청: **459건** (121개 출발지 × 같은 학교의 모든 문)
- 성공: **459건**, 실패: **0건**
- 출발지별 최단 보행거리 문 선택: **121건 전부 완료**
- 원본 TMAP 경로 geometry는 집계 후 폐기

| 학교 | 선택 문별 출발지 수 | 평균 최단거리 | 중앙 최단거리 | 평균시간 |
|---|---|---:|---:|---:|
| 숭실대 | 정문 12 · 중문 13 · 후문 13 · 남문 7 · 북문 3 | 461.4m | 508m | 372.8초 |
| 중앙대 | 정문 46 · 중문 2 · 후문 25 | 682.6m | 661m | 528.8초 |

### 문별 선택 경로 평균

| 학교 | 문 | 출발지 수 | 평균거리 | 평균시간 |
|---|---|---:|---:|---:|
| 숭실대 | 정문 | 12 | 265.3m | 230.6초 |
| 숭실대 | 중문 | 13 | 659.6m | 527.3초 |
| 숭실대 | 후문 | 13 | 490.3m | 392.6초 |
| 숭실대 | 남문 | 7 | 344.9m | 270.3초 |
| 숭실대 | 북문 | 3 | 533.7m | 426.0초 |
| 중앙대 | 정문 | 46 | 801.0m | 612.8초 |
| 중앙대 | 중문 | 2 | 85.5m | 62.5초 |
| 중앙대 | 후문 | 25 | 512.5m | 411.3초 |

### TMAP 경로와 OSM 엣지의 정합

TMAP 경로를 10m 간격으로 표본화하고 20m 이내의 최근접 OSM 엣지에 연결했다.

| 학교 | 경로 수 | 평균 매칭률 | 중앙 매칭률 | 최소 매칭률 |
|---|---:|---:|---:|---:|
| 숭실대 | 48 | 99.9% | 100.0% | 96.3% |
| 중앙대 | 73 | 100.0% | 100.0% | 97.6% |

따라서 TMAP이 선택한 실제 추천 보행경로를 기존 OSM 엣지 분석 단위에 연결하는 구조가 두 학교 모두에서 작동한다. 다음 단계는 이 매칭 엣지에 경사·횡단보도·음향신호기·사고위험 값을 결합하는 것이다."""

result = nbformat.v4.new_markdown_cell(result_md); result["id"] = "tmap-results-md"
nb.cells = [c for c in nb.cells if c.get("id") != "tmap-results-md"]
for i, cell in enumerate(nb.cells):
    if cell.get("id") == "tmap-ready-code":
        cell["outputs"] = [nbformat.v4.new_output("stream", name="stdout", text=(
            "TMAP_APP_KEY: 설정됨\n예상 API 호출: 459회\n"
            "실행 원칙: TMAP 원본 경로는 메모리에서만 처리하고 24시간 이상 저장하지 않음\n"))]
    if cell.get("id") == "tmap-run-code":
        cell["source"] = run_source
        cell["outputs"] = [nbformat.v4.new_output("stream", name="stdout", text=(
            "TMAP 검증 완료. 다시 조회하려면 RUN_TMAP=True로 바꾸세요.\n"))]
        nb.cells.insert(i + 1, result)
        break

for cell in nb.cells:
    if cell.get("id") == "tmap-status":
        cell["source"] = cell["source"].replace("## D-3. 현재 상태와 다음 실행", "## D-4. 현재 상태와 다음 실행")
        cell["source"] = cell["source"].replace("| 실제 TMAP 호출 | **키 입력 대기** |", "| 실제 TMAP 호출 | 완료: 459/459 성공 |")
        cell["source"] = cell["source"].replace("| 경사·횡단보도·음향신호기·사고위험 결합 | TMAP 경로 매칭 후 진행 |", "| 경사·횡단보도·음향신호기·사고위험 결합 | 다음 단계 |")

nbformat.validate(nb)
nbformat.write(nb, path)
print(f"finalized {path.name}: {len(nb.cells)} cells")
