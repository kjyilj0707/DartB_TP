"""최종 통학로 인터랙티브 지도를 Colab 공유용 노트북 하나로 묶는다. API 호출 없음.

지도는 셀 출력으로 저장되므로 Colab에서 열자마자 실행 없이 보인다. 다시 실행할 때는
같은 폴더의 option_a_commute_map.html을 Colab에 업로드해야 한다.
"""

import base64
from pathlib import Path

import nbformat

ROOT = Path(__file__).parent
MAP = ROOT / "figures" / "option_a" / "option_a_commute_map.html"
OUT = ROOT / "통학로_최종지도_공유.ipynb"


def iframe(html: str) -> str:
    encoded = base64.b64encode(html.encode("utf-8")).decode("ascii")
    return (
        '<iframe src="data:text/html;charset=utf-8;base64,' + encoded + '" '
        'style="width:100%;height:720px;border:none"></iframe>'
    )


def main():
    html = MAP.read_text(encoding="utf-8")
    intro = nbformat.v4.new_markdown_cell(
        """# 중앙대·숭실대 최종 통학로 지도 (Option A)

- **범위**: 각 학교 Kakao 대표점 반경 800m, 학교 밖 OSM 보행망
- **출발지**: 150m 격자별 임의 좌표를 OSM 보행 노드에 스냅한 153개(숭실대 79, 중앙대 74)
- **경로**: 출발 노드마다 OSM 보행거리상 가장 가까운 문까지 TMAP 실제 보행경로 1개(153건 모두 성공)
- **validated**: TMAP 경로가 지나간 OSM 엣지. 선이 굵고 진할수록 지난 경로가 많음
- **bridged(주황)**: validated 조각 사이 15m 이하 간격을 OSM 최단경로로 이은 엣지
- **unobserved(회색, 기본 숨김)**: 이번 153개 경로에 나타나지 않은 엣지. 보행 불가라는 뜻이 아님
- **분석망 = validated + bridged**: 숭실대 315개 엣지·22.9km, 중앙대 280개 엣지·23.4km

오른쪽 위 레이어 창에서 배경지도와 레이어를 바꿀 수 있고, 선에 마우스를 올리면 상태·지난 경로 수·도로명·길이가 보인다.
경사·횡단보도·음향신호기·사고위험 변수는 아직 결합하지 않았다(팀 논의 후 결정)."""
    )
    code = nbformat.v4.new_code_cell(
        """# 아래 지도는 저장된 출력이라 실행하지 않아도 보인다.
# 다시 실행하려면 option_a_commute_map.html을 Colab 왼쪽 '파일'에 업로드한 뒤 실행한다.
import base64
from IPython.display import HTML

html = open('option_a_commute_map.html', encoding='utf-8').read()
src = 'data:text/html;charset=utf-8;base64,' + base64.b64encode(html.encode('utf-8')).decode('ascii')
HTML(f'<iframe src="{src}" style="width:100%;height:720px;border:none"></iframe>')"""
    )
    code.execution_count = 1
    code.outputs = [nbformat.v4.new_output(
        "execute_result", data={"text/html": iframe(html), "text/plain": "<IPython.core.display.HTML object>"},
        execution_count=1,
    )]
    nb = nbformat.v4.new_notebook(cells=[intro, code])
    nb.metadata["colab"] = {"name": OUT.name, "provenance": []}
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3"}
    nbformat.validate(nb)
    nbformat.write(nb, OUT)
    print(OUT, f"{OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
