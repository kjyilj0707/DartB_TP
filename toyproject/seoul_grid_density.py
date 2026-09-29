"""서울 전체를 1km 격자로 나눠, 횡단보도 밀도와 사고다발지역 사이의 관계를 본다.

앞서 사고다발지역 693곳 내부 비교(seoul_relationship_eda)에서는 상관관계가 전부 유의하지 않았는데,
그 표본이 이미 "사고가 많이 난 곳"으로만 뽑혀 있어(전부 연 7건 이상) 범위가 좁았다는 문제가 있었다.
이 스크립트는 사고가 없는 격자도 포함해서 같은 질문을 다시 본다.

격자: 1km x 1km, EPSG:5186. H5(§2)의 "1km 칸" 그림과 같은 크기를 써서 일관성을 맞췄다.
서울 행정경계 shapefile이 없어서, 횡단보도가 1개 이상 있는 격자만 "서울 시가지"로 보고 분석 대상에 넣는다
(그 밖의 격자는 경기도이거나 산·하천 등 보행 인프라가 없는 곳으로 본다).
"""

from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

PROJECT_DIR = Path(__file__).resolve().parent
CELL_M = 1000
CROSS_CSV = PROJECT_DIR / "서울시_교차로_및_횡단보도_시설위치정보_20260824.csv"
ACC_CSV = PROJECT_DIR / "data" / "seoul_relationship_eda" / "seoul_site_profiles.csv"
OUT_CSV = PROJECT_DIR / "data" / "seoul_relationship_eda" / "seoul_grid_1km.csv"


def _read_csv(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 읽지 못함: {path}")


def load_crosswalks():
    c = _read_csv(CROSS_CSV)
    c["x"] = pd.to_numeric(c["X좌표"], errors="coerce")
    c["y"] = pd.to_numeric(c["Y좌표"], errors="coerce")
    return c.dropna(subset=["x", "y"])


def load_accidents():
    acc = _read_csv(ACC_CSV)
    x, y = Transformer.from_crs(4326, 5186, always_xy=True).transform(acc["경도"].values, acc["위도"].values)
    acc["x"], acc["y"] = x, y
    return acc


def build_grid(cell_m=CELL_M):
    crosswalks, accidents = load_crosswalks(), load_accidents()
    for df in (crosswalks, accidents):
        df["gx"] = (df["x"] // cell_m).astype(int)
        df["gy"] = (df["y"] // cell_m).astype(int)

    cross_count = crosswalks.groupby(["gx", "gy"]).size().rename("횡단보도수")
    grid = cross_count[cross_count > 0].reset_index()  # 횡단보도가 있는 격자만 "서울 시가지"로 본다

    acc_agg = accidents.groupby(["gx", "gy"]).agg(
        사고다발지역수=("site_id", "size"),
        사고건수합=("사고건수", "sum"),
        사상자수합=("사상자수", "sum"),
        사망자수합=("사망자_발생", "sum"),
    ).reset_index()

    grid = grid.merge(acc_agg, on=["gx", "gy"], how="left")
    for col in ["사고다발지역수", "사고건수합", "사상자수합", "사망자수합"]:
        grid[col] = grid[col].fillna(0).astype(int)
    grid["사고다발지역_있음"] = (grid["사고다발지역수"] > 0).astype(int)
    grid["cell_m"] = cell_m
    return grid


if __name__ == "__main__":
    grid = build_grid()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    grid.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"격자 수(횡단보도 있는 곳): {len(grid)}")
    print(f"사고다발지역이 하나라도 있는 격자: {grid['사고다발지역_있음'].sum()} ({grid['사고다발지역_있음'].mean()*100:.1f}%)")
    print(grid[["횡단보도수", "사고다발지역수", "사고건수합"]].describe())
    print("저장:", OUT_CSV)
