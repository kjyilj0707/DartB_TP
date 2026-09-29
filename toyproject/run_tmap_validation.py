"""전체 TMAP 통학로 검증을 실행하고 원본 경로를 버린 뒤 집계만 출력한다."""

from pathlib import Path

import pandas as pd

import tmap_commute_pipeline as tcp


def main():
    origins = pd.read_csv(Path("data") / "commute_origin_candidates.csv")
    print(f"START origins={len(origins)}")
    routes = tcp.run_all_routes(origins)
    success = routes["geometry"].notna().sum()
    print(f"ROUTES attempts={len(routes)} success={success} failed={len(routes)-success}")

    chosen = tcp.choose_nearest_gate(routes)
    print(f"CHOSEN origins={len(chosen)}")
    print(chosen.groupby(["학교", "문"]).size().rename("출발지수").to_string())
    print(chosen.groupby("학교").agg(
        출발지수=("origin_id", "size"), 평균거리_m=("distance_m", "mean"),
        중앙거리_m=("distance_m", "median"), 평균시간_s=("time_s", "mean"),
    ).round(1).to_string())

    _, match = tcp.match_routes_to_osm(chosen)
    print("MATCH")
    print(match.groupby("학교").agg(
        경로수=("origin_id", "size"), 평균매칭률_pct=("매칭률_pct", "mean"),
        중앙매칭률_pct=("매칭률_pct", "median"), 최소매칭률_pct=("매칭률_pct", "min"),
        평균매칭엣지수=("매칭OSM엣지수", "mean"),
    ).round(1).to_string())

    # 원본/선택 경로 geometry는 저장하지 않는다. 재현 가능한 집계만 저장한다.
    gate_summary = chosen.groupby(["학교", "문"]).agg(
        출발지수=("origin_id", "size"), 평균거리_m=("distance_m", "mean"),
        평균시간_s=("time_s", "mean"),
    ).round(1).reset_index()
    match_summary = match.groupby("학교").agg(
        경로수=("origin_id", "size"), 평균매칭률_pct=("매칭률_pct", "mean"),
        중앙매칭률_pct=("매칭률_pct", "median"), 최소매칭률_pct=("매칭률_pct", "min"),
    ).round(1).reset_index()
    gate_summary.to_csv(Path("data") / "tmap_gate_choice_summary.csv", index=False, encoding="utf-8-sig")
    match_summary.to_csv(Path("data") / "tmap_osm_match_summary.csv", index=False, encoding="utf-8-sig")
    print("SAVED aggregate summaries only; raw TMAP route geometry discarded")


if __name__ == "__main__":
    main()
