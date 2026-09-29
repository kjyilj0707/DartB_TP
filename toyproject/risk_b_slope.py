"""위험도 지표 B(경사 위험)를 통학로 망(analysis_edges)의 구간마다 계산한다.

최종 규칙 (2026-09-24, 노트북 B-0 점검 후 확정)
- 높이: 등고선(5m 간격) 정점 + 표고점을 griddata 선형보간(compute_edge_slope.py와 같은 방식).
- 표고점으로 잰 보간 오차가 RMSE 약 2m라서, 경사는 최소 60m 기준 길이로 잰다(오차 약 ±4.7%p).
  - 60m 이상 구간: floor(L/60)등분한 조각(각 60m 이상)마다 경사를 재고 최댓값을 쓴다.
  - 60m 미만 구간: 구간 중간점을 중심으로 구간 진행 방향(시작점->끝점)으로 앞뒤 30m씩, 60m 기준으로 잰다.
- B 등급: 최대 경사가 5.6%(1/18) 이하 양호 / 8.3%(1/12) 이하 주의 / 초과 위험.
- 계단(highway에 steps 포함)은 경사와 별도로 표시한다.
- 처음 계획했던 10m 조각과 B-2 급변은 데이터 해상도 한계로 뺐다(아래 edge_profiles, piece_length_sensitivity는
  B-0 점검용으로 남겨 둔다).
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.interpolate import griddata
from shapely.geometry import box

import risk_a_crossing as ra

ROOT = Path(__file__).resolve().parent
CONTOUR_PATH = ROOT / "서울시_경사도" / "등고선 5000" / "N3L_F001.shp"
ELEV_POINT_PATH = ROOT / "서울시_경사도" / "표고 5000" / "N3P_F002.shp"
PROJ = "EPSG:5186"

STEP_M = 10
BASE_M = 60            # 최종 경사 기준 길이
BUFFER_M = 300
MIN_CHANGE_LEN_M = 20
OK_PCT = 100 / 18      # 5.56%
LIMIT_PCT = 100 / 12   # 8.33%
GRADES = ["양호", "주의", "위험"]


def load_elevation_samples(area_5186, buffer_m=BUFFER_M):
    """area(EPSG:5186 도형) 주변 등고선 정점 + 표고점을 (x, y, h) 배열로 만든다."""
    xs, ys, hs = [], [], []
    for path in (CONTOUR_PATH, ELEV_POINT_PATH):
        g = gpd.read_file(path)
        clip_area = gpd.GeoSeries([area_5186.buffer(buffer_m)], crs=PROJ).to_crs(g.crs).iloc[0]
        g = gpd.clip(g, clip_area).to_crs(PROJ)
        for geom, h in zip(g.geometry, g["HEIGHT"]):
            if geom.geom_type == "Point":
                xs.append(geom.x); ys.append(geom.y); hs.append(h)
                continue
            parts = geom.geoms if geom.geom_type.startswith("Multi") else [geom]
            for line in parts:
                for x, y in line.coords:
                    xs.append(x); ys.append(y); hs.append(h)
    return np.array(xs), np.array(ys), np.array(hs, dtype=float)


def interpolate(samples, x, y):
    xs, ys, hs = samples
    h = griddata((xs, ys), hs, (x, y), method="linear")
    miss = np.isnan(h)
    if miss.any():
        h[miss] = griddata((xs, ys), hs, (x[miss], y[miss]), method="nearest")
    return h, int(miss.sum())


def grade_of(pct):
    return np.select([pct <= OK_PCT, pct <= LIMIT_PCT], ["양호", "주의"], default="위험")


def edge_profiles(edges_5186, samples, step=STEP_M):
    """구간마다 조각 끝점 좌표를 만들고 한 번에 보간한 뒤 조각 경사를 계산한다."""
    pts_x, pts_y, owner = [], [], []
    seg_len = []
    for i, geom in enumerate(edges_5186.geometry):
        L = geom.length
        n = max(1, int(round(L / step)))
        for d in np.linspace(0, L, n + 1):
            p = geom.interpolate(d)
            pts_x.append(p.x); pts_y.append(p.y); owner.append(i)
        seg_len.append(L / n)
    h, n_nearest = interpolate(samples, np.array(pts_x), np.array(pts_y))
    owner = np.array(owner)
    profiles = []
    for i in range(len(edges_5186)):
        hi = h[owner == i]
        g = np.diff(hi) / seg_len[i] * 100          # 부호 있는 조각 경사(%)
        profiles.append((hi, g, seg_len[i]))
    return profiles, n_nearest, (np.array(pts_x), np.array(pts_y), owner, h)


def score_edges(edges_5186, profiles):
    rows = []
    for (hi, g, sl), L in zip(profiles, edges_5186.geometry.length):
        a = np.abs(g)
        over_ok = a > OK_PCT
        over_lim = a > LIMIT_PCT
        can_change = L >= MIN_CHANGE_LEN_M and len(g) >= 2
        jumps = 0
        max_change = np.nan
        if can_change:
            ch = np.abs(np.diff(g))
            max_change = ch.max()
            lo, hi_ = a[:-1], a[1:]
            jumps = int((((lo <= OK_PCT) & (hi_ > LIMIT_PCT)) | ((lo > LIMIT_PCT) & (hi_ <= OK_PCT))).sum())
        rows.append({
            "조각수": len(g),
            "끝점경사_pct": abs(hi[-1] - hi[0]) / L * 100,
            "최대경사_pct": a.max(),
            "5.6초과_비율": over_ok.mean(),
            "8.3초과_비율": over_lim.mean(),
            "최대경사변화_pctp": max_change,
            "급변_수": jumps if can_change else np.nan,
        })
    out = pd.DataFrame(rows, index=edges_5186.index)
    out["B1_등급"] = grade_of(out["최대경사_pct"])
    # 비교 규칙: 기준 초과 조각 길이가 구간의 절반 이상일 때만 그 등급
    out["B1_등급_절반규칙"] = np.select(
        [out["8.3초과_비율"] >= 0.5, out["5.6초과_비율"] >= 0.5], ["위험", "주의"], default="양호")
    out["B2_급변"] = np.select([out["급변_수"].isna(), out["급변_수"] > 0], ["산출 불가", "있음"], default="없음")
    return out


def run():
    nets = {}
    for school in ra.SCHOOLS:
        _, _, an = ra.load_school(school)
        nets[school] = an.to_crs(PROJ)
    area = gpd.GeoSeries(pd.concat([n.geometry for n in nets.values()]), crs=PROJ).union_all().envelope
    samples = load_elevation_samples(area)
    return samples, {school: score_b(an, samples) for school, an in nets.items()}



def study_area(results_or_nets):
    geoms = [v["edges"].geometry if isinstance(v, dict) else v.geometry for v in results_or_nets.values()]
    return gpd.GeoSeries(pd.concat(geoms), crs=PROJ).union_all().envelope


def spot_height_error(area_5186, buffer_m=BUFFER_M):
    """표고점을 빼고 등고선 정점만으로 표고점 위치의 높이를 보간해 오차를 잰다(보간 정확도 점검)."""
    c = gpd.read_file(CONTOUR_PATH)
    c = gpd.clip(c, gpd.GeoSeries([area_5186.buffer(buffer_m)], crs=PROJ).to_crs(c.crs).iloc[0]).to_crs(PROJ)
    xs, ys, hs = [], [], []
    for geom, h in zip(c.geometry, c["HEIGHT"]):
        for line in (geom.geoms if geom.geom_type.startswith("Multi") else [geom]):
            for x, y in line.coords:
                xs.append(x); ys.append(y); hs.append(h)
    p = gpd.read_file(ELEV_POINT_PATH)
    p = gpd.clip(p, gpd.GeoSeries([area_5186], crs=PROJ).to_crs(p.crs).iloc[0]).to_crs(PROJ)
    pred = griddata((np.array(xs), np.array(ys)), np.array(hs, dtype=float),
                    (p.geometry.x.to_numpy(), p.geometry.y.to_numpy()), method="linear")
    err = pred - p["HEIGHT"].to_numpy(dtype=float)
    return err[~np.isnan(err)]


def piece_length_sensitivity(edges_5186, samples, lengths=(10, 20, 30, 50)):
    """조각 길이를 바꿔 가며 B-1 등급 길이 비율과 급변 수를 계산한다."""
    rows = {}
    L_all = edges_5186.geometry.length.to_numpy()
    for W in lengths:
        prof, _, _ = edge_profiles(edges_5186, samples, step=W)
        mx, jumps = [], 0
        for (h, g, sl), L in zip(prof, L_all):
            a = np.abs(g)
            mx.append(a.max())
            if len(g) >= 2 and L >= 2 * W:
                jumps += int((((a[:-1] <= OK_PCT) & (a[1:] > LIMIT_PCT)) | ((a[:-1] > LIMIT_PCT) & (a[1:] <= OK_PCT))).sum())
        gr = pd.Series(grade_of(np.array(mx)))
        share = pd.Series(L_all).groupby(gr).sum() / L_all.sum() * 100
        rows[f"{W}m"] = {**{f"{k} 길이%": share.get(k, 0.0) for k in GRADES},
                        "최대경사 중앙값%": float(np.median(mx)), "급변 수": jumps}
    return pd.DataFrame(rows).T


def edge_grades(edges_5186, samples, base=BASE_M):
    """구간마다 60m 이상 기준 길이로 잰 경사(%)들을 돌려준다(부호 있음)."""
    pts_x, pts_y, owner, base_len = [], [], [], []
    for i, geom in enumerate(edges_5186.geometry):
        L = geom.length
        if L >= base:
            n = int(L // base)
            for d in np.linspace(0, L, n + 1):
                p = geom.interpolate(d)
                pts_x.append(p.x); pts_y.append(p.y); owner.append(i)
            base_len.append(L / n)
        else:
            a, b = np.array(geom.coords[0][:2]), np.array(geom.coords[-1][:2])
            v = b - a
            norm = np.hypot(*v)
            if norm == 0:                       # 시작=끝(고리 모양) 구간은 선의 앞뒤 점으로 방향을 잡는다
                v = np.array(geom.interpolate(min(1.0, L)).coords[0][:2]) - a
                norm = np.hypot(*v) or 1.0
            u = v / norm
            m = np.array(geom.interpolate(L / 2).coords[0][:2])
            for q in (m - u * base / 2, m + u * base / 2):
                pts_x.append(q[0]); pts_y.append(q[1]); owner.append(i)
            base_len.append(base)
    h, _ = interpolate(samples, np.array(pts_x), np.array(pts_y))
    owner = np.array(owner)
    return [np.diff(h[owner == i]) / base_len[i] * 100 for i in range(len(edges_5186))], base_len


def score_b(edges_5186, samples, base=BASE_M):
    grades, base_len = edge_grades(edges_5186, samples, base)
    e = edges_5186.copy()
    e["기준길이_m"] = base_len
    e["조각수"] = [len(g) for g in grades]
    e["최대경사_pct"] = [float(np.abs(g).max()) for g in grades]
    e["B등급"] = grade_of(e["최대경사_pct"].to_numpy())
    err = float(np.sqrt(2) * 1.98 / base * 100)   # B-0에서 잰 RMSE 1.98m 기준 대략 오차
    near = np.minimum(np.abs(e["최대경사_pct"] - OK_PCT), np.abs(e["최대경사_pct"] - LIMIT_PCT)) <= err
    e["기준선_근처"] = near                        # 오차 범위 안이라 등급이 바뀔 수 있는 구간
    e["계단"] = e["highway"].astype(str).str.contains("steps")
    e["length_m"] = e.geometry.length
    return e


if __name__ == "__main__":
    run()
