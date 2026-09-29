"""이미 저장된 Option A 엣지 결과에 15m 간격 보정을 적용한다. TMAP은 호출하지 않는다."""

from pathlib import Path

import geopandas as gpd
import pandas as pd

import osm_tmap_edge_filter as pipe


DATA = Path(__file__).parent / "data"


def main():
    edges, bridges = {}, []
    for school, slug in [("숭실대", "soongsil"), ("중앙대", "chungang")]:
        saved = gpd.read_file(DATA / f"{slug}_tmap_validated_network.gpkg", layer="all_edges")
        # 재실행해도 결과가 같도록 이전 보정을 되돌린 뒤 다시 적용한다.
        saved["validation_status"] = saved["validation_status"].replace("bridged", "unobserved")
        edges[school], bridge = pipe.bridge_validated_gaps(school, saved)
        bridges.append(bridge)
    summary = pd.read_csv(DATA / "option_a_tmap_route_match_summary.csv")
    pipe.save_validated_outputs(edges, summary)
    bridges = pd.concat(bridges, ignore_index=True)
    bridges.to_csv(DATA / "option_a_bridged_gaps.csv", index=False, encoding="utf-8-sig")
    print(bridges.to_string())


if __name__ == "__main__":
    main()
