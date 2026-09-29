"""API 호출 없이 Option A 임의 출발지와 OSM 문 배정을 시각화한다."""

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from shapely.geometry import Point

import osm_tmap_edge_filter as pipe


ROOT = Path(__file__).parent
OUT = ROOT / "figures" / "option_a"
OUT.mkdir(parents=True, exist_ok=True)
COLORS = {"정문": "#2563eb", "중문": "#dc2626", "후문": "#f59e0b", "남문": "#16a34a", "북문": "#7c3aed"}


def main():
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    origins = pd.read_csv(ROOT / "data" / "option_a_origins_with_osm_gate.csv")
    gates = pipe.load_osm_gates()

    fig, axes = plt.subplots(1, 2, figsize=(16, 8), constrained_layout=True)
    for ax, school in zip(axes, ["숭실대", "중앙대"]):
        _, _, edges = pipe.load_network(school)
        edges = edges[edges["원_안"].astype(str).str.lower().isin(["true", "1"])]
        edges.plot(ax=ax, color="#d6dce5", linewidth=.65, zorder=1)

        campus = gpd.read_file(pipe.SCHOOLS[school]["campus"])
        campus.plot(ax=ax, color="#dbeafe", edgecolor="#2563eb", alpha=.65, zorder=2)

        sub = origins[origins["학교"].eq(school)]
        for gate, points in sub.groupby("OSM_최근접_문"):
            ax.scatter(points["lon"], points["lat"], s=26, color=COLORS[gate],
                       edgecolor="white", linewidth=.45, alpha=.9, zorder=4, label=f"{gate} {len(points)}")

        school_gates = gates[gates["학교"].eq(school)]
        for gate in school_gates.itertuples():
            ax.scatter(gate.lon, gate.lat, marker="^", s=130, color=COLORS[gate.문],
                       edgecolor="black", linewidth=.8, zorder=5)
            ax.annotate(gate.문, (gate.lon, gate.lat), xytext=(5, 5), textcoords="offset points",
                        fontsize=10, fontweight="bold", zorder=6)

        ax.set_title(f"{school} · 800m 층화 임의점 → OSM 노드 ({len(sub)}개)", fontweight="bold")
        ax.legend(loc="best", fontsize=9, frameon=True)
        ax.set_axis_off(); ax.set_aspect("equal")

    legend = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#64748b", markersize=8, label="스냅된 OSM 출발 노드"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#64748b", markeredgecolor="black", markersize=10, label="OSM 경계 교차 출입문"),
    ]
    fig.legend(handles=legend, loc="lower center", ncol=2, bbox_to_anchor=(.5, -.01))
    fig.suptitle("Option A 준비 결과 — 색은 OSM 보행거리상 최근접 문", fontsize=17, fontweight="bold")
    out = OUT / "option_a_random_origins_osm_gates.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
