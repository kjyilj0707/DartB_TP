"""Option A TMAP 엣지 필터 실행기.

기본 실행은 준비 상태와 예상 호출 수만 출력한다. 실제 호출에는 --execute와 정확한
예상 호출 수를 --confirm-calls로 함께 넘겨야 한다.
"""

import argparse
from pathlib import Path

import pandas as pd

import osm_tmap_edge_filter as pipe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-calls", type=int)
    args = parser.parse_args()

    path = Path("data/option_a_origins_with_osm_gate.csv")
    assigned = pd.read_csv(path) if path.exists() else pipe.prepare()[2]
    calls = pipe.expected_calls(assigned, gate_mode="osm_nearest")
    print(f"준비된 출발 노드: {len(assigned):,}개")
    print(f"예상 TMAP 호출: {calls:,}회")

    if not args.execute:
        print("DRY RUN: 외부 API를 호출하지 않았습니다.")
        return
    if args.confirm_calls != calls:
        raise SystemExit(f"호출 차단: --confirm-calls {calls}를 정확히 지정해야 합니다.")

    routes = pipe.run_tmap_filter_routes(assigned)
    failed = int(routes.geometry.isna().sum())
    print(f"TMAP 성공 {len(routes) - failed:,}건 / 실패 {failed:,}건")
    edges, summary = pipe.validate_edges(routes)
    bridges = []
    for school in list(edges):
        edges[school], bridge = pipe.bridge_validated_gaps(school, edges[school])
        bridges.append(bridge)
    pd.concat(bridges, ignore_index=True).to_csv(
        "data/option_a_bridged_gaps.csv", index=False, encoding="utf-8-sig"
    )
    pipe.save_validated_outputs(edges, summary)
    print("완료: TMAP 원본 geometry는 저장하지 않았습니다.")


if __name__ == "__main__":
    main()
