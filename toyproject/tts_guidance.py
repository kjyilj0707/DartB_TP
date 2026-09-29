"""TTS 실시간 위치 안내용 안내 지점(큐)과 안내 문장 (codex&claude.md §16.37).

큐 종류
  - 횡단: 지표 A 교차 지점 109개. 문장 = 횡단보도 유무, 보행등·음향신호기, 이단 여부, A 3점 이상이면 앞에 "주의".
  - 경사: 지표 B '위험'(>8.3%) 구간과 계단. 서로 이어진 구간은 한 덩어리로 묶어 한 번만 안내한다.
          8.3~13% "경사가 급할 수 있는", 13~20% "경사가 가파른", 20% 초과 "경사가 매우 가파른"(숫자는 말하지 않음).
  - 회전: 지표 C 급한 방향 전환(10m 안 45° 이상) 위치. 구간 선 위의 점으로 만든다.
걷는 방향을 모르므로 "앞에" 대신 "근처에"로 말한다. 가까운(15m 이내) 횡단·회전 큐는 하나로 합친다.
같은 문장은 음성 파일 하나를 같이 쓴다(audio_key = 문장 해시).
"""
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point
from shapely.ops import linemerge, unary_union

import risk_a_crossing as ra
import risk_c_complexity as rc

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "tts"
PROJ = "EPSG:5186"
MERGE_M = 15
STEEP_CERTAIN = 13.0
VERY_STEEP = 20.0

SUPPORT_TEXT = {
    "보행등+음향": "보행 신호등과 음향신호기가 있습니다",
    "보행등만": "보행 신호등은 있지만 음향신호기는 없습니다",
    "보행등 없음": "보행 신호등이 없습니다",
}


def crossing_text(r):
    if r["유형"] == "횡단보도 없는 교차로":
        body = "근처에 차도가 만나는 교차로가 있습니다. 횡단보도가 없습니다."
    else:
        body = f"근처에 횡단보도가 있습니다. {SUPPORT_TEXT[r['지원수준']]}."
        if r["횡단단수_최대"] >= 2:
            body += " 중간 교통섬을 거쳐 두 번에 나누어 건넙니다."
    if pd.notna(r["A점수"]) and r["A점수"] >= 3:
        body = "주의. " + body
    return body


def slope_text(max_grade, stairs):
    """숫자는 말하지 않는다. 60m 기준 경사도 오차가 ±4.7%p이고 일부 구간은 36~54%처럼 튀는 값이 나오기 때문."""
    if stairs:
        return "근처에 계단이 있습니다."
    if max_grade > VERY_STEEP:
        return "경사가 매우 가파른 구간입니다."
    if max_grade > STEEP_CERTAIN:
        return "경사가 가파른 구간입니다."
    return "경사가 급할 수 있는 구간입니다."


TURN_TEXT = "길이 크게 꺾이는 곳입니다."


def turn_points(geom, angle=rc.ANGLE_DEG, window=rc.WINDOW_M, step=rc.RESAMPLE_M):
    """rc.sharp_turns와 같은 규칙으로, 전환이 시작되는 곳에서 window/2 뒤의 점을 돌려준다."""
    h = rc._headings(geom, step)
    k = max(1, int(round(window / step)))
    if len(h) <= k:
        return []
    diff = (h[k:] - h[:-k] + 180) % 360 - 180
    flag = np.abs(diff) >= angle
    starts = np.flatnonzero(flag & ~np.concatenate([[False], flag[:-1]]))
    return [geom.interpolate(min(geom.length, s * step + window / 2)) for s in starts]


def _edge_key(df):
    return df["u"].astype(str) + "_" + df["v"].astype(str) + "_" + df["key"].astype(str)


