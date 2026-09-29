"""
학교 영역 규정 방식 비교 시각화 (팀 공유용)
==========================================
A. OSM 캠퍼스 폴리곤으로 학교 영역을 규정
B. 카카오 API의 문 좌표에 반경(원)만 씌워서 학교 영역을 규정
두 방식이 학교 안/밖을 얼마나 다르게 나누는지, 그 차이가 통학로(학교 밖 보행망)에
어떤 영향을 주는지를 그림과 수치로 보여준다.

- 기준(정답 대용)은 OSM 캠퍼스 폴리곤이다. 공식 경계 데이터가 아니므로 '기준'이지 '정답'은 아니다.
- 카카오 문 좌표는 키워드 검색 "숭실대학교 <문 이름>"으로 조회한다.

결과: figures/soongsil_campus_definition.png, figures/soongsil_campus_definition.html
      data/soongsil_campus_polygon.geojson (2단계에서 재사용할 캠퍼스 폴리곤)
"""

import os
import sys
import time
from pathlib import Path

import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import pandas as pd
import requests
from dotenv import load_dotenv
from matplotlib import rcParams
from shapely.geometry import LineString, Point
from shapely.ops import polygonize, unary_union

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))
load_dotenv(PROJECT_DIR / ".env")
import soongsil_config as cfg  # noqa: E402
from collect_infra_places import bbox_from_center  # noqa: E402

rcParams["font.family"] = "Malgun Gothic"
rcParams["axes.unicode_minus"] = False

DATA_DIR = PROJECT_DIR / "data"
FIG_DIR = PROJECT_DIR / "figures"
PROJ = "EPSG:5186"
OSM_RELATION_ID = 19035920  # 숭실대학교 (amenity=university)
UA = {"User-Agent": "dartb-accessibility-study/0.1"}


def to_proj(geom, src="EPSG:4326"):
    return gpd.GeoSeries([geom], crs=src).to_crs(PROJ).iloc[0]


def to_ll(geom):
    return gpd.GeoSeries([geom], crs=PROJ).to_crs("EPSG:4326").iloc[0]


# ---------------------------------------------------------------------------
# 데이터 수집
# ---------------------------------------------------------------------------

def overpass(query):
    for _ in range(4):
        r = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, headers=UA, timeout=90)
        if r.status_code == 200 and r.text.strip().startswith("{"):
            return r.json()
        time.sleep(8)
    raise RuntimeError("Overpass 응답 실패")


def load_campus_polygon():
    """OSM relation에서 캠퍼스 폴리곤(WGS84)을 만들어 data/에 저장하고, 없으면 저장본을 쓴다."""
    path = DATA_DIR / "soongsil_campus_polygon.geojson"
    if path.exists():
        return gpd.read_file(path).geometry.iloc[0]
    rel = overpass(f"[out:json][timeout:60];relation({OSM_RELATION_ID});out geom;")["elements"][0]
    lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
             for m in rel["members"] if m.get("role") == "outer" and "geometry" in m]
    poly = unary_union(list(polygonize(unary_union(lines))))
    gpd.GeoSeries([poly], crs="EPSG:4326").to_file(path, driver="GeoJSON")
    return poly


def load_osm_gates():
    q = '[out:json][timeout:60];node["entrance"]["name"~"숭실대"](37.4935,126.951,37.499,126.9605);out;'
    return {el["tags"]["name"].replace("숭실대학교 ", ""): (el["lat"], el["lon"]) for el in overpass(q)["elements"]}


def load_kakao_gates():
    """'숭실대학교 <문>' 키워드 검색으로 출입구(교통,수송 > 입출구) 좌표를 모은다."""
    headers = {"Authorization": f"KakaoAK {os.environ['KAKAO_REST_API_KEY']}"}
    gates = {}
    for name in ["정문", "후문", "남문", "북문", "중문", "서문", "동문", "쪽문"]:
        r = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=headers,
                         params={"query": f"숭실대학교 {name}", "x": cfg.CENTER_LON, "y": cfg.CENTER_LAT, "radius": 1500, "size": 5},
                         timeout=15).json()
        for d in r.get("documents", []):
            if d["place_name"] == f"숭실대학교 {name}" and d["category_name"].startswith("교통,수송 > 입출구"):
                gates[name] = (float(d["y"]), float(d["x"]))
                break
    return gates


