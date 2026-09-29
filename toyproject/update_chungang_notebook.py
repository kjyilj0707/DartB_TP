"""06 노트북의 3단계 앞에 중앙대 1·2단계를 추가하고 새 셀만 실행한다."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).parent
NOTEBOOK = ROOT / "06_숭실대_반경_1-3단계.ipynb"


def md(cell_id, source):
    cell = nbformat.v4.new_markdown_cell(source)
    cell["id"] = cell_id
    return cell


def code(cell_id, source):
    cell = nbformat.v4.new_code_cell(source)
    cell["id"] = cell_id
    return cell


cells = [
    md("cau-1-intro", """---
## 중앙대 1. 대학가 규정 (숭실대와 같은 기준)

비교가 어긋나지 않도록 중앙대도 숭실대와 똑같이 **카카오 학교 대표점 중심 반경 800m**를 대학가로 본다. 학교 범위는 OSM 캠퍼스 폴리곤, 출입문은 공식 안내에서 이름을 확인한 카카오 좌표(정문·중문·후문)를 쓴다.

- 계산 좌표계: EPSG:5186(미터)
- 저장·표시 좌표계: EPSG:4326
- 기존 중앙대 분석의 OSM 정문 기준점은 비교표에 남겨 기준 변경의 영향을 확인한다."""),
    code("cau-1-setup", """import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import Point
from shapely.ops import unary_union
from pathlib import Path

import chungang_config as ccfg
import chungang_network as cn
import viz_campus_definition as viz

DATA_DIR = Path('data')

cau_center = viz.to_proj(Point(ccfg.CENTER_LON, ccfg.CENTER_LAT))
cau_circle = cau_center.buffer(ccfg.RADIUS_M)
cau_campus = viz.to_proj(cn.load_campus_polygon())
cau_gates_ll = cn.load_gates_ll()
cau_gates = cn.load_gates()

print(f'중앙대 카카오 대표점: {ccfg.CENTER_LAT:.7f}, {ccfg.CENTER_LON:.7f}')
print(f'반경: {ccfg.RADIUS_M}m | 캠퍼스 OSM ID: {cn.OSM_RELATION_ID}')"""),
    md("cau-1-2-md", """### 중앙대 1-2. 후보 지점 비교 (대표점·정문·출입구)

카카오 대표점, 공식 명칭이 확인된 카카오 출입문 3곳, 기존 분석의 OSM 정문을 같은 표에서 비교한다. 거리와 800m 원의 겹침(IoU)은 EPSG:5186에서 계산한다."""),
    code("cau-1-2-code", """rows = [{'후보': 'KAKAO 대표점', '장소명': '중앙대학교 서울캠퍼스', 'lat': ccfg.CENTER_LAT, 'lon': ccfg.CENTER_LON}]
rows += [{'후보': f'KAKAO {r.문}', '장소명': f'중앙대학교 서울캠퍼스 {r.문}', 'lat': r.lat, 'lon': r.lon}
         for r in cau_gates_ll.itertuples()]
rows += [{'후보': '기존 OSM 정문', '장소명': '중앙대학교 정문(기존 기준점)',
          'lat': ccfg.OLD_MAIN_GATE_LAT, 'lon': ccfg.OLD_MAIN_GATE_LON}]
cau_candidates = pd.DataFrame(rows)
cau_points = gpd.GeoSeries([Point(r.lon, r.lat) for r in cau_candidates.itertuples()], crs='EPSG:4326').to_crs('EPSG:5186')
ref = cau_points.iloc[0]
cau_candidates['대표점과의거리_m'] = [round(p.distance(ref), 1) for p in cau_points]
base_circle = ref.buffer(ccfg.RADIUS_M)
cau_candidates['대표점_원과_IoU'] = [round(p.buffer(ccfg.RADIUS_M).intersection(base_circle).area /
                                           p.buffer(ccfg.RADIUS_M).union(base_circle).area, 3) for p in cau_points]
