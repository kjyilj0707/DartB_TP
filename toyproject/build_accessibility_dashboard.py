import json
import io
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import folium
import geopandas as gpd
import matplotlib
import networkx as nx
import numpy as np
import pandas as pd
from branca.colormap import linear
from folium import Element
from shapely.geometry import LineString

matplotlib.use('Agg')


ROOT = Path(__file__).resolve().parent
NOTEBOOK = ROOT / '05_보조데이터_EDA.ipynb'
OUTPUT = ROOT / '보행_접근성_안전_대시보드.html'


def execute_notebook_code():
    notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    namespace = {'__file__': str(NOTEBOOK), '__name__': '__main__'}
    for cell in notebook['cells']:
        if cell.get('cell_type') != 'code':
            continue
        source = ''.join(cell.get('source', []))
        if source.strip():
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exec(compile(source, str(NOTEBOOK), 'exec'), namespace)
    return namespace


def build_map(ns):
    edge_context = ns['edge_context']
    nearby_audible = ns['nearby_audible']
    nearby_facility = ns['nearby_facility']
    nearby_accident = ns['nearby_accident']
    center_lat = ns['CENTER_LAT']
    center_lon = ns['CENTER_LON']
    radius_m = ns['RADIUS_M']

    edge_map = edge_context[
        ['edge_id', 'length_m', 'slope_pct', 'audible_count',
         'facility_count', 'accident_count', 'priority_score', 'geometry']
    ].to_crs('EPSG:4326')
    score_min = float(edge_map['priority_score'].min())
    score_max = float(edge_map['priority_score'].max())
    if score_min == score_max:
        score_max = score_min + 1
    score_color = linear.YlOrRd_09.scale(score_min, score_max)
    score_color.caption = '보행 구간 개선 우선순위'

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=15,
        tiles='OpenStreetMap',
        control_scale=True,
    )
    folium.Marker(
        [center_lat, center_lon],
        tooltip='청룡연못 기준점',
        icon=folium.Icon(color='blue', icon='info-sign'),
    ).add_to(fmap)
    folium.Circle(
        [center_lat, center_lon],
        radius=radius_m,
        color='#2563eb',
        fill=False,
        tooltip=f'분석 범위 {radius_m:,}m',
    ).add_to(fmap)

    edge_layer = folium.FeatureGroup(name='보행 edge 우선순위', show=True)
    folium.GeoJson(
        edge_map.to_json(),
        style_function=lambda feature: {
            'color': score_color(feature['properties']['priority_score']),
            'weight': 5,
            'opacity': 0.85,
        },
        highlight_function=lambda feature: {
            'weight': 8,
            'opacity': 1.0,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['edge_id', 'slope_pct', 'audible_count',
                    'facility_count', 'accident_count', 'priority_score'],
            aliases=['edge', '경사도(%)', '음향 신호기 수',
                     '편의시설 수', '사고 지점 수', '개선 우선순위'],
            localize=True,
            sticky=False,
            labels=True,
        ),
    ).add_to(edge_layer)
    edge_layer.add_to(fmap)

    signal_layer = folium.FeatureGroup(name='음향 신호기', show=True)
    for _, row in nearby_audible.to_crs('EPSG:4326').iterrows():
        folium.CircleMarker(
            [row.geometry.y, row.geometry.x],
            radius=4,
            color='#16a34a',
            fill=True,
            fill_opacity=0.9,
            tooltip='음향 신호기',
        ).add_to(signal_layer)
    signal_layer.add_to(fmap)

    facility_layer = folium.FeatureGroup(name='장애인 편의시설', show=True)
    for _, row in nearby_facility.to_crs('EPSG:4326').iterrows():
        folium.CircleMarker(
            [row.geometry.y, row.geometry.x],
            radius=3,
            color='#7c3aed',
            fill=True,
            fill_opacity=0.9,
            tooltip='장애인 편의시설',
        ).add_to(facility_layer)
    facility_layer.add_to(fmap)

    accident_layer = folium.FeatureGroup(name='사고 지점', show=True)
    for _, row in nearby_accident.to_crs('EPSG:4326').iterrows():
        folium.CircleMarker(
            [row.geometry.y, row.geometry.x],
            radius=5,
            color='#dc2626',
            fill=True,
            fill_opacity=0.9,
            tooltip='사고 지점',
        ).add_to(accident_layer)
    accident_layer.add_to(fmap)

    score_color.add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)

    total_edges = len(edge_context)
    high_priority = int((edge_context['priority_score'] >= edge_context['priority_score'].quantile(0.9)).sum())
    mean_slope = float(edge_context['slope_pct'].abs().mean())
    max_slope = float(edge_context['slope_pct'].abs().max())
    html = f"""
    <style>
      html, body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; background: #f5f7fb; }}
      .dashboard-header {{ position: fixed; z-index: 9999; top: 14px; left: 60px; right: 60px;
        background: rgba(255,255,255,.96); border: 1px solid #dbe3ef; border-radius: 12px;
        padding: 14px 18px; box-shadow: 0 3px 16px rgba(15,23,42,.12); }}
      .dashboard-title {{ font-size: 20px; font-weight: 700; color: #172033; margin: 0 0 4px; }}
      .dashboard-subtitle {{ color: #5b667a; font-size: 13px; }}
      .dashboard-stats {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }}
      .stat {{ min-width: 132px; padding: 8px 10px; background: #f8fafc; border-radius: 8px; }}
      .stat-label {{ display: block; color: #64748b; font-size: 11px; }}
      .stat-value {{ display: block; color: #172033; font-size: 17px; font-weight: 700; margin-top: 2px; }}
      .dashboard-note {{ position: fixed; z-index: 9999; bottom: 24px; left: 60px; background: rgba(255,255,255,.94);
        border: 1px solid #dbe3ef; border-radius: 8px; padding: 8px 11px; color: #475569; font-size: 12px;
        box-shadow: 0 2px 10px rgba(15,23,42,.10); }}
      .leaflet-top.leaflet-right {{ top: 150px; }}
    </style>
    <div class="dashboard-header">
      <div class="dashboard-title">보행 접근성·안전 우선순위 대시보드</div>
      <div class="dashboard-subtitle">경사도, 음향 신호기, 장애인 편의시설, 사고 지점을 보행 구간 단위로 결합한 결과</div>
      <div class="dashboard-stats">
        <div class="stat"><span class="stat-label">분석 보행 구간</span><span class="stat-value">{total_edges:,}개</span></div>
        <div class="stat"><span class="stat-label">상위 10% 개선 후보</span><span class="stat-value">{high_priority:,}개</span></div>
        <div class="stat"><span class="stat-label">평균 절대 경사도</span><span class="stat-value">{mean_slope:.2f}%</span></div>
        <div class="stat"><span class="stat-label">최대 절대 경사도</span><span class="stat-value">{max_slope:.2f}%</span></div>
      </div>
    </div>
    <div class="dashboard-note">선의 색이 진할수록 개선 우선순위가 높습니다. 선을 클릭하면 상세 지표를 확인할 수 있습니다.</div>
    """
    fmap.get_root().html.add_child(Element(html))
    return fmap


if __name__ == '__main__':
    variables = execute_notebook_code()
    dashboard_map = build_map(variables)
    dashboard_map.save(OUTPUT)
    print(OUTPUT)