def school_cues(school, full=False):
    """full=True면 경로 안내용 전체 보행망(route_guidance.build_network 결과)으로 만든다."""
    _, _, an = ra.load_school(school, "all_edges" if full else "analysis_edges")
    an = an.to_crs(PROJ).copy()
    an["ek"] = _edge_key(an)
    cues = []

    # 횡단
    a_path = ROOT / (f"data/route/{school}_points.csv" if full else "data/risk_index/A_crossing_points.csv")
    a = pd.read_csv(a_path, encoding="utf-8-sig")
    for _, r in a[a["학교"] == school].iterrows():
        cues.append({"종류": "횡단", "geometry": Point(r["x"], r["y"]), "text": crossing_text(r),
                     "A점수": r["A점수"], "node": str(r["node"])})

    # 회전
    for g in an.geometry:
        for p in turn_points(g):
            cues.append({"종류": "회전", "geometry": p, "text": TURN_TEXT})

    # 경사: 위험 또는 계단 구간을 이어진 덩어리로
    if full:
        b = gpd.read_file(ROOT / f"data/route/{school}_edges.geojson").drop(columns="geometry")
        b["계단"] = b["계단"].astype(bool)
    else:
        b = pd.read_csv(ROOT / "data/risk_index/B_edges.csv", encoding="utf-8-sig")
        b = b[b["학교"] == school].copy()
    b["ek"] = _edge_key(b)
    sel = b[(b["B등급"] == "위험") | b["계단"]]
    e = an.merge(sel[["ek", "최대경사_pct", "계단"]], on="ek")
    for stairs, grp in e.groupby("계단"):
        parent = {}
        def find(x):
            while parent.setdefault(x, x) != x:
                x = parent[x]
            return x
        for u, v in zip(grp["u"].astype(str), grp["v"].astype(str)):
            parent[find(u)] = find(v)
        grp = grp.assign(comp=[find(str(u)) for u in grp["u"]])
        for _, c in grp.groupby("comp"):
            u = unary_union(list(c.geometry))
            line = linemerge(u) if u.geom_type == "MultiLineString" else u
            cues.append({"종류": "계단" if stairs else "경사", "geometry": line,
                         "text": slope_text(c["최대경사_pct"].max(), stairs),
                         "최대경사_pct": round(c["최대경사_pct"].max(), 1), "길이_m": round(c.geometry.length.sum(), 1)})

    g = gpd.GeoDataFrame(cues, geometry="geometry", crs=PROJ)
    g["학교"] = school
    return merge_close_points(g)


def merge_close_points(g, dist=MERGE_M):
    """15m 안의 횡단·회전 점 큐를 하나로 합친다(횡단 문장을 앞에, 회전 문장은 한 번만)."""
    pts = g[g["종류"].isin(["횡단", "회전"])].reset_index(drop=True)
    rest = g[~g["종류"].isin(["횡단", "회전"])]
    order = np.argsort(pts["종류"].map({"횡단": 0, "회전": 1}).to_numpy(), kind="stable")
    used, rows = set(), []
    for i in order:
        if i in used:
            continue
        near = [j for j in order if j not in used and pts.geometry[i].distance(pts.geometry[j]) <= dist]
        used.update(near)
        grp = pts.loc[near]
        texts = list(dict.fromkeys(grp["text"]))
        row = pts.loc[i].to_dict()
        row["text"] = " ".join(texts)
        row["종류"] = "+".join(dict.fromkeys(grp["종류"]))
        row["합친_큐수"] = len(near)
        rows.append(row)
    merged = gpd.GeoDataFrame(rows, geometry="geometry", crs=PROJ)
    return pd.concat([merged, rest], ignore_index=True)


def audio_key(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def build(save=True, full=False):
    cues = pd.concat([school_cues(s, full) for s in ra.SCHOOLS], ignore_index=True)
    cues = gpd.GeoDataFrame(cues, geometry="geometry", crs=PROJ)
    cues["audio_key"] = cues["text"].map(audio_key)
    cues["cue_id"] = [f"{s}_{i:03d}" for s, i in zip(cues["학교"], cues.groupby("학교").cumcount())]
    sentences = cues.groupby(["audio_key", "text"]).size().rename("쓰인_큐수").reset_index()
    if save:
        OUT.mkdir(parents=True, exist_ok=True)
        tag = "_full" if full else ""
        cues.to_crs(4326).to_file(OUT / f"cues{tag}.geojson", driver="GeoJSON")
        sentences.to_csv(OUT / f"sentences{tag}.csv", index=False, encoding="utf-8-sig")
    return cues, sentences