cau_candidates.to_csv(DATA_DIR / 'chungang_center_candidates.csv', index=False, encoding='utf-8-sig')
display(cau_candidates)"""),
    md("cau-1-3-md", """### 중앙대 1-3. 학교 범위 규정 — 카카오 문 좌표 + OSM 캠퍼스 폴리곤

공식 안내에서 확인되는 중앙대 서울캠퍼스 문은 정문·중문·후문 3곳이다. 병원 문과 부속학교 문은 캠퍼스 문에서 제외한다. 아래에서 문 좌표가 OSM 경계와 얼마나 가까운지 확인한다."""),
    code("cau-1-3-code", """cau_campus_ll = gpd.GeoSeries([cau_campus], crs='EPSG:5186').to_crs('EPSG:4326').iloc[0]
cau_circle_ll = gpd.GeoSeries([cau_circle], crs='EPSG:5186').to_crs('EPSG:4326').iloc[0]
gate_rows = []
for name, p in cau_gates.items():
    gate_rows.append({'문': name, 'lat': float(cau_gates_ll.loc[cau_gates_ll['문'].eq(name), 'lat'].iloc[0]),
                      'lon': float(cau_gates_ll.loc[cau_gates_ll['문'].eq(name), 'lon'].iloc[0]),
                      '폴리곤': '안' if cau_campus.covers(p) else '밖', '경계까지_m': round(p.distance(cau_campus.boundary), 1),
                      '기준점과의거리_m': round(p.distance(cau_center))})
cau_gate_table = pd.DataFrame(gate_rows).sort_values('경계까지_m')
display(cau_gate_table)
print(f'캠퍼스 폴리곤: {cau_campus.area / 1e4:.1f}ha')
print(f'대학가 영역(반경 800m): {cau_circle.area / 1e6:.2f}km², 그중 캠퍼스 {cau_campus.intersection(cau_circle).area / cau_circle.area * 100:.1f}%')

mc = folium.Map(location=[ccfg.CENTER_LAT, ccfg.CENTER_LON], zoom_start=15, tiles='OpenStreetMap')
folium.GeoJson(cau_circle_ll.__geo_interface__, style_function=lambda _: {'color': '#2563eb', 'weight': 2, 'fillOpacity': 0.03}, tooltip='대학가 영역 800m').add_to(mc)
folium.GeoJson(cau_campus_ll.__geo_interface__, style_function=lambda _: {'color': '#1d4ed8', 'weight': 2, 'fillColor': '#60a5fa', 'fillOpacity': 0.3}, tooltip='OSM 캠퍼스 폴리곤').add_to(mc)
for r in cau_gate_table.itertuples():
    folium.CircleMarker([r.lat, r.lon], radius=6, color='#dc2626', fill=True, fill_opacity=.9,
                        tooltip=f'카카오 {r.문} | 경계까지 {r.경계까지_m}m').add_to(mc)
folium.Marker([ccfg.CENTER_LAT, ccfg.CENTER_LON], tooltip='카카오 중앙대학교 서울캠퍼스 대표점', icon=folium.Icon(color='blue')).add_to(mc)
mc"""),
    md("cau-1-4-md", """### 중앙대 1-4. 학교 범위 규정 방식 비교 — 단순 반경 vs 폴리곤

숭실대 1-4와 같은 네 지표로 비교한다. 문 주변 원은 캠퍼스 모양을 근사하는 방식이고, OSM 폴리곤은 학교 안쪽 엣지를 제외하기 위한 기준이다."""),
    code("cau-1-4-code", """cau_walk_edges = cn.load_walk_edges()
cau_r_cover = viz.cover_radius(list(cau_gates.values()), cau_campus)
cau_regions = {'반경 100m': viz.union_of_circles(list(cau_gates.values()), 100),
               f'반경 {cau_r_cover:.0f}m (캠퍼스 99% 덮는 최소 반경)': viz.union_of_circles(list(cau_gates.values()), cau_r_cover),
               '폴리곤 (OSM 캠퍼스)': cau_campus}
