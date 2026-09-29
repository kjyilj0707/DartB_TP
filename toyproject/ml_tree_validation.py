"""트리 모델 지표 검증용 서울 교차로 테이블 (codex&claude.md §16.34).

1행 = 서울 교차로 1개(교차로관리번호로 묶은 횡단보도 그룹, 정상 좌표만).
정답 y = 교차로 중심 반경 R m 안에 서울 보행자 사고다발지가 있으면 1 (기본 100m, 50·200m는 민감도).
입력 X
  - A 요소: 지원점수_최대(0~2), 보행등_비율, 음향_유무(15m 배정 규칙), 횡단보도수
  - C 요소: 횡단단수_최대(일단1/이단2/삼단3), 대각선_유무
  - B 요소: 경사_60m(교차로 중심을 지나는 60m 기준선 4방향 중 최대 경사, %)
  - 통제(노출): 정류소수_100m, 승하차_200m(2026년 8월 하루 평균), 교차로수_300m(주변 교차로 밀도)
A의 부족 +1 점수는 사고다발지로 만든 값이라 넣지 않는다(누수).
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.interpolate import griddata
from scipy.spatial import cKDTree

import crosswalk_deficiency as cd
import h5_master
import risk_b_slope as rb

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "tree_model"
RIDERSHIP_CSV = ROOT / "2026년_버스노선별_정류장별_시간대별_승하차_인원_정보(08월) (1).csv"
LABEL_RADII = (50, 100, 200)
MAIN_RADIUS = 100
SLOPE_BASE_M = rb.BASE_M        # 60m, 지표 B와 같은 기준 길이
SLOPE_SAMPLE_M = 250            # 교차로마다 이 반경 안의 등고선·표고점만 써서 보간
SIGNAL_COL = "음향_배정_15m"

FEATURES_A = ["지원점수_최대", "보행등_비율", "음향_유무", "횡단보도수"]
FEATURES_C = ["횡단단수_최대", "대각선_유무"]
FEATURES_B = ["경사_60m"]
FEATURES_CTRL = ["정류소수_100m", "승하차_200m", "교차로수_300m"]


def _stage(kind):
    k = str(kind)
    return 3 if k.startswith("삼단") else 2 if k.startswith("이단") else 1


def intersections(master=None):
    """횡단보도 마스터 -> 교차로 단위 A·C 요소."""
    if master is None:
        master, _, _ = h5_master.build_master()
    cw = master[master["좌표상태"] == "정상"].copy()
    signal = cw["보행등유무"].eq("유")
    audible = cw[SIGNAL_COL].astype(float).eq(1)
    # risk_a_crossing.support_score와 같은 규칙(불일치 = 2점)
    cw["지원점수"] = np.select([signal & audible, signal & ~audible], [0, 1], default=2)
    cw["보행등"] = signal.astype(int)
    cw["음향"] = audible.astype(int)
    cw["횡단단수"] = cw["횡단보도종류"].map(_stage)
    cw["대각선"] = cw["횡단보도종류"].astype(str).str.startswith("대각선").astype(int)
    g = cw.groupby("교차로관리번호").agg(
        자치구=("자치구", "first"),
        x=("x", "mean"), y=("y", "mean"),
        횡단보도수=("횡단보도관리번호", "size"),
        지원점수_최대=("지원점수", "max"),
        보행등_비율=("보행등", "mean"),
        음향_유무=("음향", "max"),
        횡단단수_최대=("횡단단수", "max"),
        대각선_유무=("대각선", "max"),
    ).reset_index()
    return g


def add_labels(g, acc=None, radii=LABEL_RADII):
    if acc is None:
        acc = cd.load_accidents()
    seoul = acc[acc["시도시군구명"].astype(str).str.startswith("서울")]
    tree = cKDTree(seoul[["x", "y"]].to_numpy())
    xy = g[["x", "y"]].to_numpy()
    d, _ = tree.query(xy)
    g["최근접다발지_m"] = d
    for r in radii:
        g[f"y_{r}m"] = (d <= r).astype(int)
    return g


def bus_ridership():
    """정류소별 2026년 8월 하루 평균 승하차 인원(모든 노선·시간대 합 / 31)."""
    r = h5_master._read_csv(RIDERSHIP_CSV, low_memory=False)
    cols = [c for c in r.columns if c.endswith("승차총승객수") or c.endswith("하차총승객수")]
    r["승하차"] = r[cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
    per_stop = r.groupby("버스정류장ARS번호")["승하차"].sum() / 31
    return per_stop


def add_controls(g):
    b = h5_master.load_bus_stops()
    rid = bus_ridership()
    rid.index = rid.index.astype(str).str.zfill(5)
    b["승하차"] = b["ARS_ID"].astype(str).str.zfill(5).map(rid).fillna(0).to_numpy()
    bt = cKDTree(b[["x", "y"]].to_numpy())
    xy = g[["x", "y"]].to_numpy()
    g["정류소수_100m"] = [len(v) for v in bt.query_ball_point(xy, 100)]
    rid = b["승하차"].to_numpy()
    g["승하차_200m"] = [rid[v].sum() for v in bt.query_ball_point(xy, 200)]
    gt = cKDTree(xy)
    g["교차로수_300m"] = [len(v) - 1 for v in gt.query_ball_point(xy, 300)]
    return g


def seoul_elevation_samples():
    """서울 전체 등고선 정점 + 표고점 (EPSG:5186). risk_b_slope와 같은 원본."""
    xs, ys, hs = [], [], []
    for path in (rb.CONTOUR_PATH, rb.ELEV_POINT_PATH):
        g = gpd.read_file(path).to_crs(rb.PROJ)
        for geom, h in zip(g.geometry, g["HEIGHT"]):
            if geom is None:
                continue
            if geom.geom_type == "Point":
                xs.append(np.array([geom.x])); ys.append(np.array([geom.y])); hs.append(np.array([h], float))
                continue
            parts = geom.geoms if geom.geom_type.startswith("Multi") else [geom]
            for line in parts:
                c = np.asarray(line.coords)
                xs.append(c[:, 0]); ys.append(c[:, 1]); hs.append(np.full(len(c), h, float))
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(hs)


def add_slope(g, samples=None, base=SLOPE_BASE_M, sample_m=SLOPE_SAMPLE_M):
    """교차로 중심을 지나는 base m 기준선 4방향(0/45/90/135도)의 경사 중 최댓값(%).

    지표 B의 '60m 미만 구간은 중점을 지나는 60m 선으로 잰다'와 같은 생각을 방향을 모르는 점에 적용한 것.
    보간은 risk_b_slope.interpolate와 같다(선형, 빈 곳은 최근접).
    """
    if samples is None:
        samples = seoul_elevation_samples()
    xs, ys, hs = samples
    tree = cKDTree(np.column_stack([xs, ys]))
    ang = np.deg2rad([0, 45, 90, 135])
    dx, dy = np.cos(ang) * base / 2, np.sin(ang) * base / 2
    out = np.full(len(g), np.nan)
    for k, (x, y) in enumerate(g[["x", "y"]].to_numpy()):
        idx = tree.query_ball_point((x, y), sample_m)
        if len(idx) < 4:
            continue
        idx = np.asarray(idx)
        px = np.concatenate([x + dx, x - dx])
        py = np.concatenate([y + dy, y - dy])
        try:
            h, _ = rb.interpolate((xs[idx], ys[idx], hs[idx]), px, py)
        except Exception:
            continue
        out[k] = np.max(np.abs(h[:4] - h[4:])) / base * 100
    g["경사_60m"] = out
    return g


def build_table(save=True):
    g = intersections()
    g = add_labels(g)
    g = add_controls(g)
    g = add_slope(g)
    if save:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        g.to_csv(OUT_DIR / "seoul_intersections.csv", index=False, encoding="utf-8-sig")
    return g


def load_table():
    return pd.read_csv(OUT_DIR / "seoul_intersections.csv", encoding="utf-8-sig")


def route_points():
    """두 학교 통학로의 '횡단보도 있음' 교차 지점과 서울 교차로 테이블을 잇는다(교차로관리번호가 여러 개면 모두)."""
    p = pd.read_csv(ROOT / "data" / "risk_index" / "A_crossing_points.csv", encoding="utf-8-sig")
    p = p[p["유형"] == "횡단보도 있음"].copy()
    p["교차로관리번호"] = p["교차로관리번호"].astype(str).str.split(",")
    p = p.explode("교차로관리번호")
    p["교차로관리번호"] = p["교차로관리번호"].astype(float).astype(int)   # 저장값이 '7991.0' 형태
    return p
