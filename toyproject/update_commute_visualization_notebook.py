"""Append the finalized commute-route visualization section to the focused notebook."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).parent
NOTEBOOK = ROOT / "통학로규정.ipynb"
CELL_PREFIX = "commute-viz-"


def build_cells():
    return [
        nbformat.v4.new_markdown_cell(
            """# E. 확보한 통학로 구간 시각화

아래 그림은 **TMAP 보행경로 검증 결과**와 **OSM 통학로 회랑**을 한 화면에서 비교한다.

- 지도 선의 **색**: 연결되는 학교 출입문
- 지도 선의 **굵기**: OSM 최단경로 중첩수(많이 겹칠수록 굵음)
- 작은 원: 버스정류장, 큰 사각형: 지하철 출구, 삼각형: 학교 출입문
- 하단 차트: TMAP이 선택한 출입문 수와 출발지별 평균 거리·시간
""",
            id="commute-viz-intro",
        ),
        nbformat.v4.new_code_cell(
            """from IPython.display import Image, display

display(Image(filename='figures/commute_routes/tmap_validated_commute_corridors.png'))""",
            id="commute-viz-static",
        ),
        nbformat.v4.new_markdown_cell(
            """## E-1. 읽는 방법과 해석

**TMAP 검증 요약**

| 학교 | 출발지 수 | TMAP 선택 출입문 | 평균 거리 | 평균 시간 | TMAP→OSM 평균 정합률 |
|---|---:|---|---:|---:|---:|
| 숭실대 | 48 | 정문 12 · 중문 13 · 후문 13 · 남문 7 · 북문 3 | 461.4 m | 6.2분 | 99.9% |
| 중앙대 | 73 | 정문 46 · 중문 2 · 후문 25 | 682.6 m | 8.8분 | 100.0% |

출발지마다 가장 가까운 문이 달라지므로 정문 하나만 목적지로 고정하는 것보다, 모든 확인된 출입문에 대해 TMAP 보행거리를 비교하는 구조가 실제 통학 흐름을 더 잘 반영한다. 특히 중앙대는 정문 선택이 우세하지만 후문으로 연결되는 출발지도 25곳으로 적지 않다.

> **표현 범위:** TMAP 원본 경로 좌표는 보관 제한을 고려해 집계 후 폐기했다. 따라서 지도에 그려진 선은 개별 TMAP 원본 선이 아니라, TMAP 경로와 평균 99.9~100% 정합한 **OSM 기반 통학로 회랑**이다. 정확한 개별 TMAP 경로를 재현한 그림으로 해석하면 안 된다.

인터랙티브 지도에서는 학교별 회랑·출발지·출입문 레이어를 켜고 끌 수 있으며, 선을 가리키면 담당 문, 중첩수, 도로 유형과 도로명을 확인할 수 있다.
""",
            id="commute-viz-notes",
        ),
        nbformat.v4.new_code_cell(
            """from IPython.display import IFrame, display

display(IFrame(src='figures/commute_routes/tmap_validated_commute_corridors.html', width='100%', height=720))""",
            id="commute-viz-interactive",
        ),
    ]


def main():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    notebook.cells = [
        cell for cell in notebook.cells
        if not str(cell.get("id", "")).startswith(CELL_PREFIX)
    ]

    section = nbformat.v4.new_notebook(
        cells=build_cells(),
        metadata=notebook.metadata,
    )
    NotebookClient(
        section,
        timeout=120,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    ).execute()
    notebook.cells.extend(section.cells)
    nbformat.validate(notebook)
    nbformat.write(notebook, NOTEBOOK)
    print(f"updated: {NOTEBOOK} ({len(notebook.cells)} cells)")


if __name__ == "__main__":
    main()
