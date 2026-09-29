"""최종 Option A 통학로 지도(분석망)를 공유용 HTML·GeoJSON으로 내보낸다. API 호출 없음.

위험·시설 변수는 팀 논의 후 결합하므로 여기서는 OSM 엣지와 TMAP 관측 정보만 담는다.
"""

from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import pandas as pd

import osm_tmap_edge_filter as pipe


ROOT = Path(__file__).parent
OUT = ROOT / "figures" / "option_a"
DATA_OUT = ROOT / "data" / "final_commute_map"
OUT.mkdir(parents=True, exist_ok=True)
DATA_OUT.mkdir(parents=True, exist_ok=True)
SCHOOLS = [("숭실대", "soongsil"), ("중앙대", "chungang")]
KEEP = ["학교", "u", "v", "key", "osmid", "name", "highway", "length",
        "validation_status", "tmap_hit_routes", "geometry"]
HIT_COLORS = ["#9ecae1", "#6baed6", "#3182bd", "#08519c", "#08306b"]
BRIDGED = "#e8590c"


def load_edges() -> gpd.GeoDataFrame:
    frames = []
    for school, slug in SCHOOLS:
        edges = gpd.read_file(ROOT / "data" / f"{slug}_tmap_validated_network.gpkg", layer="all_edges")
        edges.insert(0, "학교", school)
        frames.append(edges)
    edges = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    edges = edges[KEEP].copy()
    for col in ["osmid", "name", "highway"]:
        edges[col] = edges[col].fillna("").astype(str)
    edges["length"] = edges["length"].round(1)
    return edges


def hit_color(hits: int) -> str:
    bins = [1, 2, 4, 8, 16]
    return HIT_COLORS[int(np.searchsorted(bins, hits, side="right")) - 1]


def export_geojson(edges: gpd.GeoDataFrame) -> None:
    analysis = edges[edges["validation_status"].isin(["validated", "bridged"])]
    analysis.to_file(DATA_OUT / "commute_analysis_edges.geojson", driver="GeoJSON")
    edges.to_file(DATA_OUT / "commute_all_edges_with_status.geojson", driver="GeoJSON")
    gates = pipe.load_osm_gates()
    gpd.GeoDataFrame(
        gates, geometry=gpd.points_from_xy(gates["lon"], gates["lat"]), crs="EPSG:4326"
    ).to_file(DATA_OUT / "osm_gates.geojson", driver="GeoJSON")
    origins = pd.read_csv(ROOT / "data" / "option_a_origins_with_osm_gate.csv")
    gpd.GeoDataFrame(
        origins[["학교", "node", "lat", "lon", "OSM_최근접_문", "OSM_문까지_m"]],
        geometry=gpd.points_from_xy(origins["lon"], origins["lat"]), crs="EPSG:4326",
    ).to_file(DATA_OUT / "option_a_origins.geojson", driver="GeoJSON")


