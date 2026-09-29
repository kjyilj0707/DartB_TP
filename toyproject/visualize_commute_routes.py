"""TMAP 검증 결과와 OSM 통학로 회랑을 정적·인터랙티브 지도로 시각화한다."""

from pathlib import Path

import folium
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import rcParams

import tmap_commute_pipeline as tcp


ROOT = Path(__file__).parent
OUT = ROOT / "figures" / "commute_routes"
OUT.mkdir(parents=True, exist_ok=True)

GATE_COLORS = {
    "정문": "#2563eb", "중문": "#dc2626", "후문": "#f59e0b",
    "남문": "#16a34a", "북문": "#7c3aed", "경계": "#64748b",
}
SCHOOL_COLORS = {"숭실대": "#1d4ed8", "중앙대": "#c2410c"}


def load_data():
    origins = pd.read_csv(ROOT / "data" / "commute_origin_candidates.csv")
    gates = tcp.load_gates()
    gate_summary = pd.read_csv(ROOT / "data" / "tmap_gate_choice_summary.csv")
    match_summary = pd.read_csv(ROOT / "data" / "tmap_osm_match_summary.csv")
    networks = {}
    for school, spec in tcp.SCHOOLS.items():
        edges = gpd.read_file(spec["network_file"], layer="edges")
        inside = edges["원_안"].astype(str).str.lower().isin(["true", "1"])
        non_virtual = edges["highway"].astype(str).ne("gate_connector")
        edges = edges[inside & non_virtual].copy()
        edges["최단경로_중첩수"] = pd.to_numeric(edges["최단경로_중첩수"], errors="coerce").fillna(0)
        networks[school] = edges
    return origins, gates, gate_summary, match_summary, networks


