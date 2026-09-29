"""위험도 지표 대시보드(HTML 한 파일)를 만든다.

입력: 위험도지표 생성.ipynb가 저장한 결과
  data/risk_index/A_crossing_points.csv, B_edges.geojson, C_edges.csv
  data/{soongsil,chungang}_tmap_validated_network.gpkg (all_edges: 배경 보행망)
  data/{soongsil,chungang}_campus_polygon.geojson, data/{soongsil,chungang}_osm_gates.csv
출력: dashboard/index.html (template.html, claude.ai Artifact용, 지도 타일 없음)
      dashboard/site/index.html (template_osm.html, GitHub Pages용, Leaflet + OpenStreetMap 실제 지도)
두 템플릿 모두 /*__DATA__*/ 자리에 데이터를 JSON으로 넣는다.

실행: python -X utf8 dashboard/build_dashboard.py
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RISK = DATA / "risk_index"
OUT = Path(__file__).resolve().parent

SCHOOLS = {
    "chungang": {"name": "중앙대", "net": "chungang"},
    "soongsil": {"name": "숭실대", "net": "soongsil"},
}
ND = 5  # 좌표 소수 자리(약 1m)


def coords(geom):
    return [[round(x, ND), round(y, ND)] for x, y, *_ in geom.coords]


def a_segment(row, score, has):
    ends = [n for n in (row["u"], row["v"]) if n in has]
    if not ends:
        return "na"
    vals = score.reindex(ends).dropna()
    return int(vals.max()) if len(vals) else "unk"


def build_school(key, cfg, pts_all, b_all, c_all):
    name = cfg["name"]
    pts = pts_all[pts_all["학교"] == name].copy()
    b = b_all[b_all["학교"] == name].copy()
    c = c_all[c_all["학교"] == name].copy()
    for d in (b, c):
        d["u"] = d["u"].astype(str)
        d["v"] = d["v"].astype(str)
        d["key"] = d["key"].astype(int)
    e = b.merge(c[["u", "v", "key", "급한전환", "횡단_배분", "C이벤트"]], on=["u", "v", "key"], how="left")
    assert len(e) == len(b), "B/C 구간 결합 실패"

    score = pts.set_index("node")["A점수"]
    has = set(pts["node"])
    e["A구간"] = e.apply(a_segment, axis=1, score=score, has=has)

    edges = []
    for r in e.itertuples():
        edges.append({
            "g": coords(r.geometry),
            "nm": r.name if isinstance(r.name, str) else "",
            "hw": str(r.highway),
            "len": round(float(r.length_m), 1),
            "a": r.A구간,
            "b": r.B등급,
            "bs": round(float(r.최대경사_pct), 1),
            "bn": bool(r.기준선_근처),
            "st": bool(r.계단),
            "ct": int(r.급한전환),
            "cx": round(float(r.횡단_배분), 2),
            "c": round(float(r.C이벤트), 2),
        })

    points = []
    for r in pts.itertuples():
        points.append({
            "p": [round(r.lon, ND), round(r.lat, ND)],
            "t": r.유형,
            "sup": r.지원수준,
            "a": None if pd.isna(r.A점수) else int(r.A점수),
            "n": int(r.횡단보도수),
            "stage": int(r.횡단단수_최대),
            "def": None if pd.isna(r.부족) else int(r.부족),
        })

    net = gpd.read_file(DATA / f"{cfg['net']}_tmap_validated_network.gpkg", layer="all_edges").to_crs(5186)
    net["geometry"] = net.geometry.simplify(1.0)
    bg = [coords(g) for g in net.to_crs(4326).geometry if g is not None and not g.is_empty]

    campus = gpd.read_file(DATA / f"{cfg['net']}_campus_polygon.geojson").to_crs(4326)
    campus["geometry"] = campus.to_crs(5186).geometry.simplify(2.0).to_crs(4326)
    poly = json.loads(campus.to_json())["features"][0]["geometry"]

    gates = pd.read_csv(DATA / f"{cfg['net']}_osm_gates.csv", encoding="utf-8-sig")
    gates = [{"p": [round(r.lon, ND), round(r.lat, ND)], "n": r.문} for r in gates.itertuples()]

    # 종합 점수
    km = e["length_m"].sum() / 1000
    sc = pts["A점수"].dropna().to_numpy()
    rng = np.random.default_rng(20260924)
    boot = [rng.choice(sc, len(sc)).mean() for _ in range(5000)]
    L = e["length_m"].sum()
    sure = e[~e["기준선_근처"]]
    turns = int(e["급한전환"].sum())
    cross_ev = float(pts["횡단단수_최대"].fillna(1).sum())
    a_share = e.groupby(e["A구간"].astype(str))["length_m"].sum() / L
    b_share = e.groupby("B등급")["length_m"].sum() / L
    summary = {
        "km": round(km, 2),
        "n_edges": len(e),
        "A": {
            "mean": round(float(sc.mean()), 2),
            "ci": [round(float(np.percentile(boot, 2.5)), 2), round(float(np.percentile(boot, 97.5)), 2)],
            "n_points": len(pts),
            "n_scored": int(len(sc)),
            "n_marked": int((pts["유형"] == "횡단보도 있음").sum()),
            "n_unmarked": int((pts["유형"] != "횡단보도 있음").sum()),
            "unknown_share": round(float(pts["A점수"].isna().mean()), 3),
            "hi_per_km": round(float((sc >= 3).sum() / km), 2),
            "dist": {str(k): int((sc == k).sum()) for k in range(5)},
            "len_share": {k: round(float(v), 4) for k, v in a_share.items()},
        },
        "B": {
            "danger_share": round(float(b_share.get("위험", 0)), 3),
            "caution_share": round(float(b_share.get("주의", 0)), 3),
            "ok_share": round(float(b_share.get("양호", 0)), 3),
            "sure_danger_share": round(float(sure.loc[sure["B등급"] == "위험", "length_m"].sum() / L), 3),
            "wmean_slope": round(float((e["최대경사_pct"] * e["length_m"]).sum() / L), 1),
            "near_edges": int(e["기준선_근처"].sum()),
            "stairs": int(e["계단"].sum()),
        },
        "C": {
            "per_km": round((cross_ev + turns) / km, 2),
            "cross_per_km": round(cross_ev / km, 2),
            "turn_per_km": round(turns / km, 2),
            "stage2_points": int((pts["횡단단수_최대"] >= 2).sum()),
            "per_km_all1": round((len(pts) + turns) / km, 2),
        },
    }
    return {"name": name, "edges": edges, "points": points, "bg": bg, "campus": poly,
            "gates": gates, "summary": summary}, sc


def main():
    pts = pd.read_csv(RISK / "A_crossing_points.csv", dtype={"node": str}, encoding="utf-8-sig")
    b = gpd.read_file(RISK / "B_edges.geojson")
    c = pd.read_csv(RISK / "C_edges.csv", dtype={"u": str, "v": str}, encoding="utf-8-sig")
    data, scores = {}, {}
    for key, cfg in SCHOOLS.items():
        data[key], scores[key] = build_school(key, cfg, pts, b, c)
    _, p = mannwhitneyu(scores["chungang"], scores["soongsil"], alternative="two-sided")
    data["meta"] = {"a_mw_p": round(float(p), 2), "built": "2026-09-24"}

    blob = "window.RISK = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    # 1) claude.ai Artifact 버전(외부 이미지 차단 -> 지도 타일 없이 SVG로 그림)
    html = (OUT / "template.html").read_text(encoding="utf-8").replace("/*__DATA__*/", blob)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print(f"index.html {len(html) / 1024:.0f} KB")
    # 2) GitHub Pages 버전(Leaflet + OpenStreetMap 실제 지도). 배경 보행망은 필요 없어 뺀다
    slim = {k: ({kk: vv for kk, vv in v.items() if kk != "bg"} if k in SCHOOLS else v) for k, v in data.items()}
    blob2 = "window.RISK = " + json.dumps(slim, ensure_ascii=False, separators=(",", ":")) + ";"
    site = OUT / "site"
    site.mkdir(exist_ok=True)
    html2 = (OUT / "template_osm.html").read_text(encoding="utf-8").replace("/*__DATA__*/", blob2)
    (site / "index.html").write_text(html2, encoding="utf-8")
    print(f"site/index.html {len(html2) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
