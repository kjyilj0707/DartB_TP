"""횡단보도 단위로 "위험 대비 인프라 부족" 지수를 만든다.

9-5(1km 격자 단위)와 같은 개념을, 격자 경계·해상도 문제 없이 횡단보도 하나하나를 중심으로 한
반경(이동창) 방식으로 다시 만든다. 격자는 어디에 선을 긋느냐에 따라 같은 지점이 다른 값을 받을 수 있지만,
횡단보도 중심 반경은 그 횡단보도를 기준으로 항상 같은 방식으로 계산된다.

각 횡단보도 i, 반경 R 안에:
  - 인프라_i = 반경 안에 있는 다른 횡단보도 개수 (그 지역의 횡단보도 밀도, 자기 자신 제외)
  - 위험_i   = 반경 안에 있는 사고다발지역들의 사고건수 합
으로 정의한다. 위험_i가 0인 횡단보도(반경 안에 사고다발지역이 아예 없음)는 "위험이 확인되지 않은 곳"이라
9-5와 같은 이유로 부족지수 계산 대상에서 제외한다(9-1의 선택편향 교훈과 반대 방향: 여기선 위험이 있는 곳끼리
비교해야 "부족"이라는 말이 의미가 있다).
"""

from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

import h5_master

PROJECT_DIR = Path(__file__).resolve().parent
ACC_CSV = PROJECT_DIR / "data" / "seoul_relationship_eda" / "seoul_site_profiles.csv"
OUT_CSV = PROJECT_DIR / "data" / "seoul_relationship_eda" / "crosswalk_deficiency.csv"

RADII_M = (300, 500, 800)
DEFAULT_R = 500


def _read_csv(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 읽지 못함: {path}")


def load_accidents():
    acc = _read_csv(ACC_CSV)
    x, y = Transformer.from_crs(4326, 5186, always_xy=True).transform(acc["경도"].values, acc["위도"].values)
    acc["x"], acc["y"] = x, y
    return acc


def load_crosswalks(master=None):
    """h5_master의 정상 위치 횡단보도만 쓴다. 음향신호기 유무(음향_배정_15m)도 그대로 가져온다."""
    if master is None:
        master, _, _ = h5_master.build_master()
    ok = master["좌표상태"] == "정상"
    return master.loc[ok, ["x", "y", "음향_배정_15m"]].reset_index(drop=True)


def build(radius=DEFAULT_R, crosswalks=None, accidents=None):
    """횡단보도마다 인프라·위험 값을 계산한다(위험이 0인 곳 포함, 전체)."""
    if crosswalks is None:
        crosswalks = load_crosswalks()
    if accidents is None:
        accidents = load_accidents()

    cw = crosswalks.copy()
    cw_xy = cw[["x", "y"]].to_numpy()
    acc_xy = accidents[["x", "y"]].to_numpy()
    acc_counts = accidents["사고건수"].to_numpy()

    cw_tree = cKDTree(cw_xy)
    cw["인프라"] = [len(v) - 1 for v in cw_tree.query_ball_point(cw_xy, radius)]

    acc_tree = cKDTree(acc_xy)
    idx_lists = acc_tree.query_ball_point(cw_xy, radius)
    cw["위험"] = [acc_counts[idx].sum() if len(idx) else 0 for idx in idx_lists]

    cw["radius_m"] = radius
    return cw


def summarize(cw, top_q=0.75):
    """위험>0인 횡단보도만 골라 부족지수(비율·순위차 두 방식)와 상위 25% 부족 플래그를 만든다."""
    hot = cw[cw["위험"] > 0].copy()
    hot["부족지수_비율"] = hot["위험"] / hot["인프라"].replace(0, np.nan)
    hot["위험순위"] = hot["위험"].rank(pct=True) * 100
    hot["인프라순위"] = hot["인프라"].rank(pct=True) * 100
    hot["부족지수_순위차"] = hot["위험순위"] - hot["인프라순위"]
    q = hot["부족지수_비율"].quantile(top_q)
    hot["부족"] = (hot["부족지수_비율"] >= q).astype(int)
    return hot, q


def priority_tier(hot):
    """부족지역 여부 x 음향신호기 없음 여부로 3단계 우선순위를 만든다."""
    no_signal = hot["음향_배정_15m"] == False
    deficient = hot["부족"] == 1
    tier = np.select(
        [deficient & no_signal, deficient ^ no_signal],
        ["1_최우선(부족지역+신호기없음)", "2_주의(둘 중 하나)"],
        default="3_양호",
    )
    hot = hot.copy()
    hot["우선순위"] = tier
    return hot


if __name__ == "__main__":
    crosswalks = load_crosswalks()
    accidents = load_accidents()
    cw = build(DEFAULT_R, crosswalks, accidents)
    hot, q = summarize(cw)
    hot = priority_tier(hot)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    hot.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"반경 {DEFAULT_R}m, 위험>0인 횡단보도 {len(hot)}개, 부족지역 기준값(75분위) {q:.2f}")
    print(hot["우선순위"].value_counts())
    print("저장:", OUT_CSV)
