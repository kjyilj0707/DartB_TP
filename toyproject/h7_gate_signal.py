"""H7: 같은 학교 안에서 출입문마다 음향신호기 개수 차이가 큰가.

표본: gate_definition_all64.csv의 A·B 등급 문 중, 캠퍼스 단위 보류가 아니고 문이 2개 이상인 대학(24곳, 67문).
연결 규칙: 문에서 반경 R m 안의 음향신호기를 그 문의 것으로 센다(기본 300m, 200·400m는 민감도).
거리 계산은 EPSG:5186(m). 문 좌표는 4326이라 변환해서 쓴다.

검정: 학교마다 "신호기가 문 주변 횡단보도 수에 비례해 나뉜다"를 귀무가설로 두고, 다항분포로 무작위 배치를
여러 번 만들어 카이제곱 통계량이 관측값보다 큰 비율을 p값으로 쓴다(기대값이 작아 일반 카이제곱 근사가 약함).
격차 크기는 변동계수(CV = 표준편차 / 평균)로 본다.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

from h5_master import build_master

PROJECT_DIR = Path(__file__).resolve().parent
GATE_CSV = PROJECT_DIR / "data" / "h7" / "gate_audit_20260922" / "all64" / "gate_definition_all64.csv"
CAMPUS_CSV = PROJECT_DIR / "data" / "h7" / "gate_audit_20260922" / "all64" / "campus_audit_all64.csv"
OUT_DIR = PROJECT_DIR / "data" / "h7"
RADIUS_M = 300
RADII_SENSITIVITY = (200, 400)
N_SIM = 20000
SEED = 20260922


def load_sample(tiers=("A_공식명칭+좌표", "B_좌표만")):
    """H7 표본 문 목록(EPSG:5186 좌표 포함)."""
    gates = pd.read_csv(GATE_CSV)
    gates = gates[gates["tier"].isin(tiers)].copy()
    campus = pd.read_csv(CAMPUS_CSV)
    keep = campus[~campus["unit_hold"]]
    counts = gates.groupby("univ_name").size()
    keep = keep[keep["univ_name"].isin(counts[counts >= 2].index)]["univ_name"]
    gates = gates[gates["univ_name"].isin(keep)].copy()
    x, y = Transformer.from_crs(4326, 5186, always_xy=True).transform(gates["lon"].values, gates["lat"].values)
    gates["x"], gates["y"] = x, y
    return gates.reset_index(drop=True)


def gate_counts(gates, crosswalks, signals, radius=RADIUS_M):
    """문마다 반경 안의 음향신호기 수, 횡단보도 수, 신호기 있는 횡단보도 수."""
    points = gates[["x", "y"]].to_numpy()
    signal_tree = cKDTree(signals[["x", "y"]].to_numpy())
    cross_tree = cKDTree(crosswalks[["x", "y"]].to_numpy())
    has_signal = crosswalks["음향_배정_15m"].to_numpy()
    near_cross = cross_tree.query_ball_point(points, radius)
    out = gates.copy()
    out["신호기수"] = [len(v) for v in signal_tree.query_ball_point(points, radius)]
    out["횡단보도수"] = [len(v) for v in near_cross]
    out["신호기있는횡단보도수"] = [int(np.nansum(has_signal[v])) for v in near_cross]
    out["횡단보도중_신호기비율"] = np.where(out["횡단보도수"] > 0,
                                   out["신호기있는횡단보도수"] / out["횡단보도수"].replace(0, np.nan), np.nan)
    out["반경_m"] = radius
    return out


def _chi2(observed, expected):
    return float(np.sum((observed - expected) ** 2 / expected))


def campus_test(counts, n_sim=N_SIM, seed=SEED):
    """학교별 CV와 몬테카를로 p값. 기대 비율은 문 주변 횡단보도 수 + 1(0 방지)에 비례."""
    rng = np.random.default_rng(seed)
    rows = []
    for name, group in counts.groupby("univ_name"):
        observed = group["신호기수"].to_numpy(float)
        total = observed.sum()
        weights = group["횡단보도수"].to_numpy(float) + 1
        share = weights / weights.sum()
        cv = observed.std(ddof=1) / observed.mean() if observed.mean() > 0 else np.nan
        row = {"대학": name, "문수": len(group), "신호기합": int(total),
               "문별_신호기수": ", ".join(str(int(v)) for v in observed), "CV": cv,
               "기대비율_근거": "횡단보도수+1"}
        if total >= 5:
            expected = total * share
            simulated = rng.multinomial(int(total), share, size=n_sim).astype(float)
            stats = ((simulated - expected) ** 2 / expected).sum(axis=1)
            row["p"] = float((stats >= _chi2(observed, expected)).mean())
            row["CV_무작위_중앙값"] = float(np.nanmedian(
                np.where(simulated.mean(axis=1) > 0, simulated.std(axis=1, ddof=1) / simulated.mean(axis=1), np.nan)))
        else:
            row["p"] = np.nan
            row["CV_무작위_중앙값"] = np.nan
            row["비고"] = "신호기 5개 미만이라 검정하지 않음"
        rows.append(row)
    result = pd.DataFrame(rows)
    return holm(result)


def holm(result, alpha=0.05):
    """Holm 보정: 같은 가설을 학교 수만큼 반복 검정하므로 보정한다."""
    result = result.copy()
    tested = result["p"].notna()
    order = result.loc[tested, "p"].sort_values()
    m = len(order)
    adjusted, running = {}, 0.0
    for rank, (idx, p) in enumerate(order.items()):
        running = max(running, min((m - rank) * p, 1.0))
        adjusted[idx] = running
    result["p_holm"] = pd.Series(adjusted)
    result["유의"] = (result["p_holm"] < alpha).astype(object)
    result.loc[~tested, "유의"] = None
    return result.sort_values(["CV"], ascending=False).reset_index(drop=True)


def pooled_test(counts, basis="crosswalk", n_sim=N_SIM, seed=SEED):
    """학교별로 따로 검정하지 않고, 학교 안 문끼리의 차이를 전체에서 한 번에 검정한다.

    각 학교의 신호기 합은 그대로 두고 문에 나누는 방식만 귀무가설로 둔다.
      basis="crosswalk": 문 주변 횡단보도 수(+1)에 비례해 나뉜다 → "공급 대비 불균형"을 본다.
      basis="uniform"  : 문마다 같게 나뉜다 → "이용자가 겪는 접근성 차이"를 본다.
    카이제곱 통계량을 학교별로 더해 한 값으로 만들고, 같은 방식으로 만든 무작위 배치와 비교한다.
    검정이 한 번이므로 다중비교 보정이 필요 없다.
    """
    rng = np.random.default_rng(seed)
    observed_total, df, simulated_total, used = 0.0, 0, np.zeros(n_sim), []
    for name, group in counts.groupby("univ_name"):
        observed = group["신호기수"].to_numpy(float)
        total = observed.sum()
        if total < 1:
            continue
        weights = (group["횡단보도수"].to_numpy(float) + 1) if basis == "crosswalk" else np.ones(len(group))
        share = weights / weights.sum()
        expected = total * share
        observed_total += _chi2(observed, expected)
        df += len(group) - 1
        simulated = rng.multinomial(int(total), share, size=n_sim).astype(float)
        simulated_total += ((simulated - expected) ** 2 / expected).sum(axis=1)
        used.append(name)
    return {"기준": "횡단보도수 비례" if basis == "crosswalk" else "문마다 같음",
            "대학": len(used), "문": int(counts["univ_name"].isin(used).sum()),
            "카이제곱합": round(observed_total, 1), "자유도": df,
            "관측/기대 비율": round(observed_total / df, 2) if df else np.nan,
            "무작위 카이제곱합 중앙값": round(float(np.median(simulated_total)), 1),
            "p": float((simulated_total >= observed_total).mean())}


def pooled_rate_test(counts, n_sim=N_SIM, seed=SEED):
    """문 주변 횡단보도 중 음향신호기가 있는 비율이 같은 학교 안에서 문마다 다른지 전체에서 한 번에 검정한다.

    귀무가설: 한 학교 안에서는 문과 상관없이 같은 비율이다(학교 전체 비율). 횡단보도 수만큼 이항 추출로 비교한다.
    """
    rng = np.random.default_rng(seed)
    observed_total, df, simulated_total, used = 0.0, 0, np.zeros(n_sim), []
    for name, group in counts.groupby("univ_name"):
        n = group["횡단보도수"].to_numpy()
        k = group["신호기있는횡단보도수"].to_numpy(float)
        if n.sum() < 5 or not (n > 0).all():
            continue
        rate = k.sum() / n.sum()
        if rate in (0.0, 1.0):
            continue
        expected = n * rate
        stat = ((k - expected) ** 2 / (expected * (1 - rate))).sum()
        simulated = rng.binomial(n, rate, size=(n_sim, len(n))).astype(float)
        simulated_total += ((simulated - expected) ** 2 / (expected * (1 - rate))).sum(axis=1)
        observed_total += stat
        df += len(group) - 1
        used.append(name)
    return {"지표": "횡단보도 중 신호기 비율", "대학": len(used), "자유도": df,
            "관측 통계량": round(observed_total, 1),
            "무작위 중앙값": round(float(np.median(simulated_total)), 1),
            "p": float((simulated_total >= observed_total).mean())}


def load_inputs():
    """마스터 표는 한 번만 만든다(반경마다 다시 만들면 느리다)."""
    master, audible, _ = build_master(use_xgeo=True)
    return master[master["좌표상태"] == "정상"], audible[~audible["좌표결측"]]


def run(radius=RADIUS_M, tiers=("A_공식명칭+좌표", "B_좌표만"), save=True, inputs=None):
    crosswalks, signals = inputs if inputs is not None else load_inputs()
    counts = gate_counts(load_sample(tiers), crosswalks, signals, radius)
    result = campus_test(counts)
    if save:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        counts.to_csv(OUT_DIR / f"h7_gate_counts_{radius}m.csv", index=False, encoding="utf-8-sig")
        result.to_csv(OUT_DIR / f"h7_campus_test_{radius}m.csv", index=False, encoding="utf-8-sig")
    return counts, result


def summarize(result, radius):
    tested = result["p"].notna().sum()
    return {"반경_m": radius, "검정한_대학": int(tested),
            "유의_대학": int(result["유의"].fillna(False).sum()),
            "CV_중앙값": round(float(result["CV"].median()), 2),
            "CV_0.5이상_대학": int((result["CV"] >= 0.5).sum())}


if __name__ == "__main__":
    data = load_inputs()
    for r in (RADIUS_M, *RADII_SENSITIVITY):
        print(summarize(run(radius=r, inputs=data)[1], r))
