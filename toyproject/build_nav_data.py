"""음성 안내 페이지용 학교별 데이터(dashboard/nav/data_{학교}.json)와 조각 목록(clips.json)을 만든다.

구간 좌표는 u -> v 방향으로 맞춘다. 교차 지점·경사·계단 안내 문장은 tts_guidance와 같은 규칙으로 만든다.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

import route_guidance as rg
import tts_clips as tc
import tts_guidance as tg

ROOT = Path(__file__).resolve().parent
NAV = ROOT / "dashboard" / "nav"
GRADE = {"양호": 0, "주의": 1, "위험": 2}


def _r(v):
    return round(float(v), 6)


def _name(v):
    """OSM 이름. 합쳐진 구간은 리스트일 수 있어 첫 이름만 쓴다."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (list, tuple, np.ndarray)):
        return str(v[0]) if len(v) else None
    s = str(v)
    return s.strip("[]").split(",")[0].strip(" '\"") if s.startswith("[") else s


def school_data(school):
    edges, points = rg.load_network(school)
    import risk_a_crossing as ra
    nodes, _, _ = ra.load_school(school, "all_edges")
    nodes = nodes.set_index("node")
    used = pd.unique(pd.concat([edges["u"], edges["v"]]))
    idx = {n: i for i, n in enumerate(used)}
    ll = nodes.loc[used].to_crs(4326)
    node_list = [[_r(p.x), _r(p.y)] for p in ll.geometry]

    out_edges = []
    for r in edges.itertuples():
        g = r.geometry
        pu = Point(nodes.loc[r.u, "x"], nodes.loc[r.u, "y"])
        if Point(g.coords[0]).distance(pu) > Point(g.coords[-1]).distance(pu):
            g = LineString(list(g.coords)[::-1])
        turns = [round(g.project(p), 1) for p in tg.turn_points(g)]
        coords = gpd.GeoSeries([g], crs=tg.PROJ).to_crs(4326).iloc[0].coords
        hazard = None
        if r.B등급 == "위험" or bool(r.계단):
            text = tg.slope_text(r.최대경사_pct, bool(r.계단))
            hazard = tc.hazard_key(text)
        out_edges.append({
            "u": idx[r.u], "v": idx[r.v], "len": round(r.length_m, 1),
            "b": round(r.length_m, 1) if hazard else 0, "grade": GRADE[r.B등급], "stairs": bool(r.계단),
            "turns": turns, "hz": hazard, "tmap": r.validation_status != "unobserved",
            "name": _name(r.name),
            "xy": [[_r(x), _r(y)] for x, y in coords],
        })

    cross = {}
    for _, p in points.iterrows():
        if p["node"] not in idx:
            continue
        text = tg.crossing_text(p)
        a_raw = None if pd.isna(p["A점수"]) else float(p["A점수"])
        cross[idx[p["node"]]] = {
            "a": float(p["A점수"] if a_raw is not None else p["지원점수_최대"]), "araw": a_raw,
            "c": int(p["횡단단수_최대"]) if pd.notna(p["횡단단수_최대"]) else 1,
            "type": p["유형"], "support": p["지원수준"],
            "near": tc.hazard_key(text), "ahead": tc.hazard_key(tc.ahead_version(text)),
        }

    origins, gates = rg.origins_and_gates(school)
    gate_list = [{"node": idx[n], "name": name} for n, name in gates.items() if n in idx]
    origin_list = [idx[n] for n in origins["node"] if n in idx]   # 시뮬레이션용 기존 출발지(TMAP 153곳)

    cues = gpd.read_file(tg.OUT / "cues_full.geojson")
    cues = cues[cues["학교"] == school]
    free = []
    for c in cues.itertuples():
        geom = [[_r(x), _r(y)] for x, y in (c.geometry.coords if c.geometry.geom_type == "Point" else
                                           (c.geometry.coords if c.geometry.geom_type == "LineString" else
                                            [xy for part in c.geometry.geoms for xy in part.coords]))]
        free.append({"kind": c.종류, "key": tc.hazard_key(c.text), "pt": c.geometry.geom_type == "Point", "xy": geom})

    return {"school": school, "nodes": node_list, "edges": out_edges, "cross": cross, "gates": gate_list, "cues": free,
            "origins": origin_list}


def build():
    NAV.mkdir(parents=True, exist_ok=True)
    clips = tc.save_library()
    (NAV / "clips.json").write_text(json.dumps(clips, ensure_ascii=False), encoding="utf-8")
    sizes = {}
    for school, tag in (("숭실대", "soongsil"), ("중앙대", "chungang")):
        d = school_data(school)
        missing = {e["hz"] for e in d["edges"] if e["hz"]} | {c[k] for c in d["cross"].values() for k in ("near", "ahead")} \
            | {c["key"] for c in d["cues"]}
        missing -= set(clips)
        assert not missing, f"조각 목록에 없는 문장: {missing}"
        path = NAV / f"data_{tag}.json"
        path.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        sizes[school] = (len(d["nodes"]), len(d["edges"]), len(d["cross"]), len(d["gates"]), len(d["cues"]),
                         round(path.stat().st_size / 1024))
    return sizes


if __name__ == "__main__":
    print(build())