def static_figure(origins, gates, gate_summary, match_summary, networks):
    rcParams["font.family"] = "Malgun Gothic"
    rcParams["axes.unicode_minus"] = False
    fig = plt.figure(figsize=(18, 15), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, height_ratios=[2.2, 1])

    for ax, school in zip([fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])], ["숭실대", "중앙대"]):
        edges = networks[school]
        background = edges[edges["최단경로_중첩수"].eq(0)]
        corridors = edges[edges["최단경로_중첩수"].gt(0)].copy()
        background.plot(ax=ax, color="#d9dee7", linewidth=.45, zorder=1)
        max_log = max(np.log1p(corridors["최단경로_중첩수"].max()), 1)
        for gate, group in corridors.groupby("소속_문"):
            width = .8 + 3.2 * np.log1p(group["최단경로_중첩수"]) / max_log
            group.plot(ax=ax, color=GATE_COLORS.get(str(gate), "#64748b"), linewidth=width, alpha=.88,
                       label=f"{gate} 회랑", zorder=3)

        sub = origins[origins["학교"].eq(school)]
        bus = sub[sub["출발지유형"].eq("버스정류장")]
        subway = sub[sub["출발지유형"].eq("지하철출구")]
        ax.scatter(bus["lon"], bus["lat"], s=13, facecolor="white", edgecolor="#334155", linewidth=.6,
                   label=f"버스정류장 {len(bus)}", zorder=5)
        ax.scatter(subway["lon"], subway["lat"], s=55, marker="s", facecolor="#facc15", edgecolor="#713f12",
                   linewidth=.8, label=f"지하철 출구 {len(subway)}", zorder=6)
        gate = gates[gates["학교"].eq(school)]
        for r in gate.itertuples():
            ax.scatter(r.lon, r.lat, marker="^", s=105, color=GATE_COLORS[r.문], edgecolor="black", zorder=7)
            ax.annotate(r.문, (r.lon, r.lat), xytext=(5, 5), textcoords="offset points", fontsize=10,
                        fontweight="bold", zorder=8)
        rate = float(match_summary.loc[match_summary["학교"].eq(school), "평균매칭률_pct"].iloc[0])
        ax.set_title(f"{school} 통학로 회랑  ·  TMAP→OSM 평균 정합 {rate:.1f}%", fontsize=14, fontweight="bold")
        ax.legend(loc="lower left", fontsize=9, ncol=2, frameon=True)
        ax.set_aspect("equal"); ax.set_axis_off()

    ax = fig.add_subplot(gs[1, 0])
    order = ["정문", "중문", "후문", "남문", "북문"]
    x = np.arange(len(order)); width = .36
    for offset, school in [(-width/2, "숭실대"), (width/2, "중앙대")]:
        s = gate_summary[gate_summary["학교"].eq(school)].set_index("문")["출발지수"].reindex(order).fillna(0)
        bars = ax.bar(x + offset, s, width, color=SCHOOL_COLORS[school], label=school)
        ax.bar_label(bars, padding=3, fontsize=10)
    ax.set_xticks(x, order); ax.set_ylabel("선택한 출발지 수")
    ax.set_title("TMAP 최단 보행경로가 선택한 문", fontweight="bold"); ax.legend(); ax.grid(axis="y", alpha=.25)

    ax = fig.add_subplot(gs[1, 1])
    school_stats = pd.DataFrame({"학교": ["숭실대", "중앙대"], "평균거리_m": [461.4, 682.6],
                                 "평균시간_분": [372.8/60, 528.8/60]})
    x = np.arange(2)
    bars = ax.bar(x, school_stats["평균거리_m"], color=[SCHOOL_COLORS[x] for x in school_stats["학교"]], width=.55)
    ax.bar_label(bars, labels=[f"{v:.0f}m" for v in school_stats["평균거리_m"]], padding=4, fontsize=11)
    for i, mins in enumerate(school_stats["평균시간_분"]):
        ax.text(i, school_stats.loc[i, "평균거리_m"] * .48, f"평균 {mins:.1f}분", ha="center", va="center",
                color="white", fontsize=11, fontweight="bold")
    ax.set_xticks(x, school_stats["학교"]); ax.set_ylabel("출발지별 선택 경로 평균거리 (m)")
    ax.set_title("TMAP 선택 통학로의 평균 거리·시간", fontweight="bold"); ax.grid(axis="y", alpha=.25)

    fig.suptitle("중앙대·숭실대 통학로 구간 — TMAP 검증 + OSM 엣지 회랑", fontsize=18, fontweight="bold")
    out = OUT / "tmap_validated_commute_corridors.png"
    fig.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def interactive_map(origins, gates, gate_summary, match_summary, networks):
    m = folium.Map(location=[37.501, 126.957], zoom_start=14, tiles="OpenStreetMap")
    for school in ["숭실대", "중앙대"]:
        edges = networks[school]
        corridors = edges[edges["최단경로_중첩수"].gt(0)].copy()
        group = folium.FeatureGroup(name=f"{school} 통학로 회랑", show=True)
        for gate, sub in corridors.groupby("소속_문"):
            show = sub[["geometry", "최단경로_중첩수", "highway", "name"]].copy()
            show["문"] = str(gate); show["학교"] = school
            max_overlap = max(float(show["최단경로_중첩수"].max()), 1)
            color = GATE_COLORS.get(str(gate), "#64748b")
            folium.GeoJson(
                show.__geo_interface__,
                style_function=lambda f, c=color, mx=max_overlap: {
                    "color": c, "weight": 1.2 + 4 * np.log1p(float(f["properties"]["최단경로_중첩수"])) / np.log1p(mx),
                    "opacity": .82,
                },
                tooltip=folium.GeoJsonTooltip(fields=["학교", "문", "최단경로_중첩수", "highway", "name"],
                                              aliases=["학교", "담당 문", "경로 중첩수", "도로 유형", "도로명"]),
            ).add_to(group)
        group.add_to(m)

        og = folium.FeatureGroup(name=f"{school} 출발지", show=True)
        for r in origins[origins["학교"].eq(school)].itertuples():
            color = "#f59e0b" if r.출발지유형 == "지하철출구" else SCHOOL_COLORS[school]
            folium.CircleMarker([r.lat, r.lon], radius=5 if r.출발지유형 == "지하철출구" else 3,
                                color=color, fill=True, fill_opacity=.85,
                                tooltip=f"{school} | {r.출발지유형} | {r.출발지명}").add_to(og)
        og.add_to(m)

        gg = folium.FeatureGroup(name=f"{school} 출입문", show=True)
        for r in gates[gates["학교"].eq(school)].itertuples():
            picked = int(gate_summary.loc[(gate_summary["학교"].eq(school)) & (gate_summary["문"].eq(r.문)), "출발지수"].sum())
            folium.Marker([r.lat, r.lon], tooltip=f"{school} {r.문} | TMAP 선택 {picked}개 출발지",
                          icon=folium.Icon(color="red", icon="flag")).add_to(gg)
        gg.add_to(m)

    legend = """
    <div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:white;padding:12px 14px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;line-height:1.55">
    <b>통학로 회랑 읽기</b><br>
    선 색 = 담당 문 · 선 굵기 = OSM 최단경로 중첩수<br>
    파랑/주황 점 = 버스정류장 · 큰 점 = 지하철 출구<br>
    TMAP→OSM 평균 정합: 숭실대 99.9% / 중앙대 100.0%
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)
    out = OUT / "tmap_validated_commute_corridors.html"
    m.save(out)
    return out


def main():
    data = load_data()
    print(static_figure(*data))
    print(interactive_map(*data))


if __name__ == "__main__":
    main()