cau_compare = pd.DataFrame({k: viz.evaluate(v, cau_campus, cau_walk_edges) for k, v in cau_regions.items()}).T.round(1)
display(cau_compare)

bx0, by0, bx1, by1 = unary_union(list(cau_regions.values())).bounds
extent = (bx0 - 40, by0 - 40, bx1 + 40, by1 + 40)
fig, axes = plt.subplots(1, 3, figsize=(19, 6.5))
for ax, (name, region) in zip(axes, cau_regions.items()):
    r = cau_compare.loc[name]
    title = (f\"{name}\\n커버율 {r['캠퍼스 커버율(%)']:.0f}% | 학교 밖 초과 {r['학교 밖 초과 면적(ha)']:.1f}ha\\n\"
             f\"학교 밖인데 제외되는 보행망 {r['학교 밖인데 제외되는 보행망(m)']:.0f}m | 학교 안인데 남는 보행망 {r['학교 안인데 통학로로 남는 보행망(m)']:.0f}m\")
    viz.draw_map(ax, title, cau_walk_edges, cau_campus, extent, None if region is cau_campus else region,
                 gates=cau_gates, gate_color='#ea580c')
fig.suptitle('중앙대 학교 범위 규정 방식 비교 — 숭실대와 같은 규칙', fontsize=14)
plt.tight_layout(rect=(0, 0, 1, .94)); plt.show()"""),
    md("cau-1-summary", """### 중앙대 1단계 정리

- 비교 기준을 통일해 **카카오 ‘중앙대학교 서울캠퍼스’ 대표점 + 반경 800m**를 사용한다.
- 학교 범위는 OSM 캠퍼스 폴리곤, 출입문은 공식 명칭이 확인된 카카오 정문·중문·후문 좌표다.
- 기존 중앙대 정문 기준 분석과 중심점이 다르므로, 기존 1km 결과와 이번 비교용 800m 결과를 혼용하지 않는다."""),
    md("cau-2-intro", """---
## 중앙대 2. 구간·거리 규정

숭실대와 같은 규칙으로 OSM 보행망을 만든다. 800m 원보다 150m 넓게 받은 뒤 캠퍼스 내부 비율이 50% 이상인 엣지를 제거하고, 각 문을 가장 가까운 외부 노드에 가상 연결한다. 원 안·학교 밖 노드에서 보행거리상 가장 가까운 문까지의 최단경로와 엣지별 최단경로 중첩수를 계산한다."""),
    code("cau-2-run", """cau_res = cn.run()
cau_nodes, cau_edges, cau_removed = cau_res['nodes'], cau_res['edges'], cau_res['removed']
cau_origins = cau_nodes[cau_nodes['출발노드']]
cau_ein = cau_edges[cau_edges['원_안'] & (cau_edges['highway'] != 'gate_connector')]
print(f\"OSM 보행망(원+150m): 노드 {len(cau_res['G_full']):,}, 엣지 {cau_res['G_full'].number_of_edges():,}\")
print(f\"학교 내부 엣지 제거: {len(cau_removed)}개, {cau_removed.geometry.length.sum():,.0f}m -> 남은 노드 {len(cau_res['G_cut']):,}, 엣지 {cau_res['G_cut'].number_of_edges():,}\")
print(f\"연결 요소 수: {nx.number_connected_components(cau_res['G_cut'])}\")
print(f\"출발 노드: {len(cau_origins)}개, 문에 도달 못 하는 노드: {cau_origins['가까운_문'].isna().sum()}개\")
display(cau_res['gate_table'])

cau_by_gate = cau_origins.groupby('가까운_문').agg(노드수=('node', 'size'), 평균_보행거리_m=('문까지_보행_m', 'mean'), 최대_보행거리_m=('문까지_보행_m', 'max')).round(0)
cau_by_gate['엣지수(원 안)'] = cau_ein.groupby('소속_문').size()
cau_by_gate['엣지길이_km'] = (cau_ein.assign(l=cau_ein.geometry.length).groupby('소속_문')['l'].sum() / 1000).round(2)
display(cau_by_gate.sort_values('노드수', ascending=False))
mis = cau_origins['가까운_문'] != cau_origins['직선_최근접_문']
close = cau_origins['1-2순위_차이_m'] < 50
print(f'직선 최근접 문과 보행 최근접 문이 다른 노드: {mis.sum()}개 / {len(cau_origins)}개 ({mis.mean()*100:.1f}%)')
print(f'1·2순위 문 거리 차이가 50m 미만: {close.sum()}개 ({close.mean()*100:.1f}%)')

cau_colors = {'정문': '#2563eb', '중문': '#dc2626', '후문': '#f59e0b', '경계': '#9ca3af'}
minx, miny, maxx, maxy = cau_res['circle'].bounds
fig, axes = plt.subplots(1, 2, figsize=(19, 9.5))
for ax in axes:
    gpd.GeoSeries([cau_res['campus']]).plot(ax=ax, color='#dbeafe', edgecolor='#1d4ed8', linewidth=1)
    cau_removed.plot(ax=ax, color='#94a3b8', linewidth=.6, linestyle='--')
    gpd.GeoSeries([cau_res['circle']]).boundary.plot(ax=ax, color='#2563eb', linestyle=':', linewidth=1.2)
    for name, p in cau_res['gates'].items():
        ax.plot(p.x, p.y, '^', ms=11, color=cau_colors[name], markeredgecolor='black', zorder=6); ax.annotate(name, (p.x, p.y), xytext=(6,6), textcoords='offset points')
    ax.set(xlim=(minx-20,maxx+20), ylim=(miny-20,maxy+20)); ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
for name in ['정문','중문','후문','경계']:
    sub = cau_ein[cau_ein['소속_문'] == name]
    if len(sub): sub.plot(ax=axes[0], color=cau_colors[name], linewidth=1.8 if name != '경계' else 1.2, label=f'{name} ({len(sub)}개)')
axes[0].legend(loc='lower left'); axes[0].set_title('중앙대 문별 통학 구간')
use = cau_ein.sort_values('최단경로_중첩수'); norm = plt.Normalize(0, np.log1p(use['최단경로_중첩수'].max()))
use.plot(ax=axes[1], color=plt.cm.YlOrRd(norm(np.log1p(use['최단경로_중첩수']))), linewidth=.6 + 3.2*norm(np.log1p(use['최단경로_중첩수'])))
axes[1].set_title('중앙대 최단경로 중첩수 (log 색상)'); plt.tight_layout(); plt.show()

cau_out = cn.save(cau_res)
print('저장:', cau_out.name, '(layers: edges, nodes | EPSG:4326)')"""),
    md("cau-2-summary", """### 중앙대 2단계 정리

- 산출물: `data/chungang_network.gpkg` (`edges`, `nodes`, EPSG:4326).
- 통학 구간의 뜻과 최단경로 중첩수의 한계는 숭실대 2단계와 같다. 실제 통행량이 아니라 원 안 노드들이 가장 가까운 문으로 향한다고 가정한 경로 중첩이다.
- 후문 가상 연결선이 25m를 넘으면 경고로 남긴다. 이는 OSM 보행망 또는 캠퍼스 경계의 누락 가능성을 뜻하므로 현장·지도 확인 대상이다.
- 병원·부속학교 출입구는 중앙대 캠퍼스 문에서 제외했다."""),
]


def main():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    notebook.cells = [c for c in notebook.cells if not str(c.get("id", "")).startswith("cau-")]
    insert_at = next(i for i, c in enumerate(notebook.cells) if c.get("id") == "a214a6b9")

    temp = nbformat.v4.new_notebook(cells=cells, metadata=notebook.metadata)
    NotebookClient(temp, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}).execute()
    notebook.cells[insert_at:insert_at] = temp.cells
    nbformat.write(notebook, NOTEBOOK)
    print(f"updated {NOTEBOOK.name}: +{len(cells)} cells at {insert_at}")


if __name__ == "__main__":
    main()
