"""Option A TMAP 필터 결과(validated·bridged·unobserved 엣지)를 시각화한다. API 호출 없음."""

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

import osm_tmap_edge_filter as pipe


ROOT = Path(__file__).parent
OUT = ROOT / "figures" / "option_a"
OUT.mkdir(parents=True, exist_ok=True)
BLUES = LinearSegmentedColormap.from_list("hits", ["#9ecae1", "#08306b"])
BRIDGED = "#e8590c"


def main():
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    gates = pipe.load_osm_gates()

    fig, axes = plt.subplots(1, 2, figsize=(16, 8.4), constrained_layout=True)
    for ax, (school, slug) in zip(axes, [("숭실대", "soongsil"), ("중앙대", "chungang")]):
        edges = gpd.read_file(ROOT / "data" / f"{slug}_tmap_validated_network.gpkg", layer="all_edges")
        campus = gpd.read_file(pipe.SCHOOLS[school]["campus"])
        campus.plot(ax=ax, color="#eef2f7", edgecolor="#94a3b8", linewidth=.8, zorder=1)

        edges[edges["validation_status"].eq("unobserved")].plot(
            ax=ax, color="#d4d4d8", linewidth=.6, zorder=2)
        validated = edges[edges["validation_status"].eq("validated")].sort_values("tmap_hit_routes")
        scale = np.log1p(validated["tmap_hit_routes"]) / np.log1p(edges["tmap_hit_routes"].max())
        validated.plot(ax=ax, color=[BLUES(s) for s in scale],
                       linewidth=1.2 + 3.3 * scale, zorder=3)
        edges[edges["validation_status"].eq("bridged")].plot(
            ax=ax, color=BRIDGED, linewidth=3.2, zorder=4)

        school_gates = gates[gates["학교"].eq(school)]
        ax.scatter(school_gates["lon"], school_gates["lat"], marker="^", s=110,
                   color="#111827", edgecolor="white", linewidth=1, zorder=5)
        for gate in school_gates.itertuples():
            ax.annotate(gate.문, (gate.lon, gate.lat), xytext=(5, 5), textcoords="offset points",
                        fontsize=10, fontweight="bold", zorder=6)

        counts = edges["validation_status"].value_counts()
        analysis_len = edges.loc[edges["analysis_edge"], "length"].sum()
        ax.set_title(
            f"{school} · 분석망 {counts.get('validated', 0) + counts.get('bridged', 0)}개 엣지 "
            f"({analysis_len / 1000:.1f} km / 전체 {edges['length'].sum() / 1000:.1f} km)",
            fontweight="bold")
        ax.set_axis_off(); ax.set_aspect("equal")

    legend = [
        Line2D([0], [0], color="#9ecae1", lw=1.5, label="validated · TMAP 경로 1개"),
        Line2D([0], [0], color="#08306b", lw=4.5, label="validated · TMAP 경로 다수"),
        Line2D([0], [0], color=BRIDGED, lw=3.2, label="bridged · 15m 이하 간격 OSM 보정"),
        Line2D([0], [0], color="#d4d4d8", lw=1, label="unobserved · 표본에서 미관측"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#111827", markersize=10, label="OSM 출입문"),
    ]
    fig.legend(handles=legend, loc="lower center", ncol=5, bbox_to_anchor=(.5, -.03), frameon=False)
    fig.suptitle("Option A TMAP 필터 결과 — 선 굵기·진하기는 해당 엣지를 지난 TMAP 경로 수",
                 fontsize=16, fontweight="bold")
    out = OUT / "option_a_tmap_validated_edges.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