def load_walk_edges():
    G = ox.graph_from_bbox(bbox_from_center(cfg.CENTER_LAT, cfg.CENTER_LON, cfg.RADIUS_M + 150), network_type="walk")
    G = ox.project_graph(ox.convert.to_undirected(G), to_crs=PROJ)
    return ox.graph_to_gdfs(G, nodes=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 지표
# ---------------------------------------------------------------------------

def evaluate(region, campus, edges):
    """region(학교로 간주한 영역)이 campus(기준)와 얼마나 다른지."""
    both = region.intersection(campus)
    spill = region.difference(campus)   # 학교가 아닌데 학교로 처리된 영역
    missed = campus.difference(region)  # 학교인데 학교로 처리되지 않은 영역
    length = lambda g: float(edges.geometry.intersection(g).length.sum())
    return {
        "캠퍼스 커버율(%)": both.area / campus.area * 100,
        "학교 밖 초과 면적(ha)": spill.area / 1e4,
        "학교 밖인데 제외되는 보행망(m)": length(spill),
        "학교 안인데 통학로로 남는 보행망(m)": length(missed),
    }


def union_of_circles(points, r):
    return unary_union([p.buffer(r) for p in points])


def cover_radius(points, campus, target=0.99):
    lo, hi = 10.0, 1000.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if union_of_circles(points, mid).intersection(campus).area / campus.area >= target:
            hi = mid
        else:
            lo = mid
    return hi


# ---------------------------------------------------------------------------
# 그리기
# ---------------------------------------------------------------------------

def draw_map(ax, title, edges, campus, extent, region=None, region_color="#f59e0b", gates=None, gate_color="#dc2626"):
    edges.plot(ax=ax, color="#cbd5e1", linewidth=0.7, zorder=1)
    if region is not None:
        gpd.GeoSeries([region.intersection(campus)]).plot(ax=ax, color="#86efac", alpha=0.7, zorder=2)
        gpd.GeoSeries([region.difference(campus)]).plot(ax=ax, color="#ef4444", alpha=0.35, zorder=2)
        gpd.GeoSeries([campus.difference(region)]).plot(ax=ax, color="#a78bfa", alpha=0.7, zorder=2)
        gpd.GeoSeries([region]).boundary.plot(ax=ax, color=region_color, linewidth=1.4, zorder=3)
    else:
        gpd.GeoSeries([campus]).plot(ax=ax, color="#bfdbfe", alpha=0.8, zorder=2)
    gpd.GeoSeries([campus]).boundary.plot(ax=ax, color="#1d4ed8", linewidth=1.2, linestyle="--", zorder=4)
    if gates:
        for name, p in gates.items():
            ax.plot(p.x, p.y, "^", ms=8, color=gate_color, markeredgecolor="white", zorder=5)
            ax.annotate(name, (p.x, p.y), fontsize=8, xytext=(4, 4), textcoords="offset points", zorder=6)
    ax.set_xlim(extent[0], extent[2]); ax.set_ylim(extent[1], extent[3])
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, fontsize=11)


