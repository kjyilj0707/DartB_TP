"""보행 난이도 우선순위(1·2·3순위) 횡단보도를 실제 지도 위에 시각화한다.

crosswalk_deficiency.py(반경 500m)로 우선순위를 만들고, 세 단계를 같은 색(주황) 계열의 짙기로
구분해서 찍는다 — 1순위(최우선)가 가장 짙고, 3순위(양호)가 가장 옅다. 위험도의 크고 작음을 나타내는
값이라 단일 색상의 명도 차이(sequential)로 인코딩했다(범주별로 색을 다르게 쓰지 않음).

좌표는 h5_master의 EPSG:5186 x,y를 WGS84 경위도로 되돌려서 쓴다. GeoJson + style_function으로
그려서(점 하나하나를 개별 CircleMarker 객체로 만들지 않음) 9천 개가 넘는 점을 찍어도 파일 용량이
크게 늘지 않는다.
"""

from pathlib import Path

import folium
from pyproj import Transformer

import crosswalk_deficiency as cwd

PROJECT_DIR = Path(__file__).resolve().parent
OUT_HTML = PROJECT_DIR / "figures" / "h7" / "08_우선순위_지도.html"

# 짙은 정도로 위험 수준을 나타낸다: 1순위가 가장 짙고 3순위가 가장 옅다(단일 색상 sequential).
TIER_COLOR = {
    "1_최우선(부족지역+신호기없음)": "#9A3B12",  # 가장 짙은 주황
    "2_주의(둘 중 하나)": "#EB6834",             # 중간 주황(프로젝트 기본색)
    "3_양호": "#F7C4A0",                         # 가장 옅은 주황
}
TIER_LABEL = {
    "1_최우선(부족지역+신호기없음)": "1순위(최우선)",
    "2_주의(둘 중 하나)": "2순위(주의)",
    "3_양호": "3순위(양호)",
}
# 옅은 색부터 그려서 짙은 1순위가 겹치는 지점에서도 위로 보이게 한다.
DRAW_ORDER = ["3_양호", "2_주의(둘 중 하나)", "1_최우선(부족지역+신호기없음)"]


def _points_geojson(df, lon_col="lon", lat_col="lat", props=None):
    props = props or {}
    features = []
    for _, r in df.iterrows():
        feature_props = {k: (bool(r[v]) if v == "음향_배정_15m" else int(r[v])) for k, v in props.items()}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r[lon_col], r[lat_col]]},
            "properties": feature_props,
        })
    return {"type": "FeatureCollection", "features": features}


def build_map(radius=cwd.DEFAULT_R, tiers=None, include_accidents=True):
    """tiers=None이면 3단계 전부."""
    if tiers is None:
        tiers = DRAW_ORDER

    crosswalks = cwd.load_crosswalks()
    accidents = cwd.load_accidents()
    cw = cwd.build(radius, crosswalks, accidents)
    hot, q = cwd.summarize(cw)
    hot = cwd.priority_tier(hot)

    t = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)
    lon, lat = t.transform(hot["x"].to_numpy(), hot["y"].to_numpy())
    hot = hot.assign(lon=lon, lat=lat)

    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11, tiles="OpenStreetMap")

    if include_accidents:
        acc_gj = _points_geojson(accidents.rename(columns={"경도": "lon", "위도": "lat"}))
        folium.GeoJson(
            acc_gj, name="사고다발지역 693곳 (배경)", show=False,
            marker=folium.CircleMarker(radius=3, weight=0, fill=True, fill_opacity=0.35),
            style_function=lambda f: {"color": "#6b6b6b", "fillColor": "#6b6b6b"},
        ).add_to(m)

    for tier_key in [k for k in DRAW_ORDER if k in tiers]:
        label = TIER_LABEL[tier_key]
        color = TIER_COLOR[tier_key]
        sub = hot[hot["우선순위"] == tier_key]
        gj = _points_geojson(sub, props={"risk": "위험", "infra": "인프라", "signal": "음향_배정_15m"})
        folium.GeoJson(
            gj, name=f"{label} ({len(sub):,}개)", show=True,
            marker=folium.CircleMarker(radius=4, weight=1, fill=True, fill_opacity=0.8),
            style_function=lambda f, color=color: {"color": color, "fillColor": color},
            tooltip=folium.GeoJsonTooltip(
                fields=["risk", "infra", "signal"],
                aliases=[f"{label} · 반경{radius}m 위험(사고건수)", "반경 안 횡단보도 수", "이 지점 신호기 있음"],
                sticky=True,
            ),
        ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    legend_html = f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background: #fcfcfb; border: 1px solid #e3e3e0; border-radius: 6px;
                padding: 10px 14px; font-size: 13px; color: #1a1a1a; line-height: 1.6;">
      <b>보행 난이도 우선순위 (색이 짙을수록 심각)</b><br>
      <span style="color:{TIER_COLOR['1_최우선(부족지역+신호기없음)']};">●</span> 1순위(최우선): 부족지역 + 신호기 없음<br>
      <span style="color:{TIER_COLOR['2_주의(둘 중 하나)']};">●</span> 2순위(주의): 둘 중 하나<br>
      <span style="color:{TIER_COLOR['3_양호']};">●</span> 3순위(양호): 둘 다 아님<br>
      <span style="color:#6b6b6b;">●</span> 사고다발지역(배경, 기본 숨김)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    return m, hot


if __name__ == "__main__":
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    m, hot = build_map()
    m.save(str(OUT_HTML))
    n1 = (hot["우선순위"] == "1_최우선(부족지역+신호기없음)").sum()
    size_mb = Path(OUT_HTML).stat().st_size / 1e6
    print(f"1순위 {n1}개 포함, 3단계 전체 저장: {OUT_HTML} ({size_mb:.1f} MB)")
