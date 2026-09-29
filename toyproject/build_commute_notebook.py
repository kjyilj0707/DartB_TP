"""06 노트북에서 두 학교의 1·2단계와 실행 결과를 통학로규정.ipynb로 묶는다."""

from copy import deepcopy
import base64
from pathlib import Path

import nbformat


ROOT = Path(__file__).parent
SOURCE = ROOT / "06_숭실대_반경_1-3단계.ipynb"
TARGET = ROOT / "통학로규정.ipynb"


def markdown(cell_id, source):
    cell = nbformat.v4.new_markdown_cell(source)
    cell["id"] = cell_id
    return cell


source = nbformat.read(SOURCE, as_version=4)

# 06의 0~18은 숭실대 1·2단계, cau-* 12개 셀은 중앙대 1·2단계다.
soongsil = deepcopy(source.cells[1:19])
chungang = deepcopy([c for c in source.cells if str(c.get("id", "")).startswith("cau-")])

cells = [
    markdown("commute-title", """# 중앙대·숭실대 통학로 규정

두 학교를 같은 규칙으로 비교하기 위한 실행 결과 노트북이다.

1. **대학가 영역**: 카카오 학교 대표점 중심 반경 800m
2. **학교 범위**: OSM 캠퍼스 폴리곤
3. **출입문**: 공식 명칭을 확인한 카카오 입출구 좌표
4. **통학 구간**: 원 안·학교 밖 노드에서 보행거리상 가장 가까운 문까지의 최단경로
5. **최단경로 중첩수**: 각 출발 노드의 최단 통학경로가 엣지에서 겹치는 횟수(실제 통행량은 아님)

거리·면적 계산은 EPSG:5186, 지도와 저장 결과는 EPSG:4326을 사용한다. 아래 셀에는 기존 실행 출력과 지도가 포함되어 있다."""),
    markdown("commute-soongsil", """# A. 숭실대학교

카카오 `숭실대학교` 대표점, 반경 800m, OSM 캠퍼스 폴리곤, 카카오 출입문 5곳을 사용한다."""),
    *soongsil,
    markdown("commute-chungang", """# B. 중앙대학교 서울캠퍼스

비교 기준을 맞추기 위해 기존 중앙대 정문 중심 1km가 아니라, 카카오 `중앙대학교 서울캠퍼스` 대표점 중심 800m로 다시 계산했다."""),
    *chungang,
    markdown("commute-compare", """---
# C. 두 학교 결과 비교

| 항목 | 숭실대 | 중앙대 |
|---|---:|---:|
| 카카오 출입문 | 5개 | 3개 |
| OSM 캠퍼스 면적 | 12.5ha | 14.5ha |
| 원+150m 보행망 노드 / 엣지 | 797 / 1,122 | 696 / 996 |
| 학교 내부 제거 엣지 / 길이 | 71개 / 3,109m | 41개 / 2,580m |
| 제거 후 연결 요소 | 1개 | 1개 |
| 원 안·학교 밖 출발 노드 | 400개 | 333개 |
| 문에 도달 못 하는 노드 | 0개 | 0개 |
| 직선 최근접 문 ≠ 보행 최근접 문 | 60개 (15.0%) | 17개 (5.1%) |
| 1·2순위 문 거리 차이 < 50m | 51개 (12.8%) | 7개 (2.1%) |
| 25m 초과 가상 연결선 | 없음 | 후문 30.2m |
| 저장 파일 | `data/soongsil_network.gpkg` | `data/chungang_network.gpkg` |

두 학교 모두 학교 내부 엣지를 제거한 뒤 외부 보행망이 하나의 연결 요소로 유지되고, 모든 출발 노드가 문에 도달한다. 중앙대 후문의 30.2m 가상 연결선은 OSM 보행망 또는 경계 누락 가능성이 있으므로 별도 확인 대상으로 남긴다.

중앙대의 중문은 보행거리 기준 담당 노드가 5개뿐이다. 이는 문 자체의 중요도가 낮다는 뜻이 아니라, 현재 OSM 외부 보행망·캠퍼스 경계·최단거리 가정 아래에서 중문이 최근접 문인 영역이 작다는 뜻이다."""),
]

notebook = nbformat.v4.new_notebook(cells=cells, metadata=deepcopy(source.metadata))
nbformat.validate(notebook)
nbformat.write(notebook, TARGET)

# 팀 공유용 Notion 페이지에 넣을 핵심 정적 그림을 노트북 출력에서 추출한다.
image_dir = ROOT / "figures" / "notion_commute"
image_dir.mkdir(parents=True, exist_ok=True)
image_cells = {
    "a9e791f5": "01_soongsil_campus_definition.png",
    "27cf3dea": "02_soongsil_commute_routes.png",
    "cau-1-4-code": "03_chungang_campus_definition.png",
    "cau-2-run": "04_chungang_commute_routes.png",
}
for cell in cells:
    filename = image_cells.get(cell.get("id"))
    if not filename:
        continue
    image = next((out["data"]["image/png"] for out in cell.get("outputs", [])
                  if "image/png" in out.get("data", {})), None)
    if image:
        (image_dir / filename).write_bytes(base64.b64decode(image))
print(f"saved {TARGET.name}: {len(cells)} cells")