def main():
    FIG_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    campus = to_proj(load_campus_polygon())
    osm_gates = {n: to_proj(Point(lo, la)) for n, (la, lo) in load_osm_gates().items()}
    kakao_gates = {n: to_proj(Point(lo, la)) for n, (la, lo) in load_kakao_gates().items()}
    center = to_proj(Point(cfg.CENTER_LON, cfg.CENTER_LAT))
    print("카카오에서 찾은 문:", list(kakao_gates))
    print("OSM에서 찾은 문:", list(osm_gates))

    edges = load_walk_edges()
    minx, miny, maxx, maxy = campus.bounds
    extent = (minx - 130, miny - 130, maxx + 130, maxy + 130)

    # 카카오만 쓰는 방식들
    pts = list(kakao_gates.values())
    r_cover = cover_radius(pts, campus)
    r_center = max(center.distance(Point(x, y)) for x, y in campus.convex_hull.exterior.coords)
    r_small = 100
    regions = {
        "A. OSM 폴리곤": campus,
        f"B1. 카카오 문 + 반경 {r_small}m": union_of_circles(pts, r_small),
        f"B2. 카카오 문 + 반경 {r_cover:.0f}m (캠퍼스 99% 덮는 최소 반경)": union_of_circles(pts, r_cover),
        f"B3. 카카오 대표점 + 반경 {r_center:.0f}m (캠퍼스 전체를 덮는 원)": center.buffer(r_center),
    }
    metrics = pd.DataFrame({k: evaluate(v, campus, edges) for k, v in regions.items()}).T.round(1)
    print("\n", metrics.to_string())

    # 모든 패널을 같은 축척·범위로 그려야 크기 비교가 된다 (가장 큰 영역 기준)
    bx0, by0, bx1, by1 = unary_union(list(regions.values())).bounds
    extent = (bx0 - 40, by0 - 40, bx1 + 40, by1 + 40)

    # 반경별 곡선 (카카오 문 기준)
    rs = list(range(25, 401, 25))
    curve = pd.DataFrame([{"R": r, **evaluate(union_of_circles(pts, r), campus, edges)} for r in rs]).set_index("R")

    # ---- 그림 ----
    fig = plt.figure(figsize=(19, 12))
    gs = fig.add_gridspec(2, 3, hspace=0.25, wspace=0.28)
    axes = [fig.add_subplot(gs[0, i]) for i in range(3)] + [fig.add_subplot(gs[1, 0])]
    names = list(regions)
    m = metrics
    def sub(name):
        r = m.loc[name]
        return (f"커버율 {r['캠퍼스 커버율(%)']:.0f}% | 학교 밖 초과 {r['학교 밖 초과 면적(ha)']:.1f}ha\n"
                f"학교 밖인데 제외되는 보행망 {r['학교 밖인데 제외되는 보행망(m)']:.0f}m | 학교 안인데 남는 보행망 {r['학교 안인데 통학로로 남는 보행망(m)']:.0f}m")
    draw_map(axes[0], "A. OSM 캠퍼스 폴리곤 (제안 방식)\n" + f"{campus.area/1e4:.1f}ha, 문은 OSM 출입구", edges, campus, extent, gates=osm_gates, gate_color="#dc2626")
    draw_map(axes[1], names[1] + "\n" + sub(names[1]), edges, campus, extent, regions[names[1]], gates=kakao_gates, gate_color="#ea580c")
    draw_map(axes[2], names[2] + "\n" + sub(names[2]), edges, campus, extent, regions[names[2]], gates=kakao_gates, gate_color="#ea580c")
    draw_map(axes[3], names[3] + "\n" + sub(names[3]), edges, campus, extent, regions[names[3]], gates={"카카오 대표점": center}, gate_color="#ea580c")

    ax = fig.add_subplot(gs[1, 1])
    ax.plot(curve.index, curve["캠퍼스 커버율(%)"], "o-", color="#16a34a", label="캠퍼스 커버율(%)")
    ax.set_xlabel("카카오 문 좌표 기준 반경 R (m)"); ax.set_ylabel("캠퍼스 커버율 (%)", color="#16a34a"); ax.set_ylim(0, 105)
    ax2 = ax.twinx()
    ax2.plot(curve.index, curve["학교 밖인데 제외되는 보행망(m)"], "s-", color="#dc2626", label="학교 밖인데 제외되는 보행망(m)")
    ax2.set_ylabel("학교 밖인데 제외되는 보행망 (m)", color="#dc2626")
    ax.axhline(100, color="#1d4ed8", linestyle="--", linewidth=0.8)
    ax.set_title("반경만으로는 커버율을 올리면 학교 밖 길이 함께 제외됨\n(OSM 폴리곤 A는 커버율 100%, 학교 밖 제외 0m)", fontsize=11)
    ax.grid(alpha=0.3)

    axl = fig.add_subplot(gs[1, 2]); axl.axis("off")
    axl.set_position([axl.get_position().x0 + 0.03, axl.get_position().y0, axl.get_position().width, axl.get_position().height])
    legend_items = [
        ("#86efac", "학교 영역으로 정확히 잡힌 부분"), ("#ef4444", "학교가 아닌데 학교로 잡힌 부분 → 통학로에서 사라짐"),
        ("#a78bfa", "학교인데 학교로 안 잡힌 부분 → 통학로로 오인"), ("#1d4ed8", "OSM 캠퍼스 폴리곤 경계 (기준)"),
    ]
    for i, (c, t) in enumerate(legend_items):
        axl.add_patch(plt.Rectangle((0, 0.9 - i * 0.12), 0.06, 0.07, color=c, alpha=0.8, transform=axl.transAxes))
        axl.text(0.09, 0.925 - i * 0.12, t, transform=axl.transAxes, va="center", fontsize=10)
    axl.text(0, 0.36, "읽는 법\n· 파란 점선 = OSM 캠퍼스 경계(기준)\n· 회색선 = OSM 보행망\n· 삼각형 = 출입구\n"
                      "· 카카오는 문/대표점 '점'만 주므로 학교 범위는\n  반경(원)으로 근사할 수밖에 없음", transform=axl.transAxes, fontsize=10, va="top", linespacing=1.6)
    fig.suptitle("숭실대 '학교 영역' 규정 방식 비교 — 카카오 좌표+반경 vs OSM 폴리곤", fontsize=15, y=0.97)
    out_png = FIG_DIR / "soongsil_campus_definition.png"
    fig.savefig(out_png, dpi=120, bbox_inches="tight"); plt.close(fig)

    # ---- 인터랙티브 지도 ----
    m1 = folium.Map(location=[cfg.CENTER_LAT, cfg.CENTER_LON], zoom_start=16, tiles="OpenStreetMap")
    style = lambda color, fill: (lambda _: {"color": color, "weight": 2, "fillColor": color, "fillOpacity": fill})
    g_osm = folium.FeatureGroup("A. OSM 캠퍼스 폴리곤", show=True); g_b1 = folium.FeatureGroup(names[1], show=False)
    g_b2 = folium.FeatureGroup(names[2], show=False); g_b3 = folium.FeatureGroup(names[3], show=False)
    folium.GeoJson(to_ll(campus).__geo_interface__, style_function=style("#1d4ed8", 0.2), tooltip="OSM 캠퍼스 폴리곤").add_to(g_osm)
    for n, p in osm_gates.items():
        ll = to_ll(p); folium.CircleMarker([ll.y, ll.x], radius=6, color="#dc2626", fill=True, tooltip=f"OSM {n}").add_to(g_osm)
    for grp, nm in ((g_b1, names[1]), (g_b2, names[2]), (g_b3, names[3])):
        folium.GeoJson(to_ll(regions[nm]).__geo_interface__, style_function=style("#ea580c", 0.2), tooltip=nm).add_to(grp)
    for n, p in kakao_gates.items():
        ll = to_ll(p)
        for grp in (g_b1, g_b2):
            folium.CircleMarker([ll.y, ll.x], radius=6, color="#ea580c", fill=True, tooltip=f"카카오 {n}").add_to(grp)
    for grp in (g_osm, g_b1, g_b2, g_b3):
        grp.add_to(m1)
    folium.Marker([cfg.CENTER_LAT, cfg.CENTER_LON], tooltip="카카오 대표점(기준점)").add_to(m1)
    folium.Circle([cfg.CENTER_LAT, cfg.CENTER_LON], radius=cfg.RADIUS_M, color="#2563eb", fill=False, tooltip="반경 800m").add_to(m1)
    folium.LayerControl(collapsed=False).add_to(m1)
    out_html = FIG_DIR / "soongsil_campus_definition.html"
    m1.save(out_html)

    metrics.to_csv(FIG_DIR / "soongsil_campus_definition_metrics.csv", encoding="utf-8-sig")
    print(f"\n저장: {out_png}\n저장: {out_html}\n저장: {DATA_DIR / 'soongsil_campus_polygon.geojson'}")


if __name__ == "__main__":
    main()