def build_map(edges: gpd.GeoDataFrame) -> folium.Map:
    center = edges.to_crs(pipe.PROJ).union_all().centroid
    center = gpd.GeoSeries([center], crs=pipe.PROJ).to_crs("EPSG:4326").iloc[0]
    # 배경지도: 로컬 파일(file://)로 열면 Referer가 없어 OSM 공식 타일은 "Access blocked",
    # CartoDB는 "API KEY REQUIRED" 워터마크가 뜨고, Esri 일반 지도는 한국 타일이 없다.
    # 그래서 OSM 데이터 기반 HOT 타일을 기본으로 두고 OSM 기본·Esri 위성은 예비로 둔다.
    fmap = folium.Map(location=[center.y, center.x], zoom_start=15, tiles=None)
    folium.TileLayer(
        "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        attr="&copy; OpenStreetMap contributors, HOT", name="배경: OSM (HOT)",
        subdomains="abc", max_zoom=19,
    ).add_to(fmap)
    folium.TileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="&copy; OpenStreetMap contributors", name="배경: OSM 기본 (웹에서 열 때)",
        max_zoom=19, show=False,
    ).add_to(fmap)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri", name="배경: 위성사진", max_zoom=19, show=False,
    ).add_to(fmap)
    tooltip = folium.GeoJsonTooltip(
        fields=["학교", "validation_status", "tmap_hit_routes", "name", "highway", "length"],
        aliases=["학교", "상태", "지난 TMAP 경로 수", "도로명", "도로 유형", "길이(m)"],
        sticky=True,
    )

    for school, _ in SCHOOLS:
        campus = gpd.read_file(pipe.SCHOOLS[school]["campus"])
        folium.GeoJson(
            campus, name=f"{school} 캠퍼스",
            style_function=lambda _: {"color": "#64748b", "weight": 1, "fillColor": "#e2e8f0", "fillOpacity": .45},
        ).add_to(fmap)

    unobserved = edges[edges["validation_status"].eq("unobserved")]
    folium.GeoJson(
        unobserved, name="unobserved · 표본에서 미관측", show=False,
        style_function=lambda _: {"color": "#a1a1aa", "weight": 1.5, "opacity": .7},
        tooltip=folium.GeoJsonTooltip(fields=tooltip.fields, aliases=tooltip.aliases, sticky=True),
    ).add_to(fmap)

    validated = edges[edges["validation_status"].eq("validated")].sort_values("tmap_hit_routes")
    folium.GeoJson(
        validated, name="validated · TMAP 경로 관측",
        style_function=lambda f: {
            "color": hit_color(f["properties"]["tmap_hit_routes"]),
            "weight": 2.5 + 1.2 * np.log2(max(f["properties"]["tmap_hit_routes"], 1)),
            "opacity": .95,
        },
        tooltip=tooltip,
    ).add_to(fmap)

    bridged = edges[edges["validation_status"].eq("bridged")]
    folium.GeoJson(
        bridged, name="bridged · 15m 이하 간격 보정",
        style_function=lambda _: {"color": BRIDGED, "weight": 5, "opacity": 1},
        tooltip=folium.GeoJsonTooltip(fields=tooltip.fields, aliases=tooltip.aliases, sticky=True),
    ).add_to(fmap)

    origins = pd.read_csv(ROOT / "data" / "option_a_origins_with_osm_gate.csv")
    origin_layer = folium.FeatureGroup(name="Option A 출발 노드 (153)", show=False)
    for r in origins.itertuples():
        folium.CircleMarker(
            [r.lat, r.lon], radius=3, color="#334155", weight=1, fill=True, fill_opacity=.8,
            tooltip=f"{r.학교} · {r.OSM_최근접_문}까지 {r.OSM_문까지_m:.0f}m",
        ).add_to(origin_layer)
    origin_layer.add_to(fmap)

    gate_layer = folium.FeatureGroup(name="OSM 출입문")
    for g in pipe.load_osm_gates().itertuples():
        folium.Marker(
            [g.lat, g.lon], tooltip=f"{g.학교} {g.문}",
            icon=folium.DivIcon(html=(
                '<div style="font:700 12px sans-serif;color:#111827;white-space:nowrap;'
                'text-shadow:0 0 3px #fff,0 0 3px #fff">▲ ' + g.문 + "</div>")),
        ).add_to(gate_layer)
    gate_layer.add_to(fmap)

    legend = """
    <div style="position:fixed;bottom:24px;left:12px;z-index:9999;background:#fff;padding:10px 12px;
                border:1px solid #cbd5e1;border-radius:6px;font:12px sans-serif;color:#1f2937;line-height:1.7">
      <b>중앙대·숭실대 통학로 지도 (Option A)</b><br>
      <span style="display:inline-block;width:26px;height:3px;background:#9ecae1;vertical-align:middle"></span> validated · TMAP 경로 1개<br>
      <span style="display:inline-block;width:26px;height:6px;background:#08306b;vertical-align:middle"></span> validated · 16개 이상<br>
      <span style="display:inline-block;width:26px;height:5px;background:#e8590c;vertical-align:middle"></span> bridged · 15m 이하 간격 보정<br>
      <span style="display:inline-block;width:26px;height:2px;background:#a1a1aa;vertical-align:middle"></span> unobserved · 미관측 (기본 숨김)<br>
      <span style="color:#6b7280">분석망 = validated + bridged</span>
    </div>"""
    fmap.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(fmap)
    return fmap


def main():
    edges = load_edges()
    export_geojson(edges)
    out = OUT / "option_a_commute_map.html"
    build_map(edges).save(out)
    print(out)
    for path in sorted(DATA_OUT.glob("*.geojson")):
        print(path)


if __name__ == "__main__":
    main()
