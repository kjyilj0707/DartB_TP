# Handoff Notes — Accessibility Walking Map Project (for Codex, from Claude)

> **NEWEST (read first): §16.32 + §16.33 (dashboard on a real OSM map, published at https://kjyilj0707.github.io/DartB_TP/commute-risk-dashboard/) — §16.32 is the consolidated English record of the whole risk-index work (A crossing / B slope / C cognitive complexity, notebook `위험도지표 생성.ipynb`) and the public dashboard built from it (Claude, 2026-09-24). §16.28–16.31 are the step-by-step log it summarizes. For the commute-route network itself read §16.27.**
>
> Previous newest: §16.15 — re-colors the priority map as a single-hue sequential ramp (Claude, 2026-09-23).
>
> **Previous newest: §15 — Claude session 2026-09-22 (afternoon). Notebook 08 was restructured by the user and
> rebuilt; H5 tested (chi-square, goodness-of-fit, Mann-Whitney U, 30 m sensitivity), H8 paused after defining
> "crosswalk with/without audible signal", H7 in progress (Seoul university + gate collection via Kakao). §15.9 is
> the quick-start for Codex. §14.19–14.20 describe an older notebook-08 layout that no longer exists.**
>
> Older: §14 (hypothesis direction notebook `08_...`) and §14.9 (2026-09-22 direction change: the user's
> revised H5-H8 wording/tests supersede §14.3). Hypotheses are now wanted, so the "do not propose hypotheses" notes below are outdated.**
> **Latest handoff: 2026-09-21, Sections 11, 12 and 13 at the end of this file. Read them before continuing.**
> Section 13 covers the notebook growth after Section 12 (81 → 109 cells): crosswalk/slope detail, ring-slope
> comparison, hotspot typology, intersection-type hotspots, merged indicators. Same conclusion: no clear
> relationship yet, still no hypotheses or tests.
> Section 12 records that the missing/outlier audit was moved before `3-1` and redone for all datasets
> (old Section 5 of the notebook was deleted; §11.2 and §11.6 describe the old layout).
> The active notebook is `06_숭실대_반경_1-3단계.ipynb`. Seoul-wide relationship exploration
> and data-quality audits have now been executed. The user explicitly wants to inspect
> descriptive results first: **do not propose hypotheses or run hypothesis tests yet.**
> Section 11 supersedes older statements that relationship visualization has not started,
> that the national-vs-Seoul scope is undecided, or that 693 records mean 693 distinct places.

> Purpose of this file: this project is being worked on with both Claude Code and Codex,
> alternating sessions. This document is a full record of direction, decisions, code, and
> results produced so far, written so a Codex session with no prior context can read it and
> continue immediately without re-deriving anything. Whenever you (Codex or Claude) make a
> meaningful decision or finish a step in this project, please append/update this file so the
> other tool can pick up the thread.

Folder: `C:\Users\kjyil\Documents\python_study\DartB_TOYPROJECT` (this is **not** a git
repository — there is no `.git` here, so there is no commit history to consult; this file and
the `step*_설명.md` files are the source of truth for what happened and why).

Most in-repo docs (`step*.md`, `accessibility_project_plan.md`) are written in Korean for the
user's own study purposes. This file is the English-language project summary/handoff doc.

---

## 1. Project goal

Build a **pedestrian accessibility map for visually impaired users**, focused on a ~1km radius
around Chung-Ang University (중앙대) main gate in Seoul (Dongjak-gu). Original idea, in order:

1. Collect infrastructure (POIs: shops, hospitals, etc.) in the target area.
2. Pair up nearby infrastructure to define walking "segments."
3. For each segment, combine visually-impaired-accessibility data (tactile paving, etc.) and
   slope/elevation data into a difficulty/ruggedness score.
4. Visualize this as a map / dashboard.

This reuses the data-collection infrastructure of an earlier project, `MAP_Project` (Yelp-review
based couple-place prediction + Kakao API Korean place collection — see that project's
`analysis_process.md`), but repurposes it for pedestrian accessibility instead of date-spot
prediction.

Step 3 below revised item 2: instead of pre-defining infrastructure *pairs*, difficulty scores
are attached to individual **graph edges**, and any infra-A→infra-B "segment" is computed
on-demand as a shortest path through those scored edges. See §5.3 for the full reasoning.

---

## 2. Directory / file map

```
DartB_TOYPROJECT/
├── .env                              # KAKAO_REST_API_KEY=<real key> (not committed/shared, no git anyway)
├── .env.example                      # KAKAO_REST_API_KEY=
├── accessibility_project_plan.md     # Step 0: idea write-up + feasibility research (KR)
├── step1_인프라_수집_설명.md          # Why/how for step 1 (KR)
├── step2_도로망_스냅_설명.md          # Why/how for step 2 (KR)
├── step3_구간_정의_결정.md            # Design decision: edges not pairs (KR)
├── step4_경사도_결합_설명.md          # Why/how for step 4 (KR)
├── collect_infra_places.py           # Step 1 script (Kakao Local API collector)
├── snap_infra_to_network.py          # Step 2 script (osmnx graph + snapping)
├── compute_edge_slope.py             # Step 4 script (elevation interpolation + slope)
├── 01_인프라_수집.ipynb               # Step 1 notebook (runs collect_infra_places.py, inspects results)
├── 02_도로망_스냅.ipynb               # Step 2 notebook (runs snap_infra_to_network.py, folium map)
├── 04_경사도_결합.ipynb               # Step 4 notebook (runs compute_edge_slope.py, folium map)
├── 데이터관찰.ipynb                   # Ad-hoc notebook: just pd.read_csv().head() on raw datasets below
├── infra_수집_요약.txt                # Text summary of step-1 collection run (counts per category)
├── data/
│   ├── kakao_places_infra.jsonl      # Step 1 output: raw Kakao place docs, one JSON per line
│   ├── kakao_done_keys_infra.txt     # Step 1 resume-checkpoint (rect+category keys already fetched)
│   ├── infra_snapped.csv             # Step 2 output: infra + snapped_node_id + snap_distance_m
│   ├── pedestrian_graph.graphml      # Step 2 output: walk-network graph (osmnx/networkx GraphML)
│   └── pedestrian_graph_with_slope.graphml  # Step 4 output: graph + elevation/slope edge attrs
├── cache/                            # Misc cache (e.g. one geocoding-style JSON cache file)
├── __pycache__/                      # Python bytecode cache, ignorable
├── 서울시_경사도/                     # Raw Seoul elevation data (government shapefiles)
│   ├── 등고선 5000/N3L_F001.shp      # Contour lines, EPSG:5174, HEIGHT attribute (13,704 nationwide; 142 in bbox)
│   └── 표고 5000/N3P_F002.shp        # Elevation points, EPSG:5174, HEIGHT attribute (76,580 nationwide; 249 in bbox)
├── 서울시_경사도_등고선.csv           # CSV export of the contour shapefile (416MB, full Seoul, not yet used)
├── 서울시_경사도_표고점.csv           # CSV export of the elevation-point shapefile (not yet used directly; script reads .shp)
├── A073_P_음향신호기_현황/            # Raw shapefile: audible traffic signal locations (not yet integrated)
├── 음향신호기_현황.csv                # CSV of the above (not yet integrated)
├── 서울시_장애인편의시설_목록정보(한국사회보장정보원)_.csv  # Disability facility listing, building-level (not yet integrated)
├── 서울교통공사_지하철_시각장애인_음성유도기_설치_위치_정보_20260213.csv  # Subway audio-guidance beacon locations (not yet integrated)
├── 보행자_사고_다발지역.csv           # Pedestrian accident hotspot areas (not yet integrated)
└── _upload_tmp.png                   # Scratch image, ignorable
```

Everything under `서울시_경사도/`, plus the four CSVs listed as "not yet integrated" above, are
**raw datasets the user already downloaded** during the feasibility-research phase (see
`accessibility_project_plan.md` §3). Only the elevation shapefiles (`서울시_경사도/`) have
actually been consumed by code so far (step 4). The others (음향신호기, 장애인편의시설, 지하철
음성유도기, 보행자 사고 다발지역) were only opened once in `데이터관찰.ipynb` to preview their
columns with `pd.read_csv(...).head()` — no processing logic exists for them yet. They are
candidate inputs for a future "accessibility data" step (see §6).

---

## 3. Environment / setup

- Python environment: same interpreter used across the session (`python -c` calls worked
  directly; no venv activation step was needed in commands run so far).
- Key libraries used: `requests`, `python-dotenv`, `pandas`, `geopandas`, `osmnx`, `networkx`
  (via osmnx), `scipy` (`interpolate.griddata`), `shapely`, `folium` (for notebook map
  previews).
- Kakao REST API key goes in `.env` as `KAKAO_REST_API_KEY=<key>` (see `.env.example`). The
  script raises `SystemExit` with a clear message if it's missing. The `.env` file already has a
  real key set for this project (copied from `MAP_Project/.env` per notebook comments).
- No git repo exists here — don't expect `git log`/`git diff` to show history; this file is the
  only changelog.

**IDE/notebook gotcha (from user's persistent memory, applies to all notebooks in this repo):**
if a `.ipynb` file is open in an IDE (e.g. Cursor/VS Code) while it gets edited/overwritten by a
script or tool, the IDE's in-memory buffer can clobber the on-disk changes when the user later
saves. If you edit a notebook that might be open in an editor, tell the user to use
"Revert File" in their IDE before re-running/saving it, so they don't lose your edits.

---

## 4. How the pipeline works today (step by step)

Each step has a paired `.py` module (pure logic, importable) and a `.ipynb` notebook (thin
runner + inline verification + folium map preview). This split was intentional: notebooks call
into the modules rather than duplicating logic, so the modules can also be reused headless (e.g.
by Codex from the CLI without touching Jupyter).

### Step 1 — Infrastructure (POI) collection — `collect_infra_places.py` / `01_인프라_수집.ipynb`

**What it produces:** `data/kakao_places_infra.jsonl` — one JSON object per line, each a raw
Kakao Local API place doc (name, category, road address, `x`/`y` = lon/lat in WGS84).

**Why Kakao Local API** (vs. government 상가업소 data): Kakao's data is closer to real-time
(government data updates quarterly and lags closures/relocations), and the same collection
pattern was already validated in `MAP_Project/collect_kakao_places.py` for a nationwide Seoul
collection, so reusing it was low-risk. Full reasoning in `step1_인프라_수집_설명.md`.

**Method:**
- Center point: Chung-Ang University main gate, `lat=37.5070419, lon=126.9591522` (verified via
  raw OSM API lookup, tagged node — see `accessibility_project_plan.md` §3-2). Back gate has no
  OSM name tag, coordinates not yet pinned down; the 1km-radius bbox from the front gate already
  covers most of the compact campus and both gate areas, so this was deferred rather than
  blocking.
- Radius: 1000m, converted to a bbox via `bbox_from_center()` (lat degree ≈ 111,320m constant;
  lon degree scaled by `cos(lat)`).
- Categories collected (Kakao `category_group_code`): `HP8` hospital, `PM9` pharmacy, `CS2`
  convenience store, `MT1` large mart, `BK9` bank, `SW8` subway station, `FD6` restaurant, `CE7`
  cafe. **This is explicitly called out as a preliminary/pilot subset** (8 of Kakao's 18
  category groups) — chosen quickly to validate the pipeline end-to-end, not by rigorously
  filtering all 18 against "is this a real pedestrian destination?" Missing categories flagged
  in the notebook as needing review before a "real" run: schools, daycare/kindergarten, cultural
  facilities, public institutions.
- Kakao's category-search endpoint caps results at 45 per rectangle. Handled via: start from a
  coarse grid (`initial_grid`, 0.005° cells) over the target bbox; if a cell returns ≥45
  (`truncated`), recursively quarter-split it (`split_rect`) until either under 45 or the
  rectangle is smaller than `MIN_RECT_SIZE_DEG` (~150m), at which point it's accepted as-is.
  Completed `(category, rect)` keys are appended to `data/kakao_done_keys_infra.txt` so a
  re-run resumes instead of re-fetching (dedup handled at the API-call level, not just output
  level).
- Rate limiting: 0.15s delay between calls, up to 5 retries with backoff on HTTP 429.

**Actual run result** (`infra_수집_요약.txt`): 771 raw records, 770 after de-duplicating by
Kakao place `id`. Breakdown: 음식점(restaurant) 452, 카페(cafe) 125, 병원(hospital) 67, 편의점
(convenience) 49, 은행(bank) 43, 약국(pharmacy) 28, 대형마트(mart) 3, 지하철역(subway) 3.

### Step 2 — Walk network graph + infra snapping — `snap_infra_to_network.py` / `02_도로망_스냅.ipynb`

**What it produces:**
- `data/pedestrian_graph.graphml` — the walk network as an osmnx/networkx graph.
- `data/infra_snapped.csv` — step-1 infra rows plus `snapped_node_id` (nearest graph node) and
  `snap_distance_m` (distance from the infra's real coordinate to that node, in meters).

**Why osmnx / Overpass now, vs. raw OSM API before:** earlier feasibility research (plan.md
§3-2) hit repeated Overpass API timeouts and fell back to the raw OSM `api/0.6/map` endpoint.
For this much smaller bbox (~2km×2km), Overpass was retested and returned in 12 seconds (576
nodes, 1626 edges at that test), so `osmnx.graph_from_bbox(..., network_type="walk")` was used
directly instead of hand-parsing raw OSM XML/JSON. Timeout raised to 120s (`ox.settings.timeout
= 120`) as a safety margin.

**Why `network_type="walk"` specifically** (not just `highway=footway/pedestrian/crossing/...`,
the 165-way subset counted during feasibility research): a narrow footway-only filter would
exclude ordinary back-streets that pedestrians actually use but that aren't separately tagged as
sidewalks, breaking shortest-path connectivity between real destinations. `"walk"` includes
anything walkable except things like motorways.

**Snapping method:** project the graph to a local planar CRS (`ox.project_graph`), reproject
infra points to match, then `ox.distance.nearest_nodes(..., return_dist=True)` for both nearest
node id and true planar distance in meters (must not use raw lat/lon differences for distance —
that's why projection happens first).

**Actual result:** graph loaded, snapped 770 infra rows, saved both outputs. In the notebook's
outlier check, the largest `snap_distance_m` values clustered around `서울 동작구 흑석로 84`
(a Chung-Ang campus building address) and `흑석한강로 27` — interpreted as: internal campus
walkways / riverside paths aren't well-tagged in OSM's public `"walk"` network, so infra inside
those areas snapped to nodes on the nearest tagged big road instead. This is a known, observed
instance of a limitation flagged in advance in `step2_도로망_스냅_설명.md` §7. **Open TODO**:
decide in the difficulty-scoring design step how to treat/flag high-snap-distance edges (e.g.
down-weight or visually mark them as unreliable).

### Step 3 — Segment-definition design decision (no new artifact, decision only)

Documented in full in `step3_구간_정의_결정.md`. Summary of the decision and reasoning:

**Decision:** Do NOT build a separate "pair up nearby infrastructure" step. Instead:
- Treat each individual graph **edge** (from step 2: 1,626 edges) as the atomic "segment" unit.
- When a segment between two *specific* infra points is needed, compute the shortest path
  between their two `snapped_node_id`s on demand (via `networkx.shortest_path` / osmnx routing)
  — the sequence of edges on that path *is* the segment between them.
- Difficulty/ruggedness scores are only ever computed **per edge**. A pair's total difficulty =
  sum of its shortest-path edges' scores, computed at query time, never pre-stored.

**Why (three reasons from the doc):**
1. Pre-defining infra pairs by some "nearby" threshold would blow up combinatorially (770 infra
   → thousands of pairs depending on the distance cutoff chosen), whereas the graph already
   fixes the segment count at 1,626 regardless of how much infra exists.
2. Slope/tactile-paving/sidewalk-width data are inherently properties of a road segment, not of
   an infra pair — storing them at the pair level would require recomputation every time infra
   is added or a new pair is queried. Storing at the edge level means any future pair query is
   just a sum over its path.
3. Shortest-path computation already does exactly what "pairing" was trying to do — it finds the
   real sequence of connected edges between two points, so segments can never be a disconnected
   straight-line fiction (this also directly resolves the original core risk flagged in the plan:
   "don't create walking segments that ignore the real footpath network").

**Status table as of this decision** (also in the doc):

| Step | Status | Output |
|---|---|---|
| 1. Infra collection | Done (pilot) | `data/kakao_places_infra.jsonl` (770 rows, 8 categories) |
| 2. Graph + snapping | Done | `data/pedestrian_graph.graphml` (576 nodes, 1,626 edges), `data/infra_snapped.csv` |
| 3. Segment-definition decision | Done | This doc only, no artifact |
| 4. Per-edge slope | Done (see below) | `data/pedestrian_graph_with_slope.graphml` |
| 5. Per-edge accessibility data | Not started | — |
| 6. Edge difficulty scoring design | Not started | — |
| 7. Map / dashboard visualization | Not started | — |

**Open TODOs flagged in this doc for the scoring step (6):**
- Decide what the shortest-path algorithm should optimize on: raw distance, difficulty score, or
  offer both.
- Shortest-path only ever returns one "best" route; alternative-route comparison (e.g. k-shortest
  paths) is out of scope unless revisited later.

### Step 4 — Per-edge slope — `compute_edge_slope.py` / `04_경사도_결합.ipynb`

**What it produces:** `data/pedestrian_graph_with_slope.graphml` — the step-2 graph with three
new edge attributes: `elevation_start_m`, `elevation_end_m`, `slope_pct`.

**Input data:** `서울시_경사도/등고선 5000/N3L_F001.shp` (contour lines, `HEIGHT` attribute, EPSG:5174)
and `서울시_경사도/표고 5000/N3P_F002.shp` (elevation points, `HEIGHT` attribute, EPSG:5174).
Clipped to the target bbox with a 300m buffer (`BUFFER_M`) so interpolation near the bbox edge
stays stable — 142 contour features / 249 elevation points fall inside the raw bbox per the plan
doc, more with the buffer.

**Method (`step4_경사도_결합_설명.md`):**
1. `load_elevation_samples`: turn contour *lines* into scatter points by extracting every vertex
   of every line segment (handling `MultiLineString` from bbox-clipping) and pairing each vertex
   with that line's `HEIGHT`; combine with the elevation points as-is → one `(x, y, height)`
   scatter dataset in the graph's projected CRS.
2. `estimate_node_elevations`: for every graph node, interpolate height from the scatter data
   using `scipy.interpolate.griddata(method="linear")`; any node outside the convex hull of the
   scatter data (where linear interpolation returns NaN) is filled in with `method="nearest"`.
3. `add_slope_to_edges`: for each edge, `slope_pct = abs(h_v - h_u) / length * 100` where
   `length` is the OSM-provided edge length in meters (already present in the graph from step 2).
   Note this is an **unsigned** slope — uphill and downhill are not currently distinguished; that
   distinction is deferred to the difficulty-scoring step if needed.

**Actual result:** script runs, prints a slope-percent summary (mean/median/max, count of edges
over 10%) and saves the graph. Exact printed numbers weren't captured in the docs read, but the
notebook's folium cell buckets edges into green (<5%), gold (5–10%), orange (10–15%), red (15%+)
to visualize steep segments.

**Known limitations (from the doc):**
- Elevation source data is a one-time 2023 국토지리정보원 survey — no updates for later terrain
  changes (construction, etc.).
- Interpolation is an estimate; accuracy is better where contours/points are dense (e.g. hill
  slopes) and worse where they're sparse (flat areas).
- Slope is unsigned (direction-agnostic) for now.
- Long edges (e.g. straight roads) only look at endpoint elevation difference — mid-segment
  undulation isn't captured.

---

## 5. What's NOT done yet (next steps, in the order the project docs propose)

1. **Confirm back-gate coordinates precisely** — currently only the front-gate bbox is used;
   back gate has no OSM name tag and its exact point was never pinned down (deferred since the
   1km bbox already covers it).
2. **Re-run/expand step 1** with the full category set (or at least add school/daycare/cultural/
   public-institution categories) instead of the current 8-category pilot subset — this was
   explicitly called out in the notebook as a "pilot run, not final" caveat.
3. **Step 5 — attach accessibility data per edge**: OSM `tactile_paving`/`wheelchair` tags
   (already spot-checked in plan.md §3-2: 31 tactile_paving tags, 15 wheelchair tags, 15
   sidewalk tags, 0 kerb tags in the bbox) as the primary source, supplemented by whichever of
   the still-unintegrated raw CSVs turn out to be useful:
   - `음향신호기_현황.csv` / `A073_P_음향신호기_현황/` (audible traffic signals)
   - `서울시_장애인편의시설_목록정보(한국사회보장정보원)_.csv` (disability facilities, but
     building-level not road-level — noted as a mismatch concern in plan.md §3-1)
   - `서울교통공사_지하철_시각장애인_음성유도기_설치_위치_정보_20260213.csv` (subway audio
     guidance beacons)
   - `보행자_사고_다발지역.csv` (pedestrian accident hotspots) — not an accessibility dataset per
     se but could factor into a "risk" dimension of the difficulty score.
   None of these four have any processing code yet — `데이터관찰.ipynb` only previewed their
   columns with `.head()`.
4. **Step 6 — design the edge difficulty score**: combine `slope_pct` + accessibility-tag
   presence/absence into one number. MVP proposal in the plan doc: simple weighted sum of slope
   and accessibility-tag presence. Needs a decision on: how to weight kerb-data absence (OSM has
   zero `kerb` tags in this area — a documented hard limitation), how to treat high
   `snap_distance_m` infra (§ step 2 open TODO above), and whether/how to add slope direction
   (uphill vs downhill) per §4 step-4 limitations.
5. **Step 7 — map / dashboard visualization**: plan doc suggests Folium or Streamlit; all
   notebooks so far only use Folium for ad-hoc verification maps, not a real dashboard.

---

## 6. Known constraints / gotchas worth remembering

- **No git repo** in this folder — don't try to diff against history; this file + the step docs
  are the record.
- **Coordinate systems**: Kakao and OSM both use WGS84 (EPSG:4326) so no conversion is needed
  between infra points and the graph. The Seoul government elevation shapefiles use EPSG:5174
  (중부원점 TM, meters) — always reproject before combining with the graph's projected CRS
  (handled today via `gpd.GeoDataFrame.to_crs`).
- **Kakao API rate limit**: 45 results per rect per category call; the recursive quarter-split
  approach in `collect_infra_places.py` is the established pattern for this — reuse it rather
  than re-inventing pagination logic if collection needs to be extended/rerun.
- **Resume-safety**: `collect_infra_places.py` is idempotent/resumable via
  `data/kakao_done_keys_infra.txt`; safe to interrupt and rerun.
- Notebooks are thin wrappers around the `.py` modules by design — prefer extending the `.py`
  modules and re-running notebooks over writing new logic directly in a notebook cell, to keep
  the modules reusable from a plain Python/CLI context (relevant since Codex may prefer running
  scripts directly rather than through Jupyter).

---

## 7. Step 5 preparation — auxiliary-data EDA (completed 2026-09-19)

Created and executed `05_보조데이터_EDA.ipynb`. It profiles the four previously unintegrated
raw datasets, checks encodings/missingness/duplicate records, converts all usable coordinate
data to WGS84, filters against the same Chung-Ang University main-gate 1km reference radius,
and renders a Folium inspection map. It intentionally does **not** define or calculate a
difficulty score yet.

Observed results from the executed notebook:

- Audible traffic signals: 21,451 rows; 16,847 have usable `XCE`/`YCE` coordinates, and 85 are
  within the 1km reference radius. The source coordinates are KGD2002 Central Belt 2010
  (EPSG:5186), verified from the supplied shapefile `.prj`, so they must be reprojected before
  combining with WGS84 OSM data. Coordinate fields are missing in 21.46% of all rows.
- Disability-facility list: 29,153 rows; 24,075 have plausible WGS84 coordinates (zero/zero
  records excluded), with 218 in the 1km reference radius. This is building/facility-level
  information, so its conceptual relation to an edge difficulty score still needs a deliberate
  rule rather than automatic inclusion.
- Pedestrian accident hotspots: 2,402 rows; all have usable point coordinates, with 5 in the
  1km reference radius. The notebook also attempts to display each source GeoJSON polygon.
  This is more naturally a route-risk layer than an accessibility-infrastructure signal.
- Subway visual-impaired voice-guidance installation list: 5,802 rows, but only five
  non-spatial fields (`연번`, `호선`, `외부역번호`, `역명`, `설치위치`); it has no coordinate column.
  It cannot be snapped to graph edges until joined to a station/entrance coordinate source.

The next appropriate implementation step is to load `pedestrian_graph_with_slope.graphml` and
define data-specific edge-association rules: snap audible-signal points to nearby crossing/edge
features, intersect or buffer accident polygons against edges, and record snap/intersection
distance as a data-quality attribute. Do not silently treat all facility points as an edge
property.

### Follow-up: audible-signal EDA detail

The notebook's audible-signal section was expanded after the initial EDA. It now shows the
raw `XCE`/`YCE` and WKT `geometry` representations together, displays candidate status/history
columns (`STAT_CDE`, `WORK_CDE`, `VIEW_CDE`, `DRN_CDE`, `ESB_YMD`, `CAE_YMD`) as value
distributions, and displays the EPSG:5186-to-WGS84 converted location for nearby devices.
It also makes a nearest-POI table against `infra_snapped.csv`, explicitly labelled as a spatial
reference rather than a source-provided device-to-infrastructure relationship.

The agreed interpretation is that audible signals are independent point observations of a
crossing environment. A future processing step should snap them to a crossing node or edge and
retain the snap distance. Presence can become an evidence-backed accessibility feature, but
absence must remain unknown unless source coverage is proven complete. `STAT_CDE` and other
codes must not be treated as working/fault status until a source codebook verifies their meaning.

### Follow-up: audible-signal codebook and state-focused analysis

The user supplied authoritative mappings for the A073 source: kind `001=button type`; facility
status `001=good, 002=damaged, 003=painting, 004=aged`; visibility `001=hidden, 002=shown`;
construction form codes; work-flow codes; and eight direction codes mapped to degrees. These are
now encoded in `05_보조데이터_EDA.ipynb`, along with a Korean column guide and `audible_enriched`
fields for the decoded values.

The notebook now separately reports physical facility state, display state, work-flow state,
construction form, and direction. It uses a status-coloured map (good=green, damaged=red,
painting=orange, aged=purple, unknown=gray). Analysis of the current raw data found all 85
coordinate-valid devices within the Chung-Ang University 1km reference radius are `good`; their
work-flow values are 72 data-input and 13 verified-complete. Thus device condition is currently
positive coverage evidence in this area, but work-flow status is kept as data confidence rather
than being treated as physical condition.

Proposed future edge fields are counts by condition (`good`, `damaged`, `paint`, `aged`,
`unknown`) plus a snap-distance quality flag. Good devices may produce a modest accessibility
support benefit at an associated crossing; damaged devices instead produce a maintenance-risk
warning and no benefit. Painting/aged records remain inspection states, not proven failures.

> **Correction (2026-09-21, see §10.5):** across all of Seoul, `STAT_CDE` is `1` (good) in every
> one of the 21,426 non-null rows, not only near CAU. The `damaged`/`paint`/`aged` codes never
> occur in this file, so condition-based fields have no variation and cannot drive a score. Use
> "signal present near the crosswalk (distance-based)" instead.

---

## 8. EDA handoff update and shared documentation (2026-09-19)

### Executed-notebook scope

The shared EDA record must be limited to work actually run in `05_보조데이터_EDA.ipynb`.
Do not present auxiliary-data snapping, final difficulty-score weighting, subway-coordinate
joining, or accident-polygon/edge intersection as completed implementation. They remain
recommended next steps only.

### Notebook structure and DataFrame naming

Each source has its own named DataFrame and a separate `.columns` cell:

| DataFrame | Source | EDA role |
|---|---|---|
| `audible` | Audible traffic-signal inventory | Main state-focused analysis |
| `facility` | Disability-facility inventory | Building/facility context |
| `subway_voice` | Subway voice-guidance inventory | Non-spatial source review |
| `accident` | Pedestrian accident hotspot data | Potential risk layer |

Named DataFrames are preferred to a generic `df`: they make each cell readable, prevent an
accidental mix-up between sources, and make later processing rules explicit.

The profile fields mean: `dtype` = pandas column type; `missing_n` = missing-value count;
`missing_pct` = percentage missing; `nunique` = number of distinct non-missing values.

### Coordinates and quality interpretation

Audible-signal `XCE`/`YCE` are projected coordinates, not longitude/latitude. The authoritative
source CRS is EPSG:5186 (`KGD2002 / Central Belt 2010`). The notebook transforms them to
WGS84 / EPSG:4326 before the 1 km filter or web-map display. EPSG is a standard coordinate-system
identifier. `geometry` entries such as `POINT(X Y)` represent the same location in WKT form.

Missing or malformed coordinates mean **location unknown**, not device absent. Missing points or
no nearby device must therefore never automatically receive a negative accessibility score.

### Audible-signal codebook and state finding

The notebook implements the user-supplied codebook in decoding dictionaries and
`audible_enriched`:

- `A073_KND_CDE`: `001` = button type.
- `STAT_CDE` (physical state): `001` good; `002` damaged; `003` painting; `004` aged.
- `VIEW_CDE`: `001` hidden/not shown; `002` shown.
- `FRM_CDE`: construction form (new, replacement, removal, painting, repainting, relocation,
  light-shield replacement, pedestal, dismantle/reinstall, etc.).
- `WORK_CDE`: administrative work-flow state, from data entry through validation/approval/rejection.
- `DRN_CDE`: direction values map to 0, 45, 90, 135, 180, 225, 270, and 315 degrees.

`STAT_CDE` and `WORK_CDE` must remain separate. `STAT_CDE` is physical device condition;
`WORK_CDE` is record-processing status. A workflow-verified record can still represent a
physically damaged device.

For the Chung-Ang University main-gate 1 km reference radius, 85 audible-signal records have
valid coordinates and all 85 have `STAT_CDE = good`. Their workflow values are 72 `data input`
and 13 `verification complete`. This is positive evidence for known devices, but not proof of
complete device coverage or live operation. The map colours states as good=green, damaged=red,
painting=orange, aged=purple, unknown=gray. Nearest Kakao infrastructure is only a spatial
reference, never a verified device-to-facility link.

> **Correction (2026-09-21, see §10.5):** the all-`good` result is true for the whole Seoul file
> (21,426 non-null rows), so it is a property of the dataset, not positive evidence for this area.
> The condition-count fields and the `maintenance_warning_component` proposed below would always be
> zero. The 21% missing coordinates are concentrated in `WORK_CDE = 자료입력` rows registered since
> 2021, so recently installed signals are the ones missing from maps.

### Future edge integration (proposal only)

1. Snap each audible device to a suitable crossing node first; use a nearby pedestrian edge only
   when a crossing node is unavailable.
2. Save `signal_snap_distance_m` and flag uncertain spatial matches (20 m is an initial review
   threshold, not a final rule).
3. Save separate edge fields: `audible_signal_count`, `good_count`, `damaged_count`,
   `paint_count`, `aged_count`, and `unknown_count`.
4. Later compare `DRN_CDE` with edge/crossing direction to credit only relevant support.

Uncalibrated conceptual form:

`edge_difficulty = slope_component + crossing_risk_component - audible_support_component + maintenance_warning_component`

Good, confidently snapped devices can provide a modest support benefit. Damaged devices provide
no benefit and instead raise a maintenance warning. Painting/aged are inspection states, not
proven failures. Use `WORK_CDE` in `data_confidence`, not directly in difficulty. Weights need
field validation and user-needs review.

### Shared Notion page

The Notion page provided by the user was updated with an EDA-only team handoff focused on
coordinates, the four sources, audible-signal condition, limitations, and proposed edge use.
The page contains an earlier short EDA summary plus the detailed EDA section, so it has some
content overlap.

---

## 9. Codex update: auxiliary-data review and notebook work (2026-09-19)

This section records the latest work completed in `05_보조데이터_EDA.ipynb`.

### 9.1 Disability-facility inventory

Source: `서울시_장애인편의시설_목록정보(한국사회보장정보원)_.csv`

- 29,153 rows; `시설유형` has 67 distinct values.
- `시설위도` and `시설경도` are already longitude/latitude values. Treat them as WGS84 /
  EPSG:4326; no source-coordinate conversion is needed.
- About 5,078 rows contain `(0, 0)` coordinates and should be excluded from spatial analysis.
- Use EPSG:4326 for storage and maps; project to EPSG:5186 for distance calculations.
- This is building/facility-level data, not automatically a road-edge attribute. Future edge
  integration must define a spatial association rule and retain association distance.

### 9.2 Subway voice-guidance inventory

Source: `서울교통공사_지하철_시각장애인_음성유도기_설치_위치_정보_20260213.csv`

- 5,802 rows with station name, line, external station number, and installation-location text.
- `서울역(1)` means Seoul Station on Line 1; `서울역(4)` means Seoul Station on Line 4.
- The current file contains Lines 1-8. No station name contains `(9)`, so Line 9 is not present.
- There is no latitude/longitude column. Use `호선 + 외부역번호` as the stable station identity;
  joining to a coordinate source is required before graph snapping.

### 9.3 Pedestrian accident hotspots

Source: `보행자_사고_다발지역.csv`

- 2,402 rows covering nationwide locations, not Seoul only.
- Approximate coordinate extent: longitude 126.25-129.55; latitude 33.22-38.21.
- No EPSG code is stored explicitly, but `경도`/`위도` and the GeoJSON polygons use ordinary
  longitude/latitude. Treat them as WGS84 / EPSG:4326.
- One row represents one accident hotspot location/area, not one administrative region.
- `사고다발지fid` is unique per row and is safer as a row identifier than `지점코드`.
- For Seoul-only analysis, filter `시도시군구명` values containing `서울`.

### 9.4 Accident and casualty-column relationships

The six inspected columns are:

```text
사고건수       number of crashes
사상자수       total casualties
사망자수       fatalities
중상자수       serious injuries
경상자수       minor injuries
부상신고자수   reported injuries
```

For all 2,402 rows:

```text
사상자수 = 사망자수 + 중상자수 + 경상자수 + 부상신고자수
```

The equality holds for every row. Do not include `사상자수` together with all four detailed
casualty columns in a severity score, because that double-counts the same information.

Observed Pearson correlations:

| Pair | Correlation |
|---|---:|
| Accident count - total casualties | 0.792 |
| Accident count - serious injuries | 0.909 |
| Total casualties - serious injuries | 0.834 |
| Total casualties - minor injuries | 0.552 |
| Accident count - fatalities | 0.032 |

Interpretation: more crashes generally correspond to more casualties; serious injuries dominate
this dataset; fatalities are rare, so their simple linear correlation is low even though they are
high-severity outcomes.

### 9.5 Notebook cells added for accident analysis

- `accident-metric-observation`: displays the six columns and descriptive statistics.
- `accident-metric-relationship`: checks the casualty-sum identity and displays correlations.
- `accident-metric-visualization`: shows a correlation heatmap and an accident-count vs.
  casualty-count scatter plot.
- `accident-metric-interpretation`: markdown summary of findings and future-use direction.

If an IDE shows an older notebook state, close/reopen the notebook or use **Revert File** before
saving. An in-memory notebook can otherwise overwrite on-disk cell edits.

### 9.6 Future severity score and edge-difficulty direction

Use the four detailed casualty fields for an initial severity score:

```text
severity_raw =
    w_fatality * fatalities
  + w_serious  * serious_injuries
  + w_minor    * minor_injuries
  + w_reported * reported_injuries
```

Start with `w_fatality > w_serious > w_minor > w_reported`, then normalize to 0-1. These are
project modeling choices, not official safety standards.

For edge difficulty, associate each hotspot point or polygon with pedestrian-network edges using
a stated rule, retain match distance and method, aggregate severity per edge, and combine it with
slope and accessibility components only after normalizing all components. Consider exposure
adjustment by traffic volume, pedestrian volume, observation period, or edge length; raw counts
alone can overstate risk on longer or busier segments.

Edge association and final weighting are not implemented yet. The notebook currently performs EDA
and visualisation only.
- If editing a `.ipynb` that might be open in the user's IDE, remind them to "Revert File" before
  re-running/saving so the IDE doesn't clobber the edit (see §3).

---

## 10. Main project phase — Soongsil University part, steps 1–3 (Claude session, 2026-09-21)

This section records **only one Claude Code session (2026-09-21)**. Read it before continuing
the Soongsil work. Sections 1–9 describe the earlier Chung-Ang University (CAU) pilot and are
unchanged.

### 10.0 New project framing (team meeting)

The team project is now **"Seoul university districts from a visually impaired person's
viewpoint — Chung-Ang University vs Soongsil University (숭실대)"**. Pipeline agreed by the team:

1. Define the university district (commute-route viewpoint, Kakao API, EPSG:4326, 800 m radius).
2. Define segments/distances (nodes + edges inside the radius, identify commute routes).
3. Visualise the data and set hypotheses (these decide the components and weights of the
   difficulty index).
4. Build the index (hypotheses are verified here with statistics/ML/simulation).
5. Map dashboard (a commute-route recommendation / risk map).
6. Compare the two universities.

Roles: a CAU sub-team and a Soongsil sub-team. **The user owns the Soongsil part, steps 1–3.**
The 800 m radius is a team decision.

### 10.1 Files created or changed in this session

```
DartB_TOYPROJECT/
├── 06_숭실대_반경_1-3단계.ipynb        # MAIN notebook for the Soongsil part (steps 1, 2, 3-EDA). 43 cells, executed.
├── 07_숭실대_3단계_데이터_EDA.ipynb    # Standalone copy of the step-3 EDA; now DUPLICATED inside 06 (user has not decided whether to delete)
├── soongsil_config.py                 # Reference point + radius + query bbox
├── compare_univ_center.py             # Step 1: reference-point candidates (Kakao vs OSM)
├── viz_campus_definition.py           # Campus polygon, Kakao gates, radius-vs-polygon metrics and figures
├── soongsil_network.py                # Step 2: school-outside walk graph + nearest-gate assignment
├── 서울시_교차로_및_횡단보도_시설위치정보_20260824.csv  # CSV converted from the user's .xlsx (crosswalks)
├── 교통약자다발지점_보행자.csv          # CSV converted from the user's .xls (vulnerable-road-user hotspots)
├── 교통약자다발지점 사고지표.csv        # Header-only CSV from an EMPTY earlier download; obsolete (not deleted)
├── data/
│   ├── soongsil_center_candidates.csv   # Reference-point candidates and distances
│   ├── soongsil_campus_polygon.geojson  # OSM campus polygon (EPSG:4326)
│   ├── soongsil_kakao_gates.csv         # 5 Kakao gate coordinates (cache so the notebook runs without an API key)
│   └── soongsil_network.gpkg            # Step 2 output, layers `edges` and `nodes`, EPSG:4326
└── figures/
    ├── soongsil_campus_definition.png / .html   # Radius vs polygon comparison (team-sharing figure)
    └── soongsil_campus_definition_metrics.csv
```

User-supplied raw files that stay untouched: `교통약자다발지점 사고지표.xls`, `교통약자다발지점_보행자.xls`,
`서울시_교차로_및_횡단보도_시설위치정보_20260824 (1) copy.xlsx`, `장애인+현황(장애유형별_동별)_20260921153328.csv`.
The two `.xls` files are really `.xlsx` (zip) files. pandas reads them with `engine="openpyxl"`,
but `openpyxl.load_workbook` rejects the `.xls` extension, so copy to a `.xlsx` name first if needed.

The 06 notebook contains **two markdown cells written by the user** (index 13: note on the
connected-component count; index 17: note on the shortest-path overlap count). Preserve them
when editing.

### 10.2 Coordinate-system rule (user-confirmed)

- **Inputs and deliverables** (saved files, maps, coordinates shared with the team) use
  **EPSG:4326** (Kakao latitude/longitude).
- **Distance, area, radius, and slope calculations** use **EPSG:5186** (Korea Central Belt 2010,
  metres). EPSG:4326 is in degrees and cannot be used for distances directly.
- Source CRSs are mixed: accident hotspots and facilities are 4326; crosswalks and audible
  signals are 5186; elevation shapefiles are EPSG:5174.
- `soongsil_network.gpkg` is saved in 4326; node `x`/`y` (5186 metres) were replaced with
  `lon`/`lat`. Anything that re-reads it for calculations must call `.to_crs("EPSG:5186")`.

### 10.3 Step 1 — University district (done)

- **Reference point:** the Kakao Map result for the keyword "숭실대학교" (campus representative
  point) at **37.495853, 126.957818** (EPSG:4326). **Radius 800 m** (straight-line circle).
  Stored in `soongsil_config.py`. Notebook cell 1-1 re-queries Kakao and checks the value
  (0.00 m difference).
- **Naver was dropped** by the user. Naver's web search returned `ncaptcha` (bot blocking) and
  there is no Naver API key; no attempt was made to bypass this.
- The representative point is about 293 m east of the main gate. The Kakao main gate and the OSM
  main gate differ by 11 m. An 800 m circle on the representative point overlaps an 800 m circle
  on the main gate with IoU 0.61.
- **Open issue for the team:** CAU was analysed from its OSM main gate, while Soongsil uses the
  Kakao representative point. The Kakao "중앙대학교 서울캠퍼스" point (37.505149, 126.957173) is
  273 m from the CAU centre that was used. The rules differ, and this affects the comparison
  step. It is not resolved.

**School area inside the circle = OSM campus polygon; gates = Kakao coordinates.**

- Kakao provides only POIs (no road network, no campus polygon). The Kakao Mobility walking
  directions API is partner-only. So OSM is required for the walk network and the campus shape.
- OSM relation **19035920** (`amenity=university`, 숭실대학교): 12.5 ha, 3 outer parts (main
  campus + two small lots). The small lots contain 창의관/SNS마케팅센터 (1,292 m²) and
  정보과학관/IT대학 (3,234 m²), so they are school land and are **included**. They have no gates.
  They seem separated from the main campus by a road (사당로/상도로61길); this is not verified on
  a map.
- Validation: 39 of 40 Kakao "교육,학문" Soongsil POIs are inside the polygon (the outlier is
  숭실대학교어린이집, 101 m outside). The polygon edges are coarse, and this is a cross-check,
  not a comparison with an official boundary.
- **Kakao gates** (keyword "숭실대학교 <gate>", category `교통,수송 > 입출구`): 정문, 후문, 북문,
  중문, 남문. All five are within 21 m of the polygon boundary (중문 0.9, 후문 3.2, 북문 4.7,
  남문 16.5, 정문 20.8 m). 후문 and 북문 are different gates, and both are used.
- **Radius vs polygon comparison** (gates are Kakao in both; the reference is the OSM polygon):

| School-area method | Campus coverage | Extra area | Outside walkways wrongly excluded | Inside walkways wrongly kept |
|---|---|---|---|---|
| 5 gates + 100 m circles | 62.7% | 7.8 ha | 3,576 m | 1,100 m |
| 5 gates + 162 m (min radius for 99%) | 99.0% | 19.6 ha | 6,645 m | 21 m |
| OSM polygon | 100% | 0 | 0 | 0 |

The campus is elongated (about 660 m × 405 m), so circles cannot fit it. The polygon's 100%/0
only means that it is the reference, not that it matches an official boundary.
`figures/soongsil_campus_definition.png` shows OSM gates in its polygon panel; notebook cell
1-4 is the Kakao-gate version.

### 10.4 Step 2 — Segments and distances (done)

Implemented in `soongsil_network.py` (`run()`, `save()`), shown in notebook section 2.

- **Walk graph:** OSM `network_type="walk"` for the 800 m circle **plus a 150 m margin** (so
  detour paths can be computed). The graph is undirected and in EPSG:5186. Project before
  `to_undirected`, because `project_graph` turns the graph back into a directed one. Result: 797
  nodes, 1,122 edges.
- **Remove the school interior:** an edge is removed if **at least 50% of its length is inside
  the campus polygon**. This removed 71 edges (3.1 km). The rest is **one connected component**
  (738 nodes).
- **Rule change:** an earlier idea was to keep edges within 25 m of a gate. It was dropped,
  because 4 such edges run 104–165 m into the campus. Instead, each gate is joined to its nearest
  remaining node with a **virtual connector edge** (`highway="gate_connector"`, straight-line
  length 2.7–23.5 m, warning if over 25 m).
- **Nearest gate by walking distance:** Dijkstra from each gate. Every node gets its nearest
  gate, the distance, the 2nd-nearest gate, and the gap between them. Start nodes = nodes inside
  the circle and outside the campus (400). All 400 reach a gate.
- **Edge attributes:** `소속_문` (the gate of both end nodes, or `경계` if they differ),
  `문까지_최소_m` / `문까지_최대_m`, `원_안`, `highway`, and **`최단경로_중첩수`**.
  `최단경로_중첩수` was renamed from `이용집중도` at the user's request. It counts how many of the
  400 start nodes' shortest paths to their nearest gate pass through the edge. **It is not actual
  pedestrian volume**: every node counts equally and everyone is assumed to walk the shortest
  path. Nodes drawn more densely in OSM get higher counts.
- **Results:** 정문 171 nodes (mean 457 m), 중문 78 (594 m), 남문 76 (611 m), 북문 47 (470 m),
  후문 28 (545 m). The nearest gate by straight line differs from the nearest gate by walking for
  **15%** of nodes. For 12.8% of nodes the 1st and 2nd gates are less than 50 m apart, so their
  assignment is sensitive. Some nodes are 1.4–1.6 km from a gate; the cause was not checked.
- **Limitations:** the polygon and the network are OSM. Whether each gate is a pedestrian gate
  was not verified. Shortcuts through the campus are excluded by design. Direction, stairs, and
  crossings are not yet in the edges.
- The Seoul "도보 네트워크 공간정보" open dataset (data.seoul.go.kr OA-21208) was found as a
  possible OSM alternative (it has crosswalks and overpasses). It was **not downloaded or
  inspected**.

### 10.5 Step 3 — Data-by-data EDA (done; visualisation and hypotheses NOT started)

This is notebook 06, section 3 (3-0 inventory, 3-1 … 3-8, then a summary cell); the same content
is in 07. The user's plan for step 3 also listed dataset 7 (population), which is **on hold**:
administrative-dong population does not represent the people who use a university district.

| Dataset | Key facts established |
|---|---|
| 3-1 `보행자_사고_다발지역.csv` | **Nationwide, not Seoul**: 2,402 rows, 693 in Seoul. Accident count ≥ 7 everywhere, and 57% of Seoul rows are exactly 7, so it looks like a "7+ accidents" selection. `사상자수` equals the sum of the four detailed casualty columns in 100% of rows (double-counting risk). Correlations: accidents–serious injuries 0.92; accidents–fatalities 0.03. Dongjak-gu: 38 hotspots (4th of 25 districts). **3 inside the Soongsil 800 m circle, each with 1 fatality.** No period/year in the file. |
| 3-2 Slope (`서울시_경사도/`) | Contours at 5 m intervals plus spot heights, EPSG:5174. Node heights near Soongsil are 25–171 m; the median 73 m is higher than 84% of Seoul spot heights. Edges ≥ 20 m inside the circle: median slope 5.9%; by length, 33% exceed 8.3% (1/12) and 23% exceed 10%. Steps and paths are steepest. 8.3% is only a reference line, not a validated threshold. Short edges carry large interpolation error. |
| 3-3 Crosswalks (from the user's xlsx) | 21,776 crosswalks, 7,592 intersections, EPSG:5186. Columns: 자치구, 횡단보도관리번호, 교차로관리번호, 횡단보도종류, 보행등유무, 교차로명, X/Y. No pedestrian signal (`보행등유무 = 무`): Seoul 38%, Dongjak 49%, Soongsil circle 33%. **69 crosswalks / 27 intersections inside the circle** (Dongjak 55, Gwanak 14); OSM crossing nodes found only 18. The codes 일단/이단/화살표 are not decoded. |
| 3-4 Audible signals | **`STAT_CDE` is 1 (good) in every one of the 21,426 non-null rows across Seoul**; `VIEW_CDE` and `A073_KND_C` also have one value each. **Converting condition to numbers gives no variation, so it cannot drive an index** (this corrects the §7–§8 assumption that condition could matter). Coordinates are missing in 21% of rows, **not at random**: only in `WORK_CDE = 자료입력` rows, and sharply more since 2021 (70–85% for ESB_YMD 2023–2025). Recently installed signals are the ones missing from maps. Share of crosswalks with a signal within 15 m: 65% with a pedestrian signal, 27% without. Soongsil circle: 40 of 69 crosswalks (58%) within 15 m; median nearest distance 11.6 m. |
| 3-5 Disability facilities | 29,153 rows; 17.4% have unusable coordinates; all rows are "영업". Inside the circle there are 111, of which **64% are housing** (다세대주택, 아파트, …), so most are not walking destinations. `시설유형` strings contain `?` (probably a broken separator in the source). |
| 3-6 Disability status (`장애인+현황(장애유형별_동별)…csv`) | 2025, four-row header (year / 합계 / type × 16 / sex). **District level only, despite "동별" in the name.** Seoul: 384,934 registered disabled people, 40,062 visually impaired (10.4%). Dongjak: 1,427 (16th), 10.3% (16th). The visual-impairment share ranges only 9.4–12.0% across districts. The Soongsil circle spans Dongjak and Gwanak. |
| 3-8 Vulnerable-road-user hotspots, pedestrians (`교통약자다발지점_보행자.csv`) | **2024-based, 3-year data** (confirmed by the user from the download conditions; the file has no year). Exactly 30 rows per district (750), so it is likely the top 30 per district. Totals: 5,068 accidents, 106 deaths, matching the file's total row. **No coordinates and no road-user type column**, so visually impaired people cannot be separated. It is only a "vulnerable pedestrian" reference. `보 기` is empty; hidden `WALK_CNT` is all 0; `MOTOCY_CNT`/`CYCLE_CNT`/`DRK` are not decoded. 15 duplicate (district, place name) rows. Location names are "landmark (direction + metres)" in 47% of rows. Dongjak's top-30 total is 268 (4th). |

Time-basis mismatch to keep in mind: crosswalks 2026-08-24, audible signals 2026-05-28, disability
status 2025, vulnerable hotspots 2024-based 3 years, accident hotspots unknown. Linking past
accidents to current facilities can attach signals installed after the accidents.

### 10.6 Open decisions before visualisation and hypotheses (asked, not yet answered)

1. Audible signals: use "a signal exists near the crosswalk (distance-based)" instead of
   condition. Decide how to separate "no signal" from "signal with missing coordinates".
2. Accident data: Seoul only (693) vs nationwide (2,402) for finding patterns. The proposed
   design is to find and test patterns on the wide data and apply them to Soongsil, because the
   circle has only 3 hotspots.
3. Facilities: whether to drop housing types and keep only destination-type facilities.
4. Disability status: district-level only, so probably background context rather than an edge
   weight.
5. Vulnerable hotspots: reference only, or geocode the place names.

Other open items: the CAU vs Soongsil reference-point rule (10.3); whether to delete
`07_숭실대_3단계_데이터_EDA.ipynb` and the header-only `교통약자다발지점 사고지표.csv`.

### 10.7 Notion and working notes

- The Notion page "TP본 진행상황"
  (https://app.notion.com/p/3e2e935a81c9802b98e5c39dc9bf31ab, in the DartB workspace under
  "DartB 세션 기록(개인) / 개인 기록") holds a Korean summary of step 1, the school-area
  comparison, and the then-open step-2 decisions, plus two figures. **It does not contain the
  step-2 results or the step-3 EDA.**
- The user prefers plain Korean explanations without analogies. Confirm before overwriting or
  deleting anything.
- Notebook editing pattern used: build or modify with `nbformat`, execute with `nbclient`
  (`resources={"metadata": {"path": <project dir>}}`), check for error outputs, then write. After
  editing any `.ipynb`, tell the user to use **Revert File** in the IDE (see §3).

---

## 11. Latest handoff — Seoul relationship EDA and quality audit (2026-09-21)

### 11.1 Current user intent and scope

The long-term goal is still application to the Soongsil university walking area. However,
the user explicitly asked to study the wider available data first, observe relationships,
and eventually validate selected relationships before applying them to the Soongsil radius.
Do not limit the current exploratory sample to the 800 m circle.

The agreed sequence is:

1. Describe accident-hotspot records using accident counts and casualty composition.
2. Compare accident outcomes against crosswalk characteristics across Seoul.
3. Separately compare accident outcomes against terrain slope across Seoul.
4. Let the user inspect the figures and identify interesting patterns.
5. Only after a further request, formulate hypotheses and plan/run statistical tests.
6. Eventually consider application to Soongsil, with the study limitations preserved.

**Current stopping point:** descriptive exploration and missing-value/outlier audits are done.
The user explicitly said not to propose hypotheses or test them yet. Spearman coefficients
already in the notebook are descriptive summaries only; there are no p-values, significance
decisions, regressions, causal claims, or combined crosswalk-plus-slope models.

The user wants actual notebook cells, not just plans in chat, and short Korean Markdown
explanations before each step. This handoff file is English, with exact Korean file/column
names retained for reliable continuation.

### 11.2 Files and notebook structure

Active file: `06_숭실대_반경_1-3단계.ipynb` in this project folder.

Changes in this conversation:

- Section 3-3: appended `display(cross.head(10))` to preview original crosswalk rows.
- Section 3-8: appended `display(vul.head(10))` to preview vulnerable-pedestrian hotspot rows.
- Section 3-1-1: added the nationwide polygon-based outcome profile (`acc_profile`).
- Section 4: added Seoul-wide data loading, crosswalk joins, terrain estimation, descriptive
  figures, exports, and observations. Seven code cells were executed successfully.
- Section 5: added missing-value, numeric-validity, duplication, geometry, and IQR-candidate
  audits. Four code cells were executed successfully, with outputs saved in the notebook.

Useful code-cell IDs for programmatic navigation:

- `acc-profile-code`: earlier national profile.
- `seoul-eda-load`, `seoul-eda-cross`, `seoul-eda-terrain`, `seoul-eda-quality`,
  `seoul-eda-plots`, `seoul-eda-corr`, `seoul-eda-save`: Section 4, in execution order.
- `quality-audit-setup`, `quality-audit-acc`, `quality-audit-cross`,
  `quality-audit-slope`: Section 5, in execution order.
- `seoul-eda-observations` and `quality-audit-brief`: Markdown summaries of executed results.

Older campus-specific cells remain in place. The earlier statement that section 3 is shared
with notebook 07 is historical; this conversation modified notebook 06 only.

### 11.3 Important corrections to earlier advice/code

- The actual accident polygon column is **`다발지역폴리곤`**, NOT
  `사고다발지역폴리곤`. The latter caused the reported `KeyError` and was corrected.
- The first attempted fix only added imports and removed dependence on `PROJ`; it did not
  fix the wrong column name. Do not repeat that diagnosis. The subsequent column correction
  addressed the error shown by the user.
- Polygon shape and EPSG coordinate reference system are different concepts. Both points
  and polygons have a CRS. Accident polygon JSON contains longitude/latitude pairs and is
  treated as EPSG:4326 in this project; use EPSG:5186 for these spatial calculations.
- `사고당_사상자수` = `사상자수 / 사고건수` is **casualties per accident**, not temporal
  recurrence. Earlier assistant wording calling this "repetition" was incorrect.
- `사상자수` is the sum of fatalities, serious injuries, minor injuries, and reported injuries.
  Do not add the total and its components into a composite score as independent quantities.
- The previous "693 Seoul hotspots" wording must now be read as **693 records**, not
  necessarily 693 distinct, independent physical locations; see the duplication findings below.

The old national `acc_profile` cell retains convenience aliases (`사고_발생_규모`,
`피해_규모`, `중대도_사망자수`, `중대도_중상자수`, `사고건수_대비_사상자수`).
These copy existing quantities rather than creating independent predictors. It also uses
`fillna(0)` for some casualty ratios. Section 4 is the newer comparison workflow and correctly
leaves ratios with nonpositive/missing denominators undefined. Existing raw accident data
have no such missing counts, so that legacy difference did not affect the observed results.

### 11.4 Seoul comparison methodology actually implemented

Inputs:

- `보행자_사고_다발지역.csv`: CP949, 2,402 national records; 693 selected by
  `시도시군구명` beginning with `서울`.
- `서울시_교차로_및_횡단보도_시설위치정보_20260824.csv`: 21,776 rows, EPSG:5186.
- `서울시_경사도/등고선 5000/N3L_F001.shp`: 13,704 contour features.
- `서울시_경사도/표고 5000/N3P_F002.shp`: 76,580 spot heights.
  The elevation layers are read in their declared CRS and transformed to EPSG:5186.

The Section 4 cells independently load their inputs. They work with the current directory
set to either this project folder or its parent `python_study`. They do not require running
campus API requests or the earlier campus-network computations.

`seoul_sites` holds Seoul accident polygons. `site_id = acc_row_<original CSV row index>`
identifies a source record, not a unique physical site; it changes if the input is reordered.
`seoul_analysis` holds the joined attributes; the original nationwide `acc_profile` is separate.

Crosswalk features:

- Count crosswalk points intersecting each polygon, including its boundary.
- Also count points within outward polygon buffers of 50 m and 100 m. These are cumulative
  expanded areas, not rings and not distances from the representative point.
- Count distinct `교차로관리번호` among intersecting crosswalk records.
- Compute `보행등없음_비율` using only recognized `유`/`무` values as the denominator.
- Compute nearest distance from the polygon to a crosswalk; it is zero for an internal point.
- A crosswalk may join to multiple overlapping accident polygons. Summed per-record counts
  do not represent a deduplicated Seoul facility total.

Terrain features:

- Available road networks cover university surroundings, not all Seoul. Therefore the new
  calculation is **estimated terrain slope**, not road-aligned/pedestrian-edge slope.
- For each accident polygon, gather contour vertices and spot heights within a 300 m buffer.
- Exclude nonfinite coordinates/heights. Average heights at duplicate sample XY positions.
- Evaluate a globally aligned 20 m grid inside the polygon. Use linear elevation interpolation
  and east/west/north/south offsets of 10 m; calculate gradient magnitude as a percentage.
- A grid location is usable only if all four probes have finite interpolated heights and lie
  within 100 m of a source sample. There is no nearest-neighbor fill outside interpolation support.
- Require at least 10 usable grid locations and at least 80% coverage per polygon.
- Output mean slope, 90th percentile slope, fraction of grid slopes above 5%, sample/grid
  counts, coverage, and status. These settings are exploratory, not validated safety thresholds.
- 678 records pass the coverage criteria; 15 retain missing slope features. They remain in
  crosswalk comparisons and are excluded pairwise only from slope-related figures/statistics.

The figures compare spatial features against accident count, casualties, casualties per
accident, and `(fatalities + serious injuries) / casualties`. The scatter panels show three
outcomes; the correlation table includes all four. Every pair has its own valid sample size.

### 11.5 Executed exploratory outputs

Saved directory: `data/seoul_relationship_eda/`.

| Output | Contents |
|---|---|
| `seoul_site_profiles.csv` | 693 record-level profiles, UTF-8 BOM; no geometry column |
| `seoul_site_profiles.geojson` | The profiles with polygons exported as EPSG:4326 |
| `spearman_exploratory.csv` | Descriptive spatial-feature/outcome rank correlations |
| `pair_counts.csv` | Valid observations for each correlation pair |
| `01_distributions.png` | Crosswalk count, no-signal fraction, mean terrain slope distributions |
| `02_scatter.png` | Nine spatial-feature/outcome scatter panels |
| `03_groups.png` | Casualty severity composition by crosswalk group and slope interval |
| `04_correlation.png` | Correlation heatmap with pairwise sample sizes |
| `05_maps.png` | Spatial distributions; missing slope records shown as gray crosses |

Section 4 also links these PNGs in Markdown for immediate viewing without recomputation.
Code-cell text outputs were saved after execution in a fresh Python process. Figures were
generated with a noninteractive backend and inspected visually. The whole legacy notebook
was NOT rerun; only the newly added workflows were executed. Notebook schema and exports
were validated (693 unique record IDs, EPSG:4326 GeoJSON, five PNGs).

Observed rank correlations across the nine spatial features and four outcomes range from
approximately -0.083 to 0.048. No strong simple monotonic pattern was observed; this is not
proof of no relationship and not a significance-test result. Many severity fractions equal
1.0, which limits differentiation. Records failing slope coverage have median accident count
10, versus 7 for usable records, so slope missingness should not be assumed random.

### 11.6 Missing-value and outlier audit: actual findings

Audits identify candidates only; **no new deletion, winsorization, imputation, deduplication,
or repair was performed**, and the existing analysis exports were not changed by Section 5.
The IQR rule is outside `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`. It does not establish data errors.

**Accident data**

- All original columns have zero missing values nationwide and in the Seoul subset.
- Counts have no conversion failures, infinities, negatives, or fractional values.
- Casualty component sums match totals in every record. No fully duplicate rows.
- All 2,402 polygons parse, are valid/nonempty, and contain their supplied representative point.
- Seoul IQR candidates: accident count 112/693 (upper fence 9.5), casualty count 52/693
  (upper fence 12), casualties per accident 29/693 (upper fence 1.3125). These candidate sets
  can overlap and should not be summed as a number of distinct suspect records.
- The largest casualties-per-accident value is 31/7 = 4.428571 at
  `서울특별시 동작구 사당동(대성문구인쇄 부근)`, `acc_row_145`:
  0 fatalities, 13 serious injuries, 18 minor injuries, 0 reported injuries. Arithmetic is
  consistent; the record was preserved pending source verification.

**Important newly discovered record-identity issue**

- `사고다발지fid` is unique; `사고다발지id` is NOT a per-location key.
- Seoul has only five values of `사고다발지id`: `2022040` (191 rows), `2023060` (134),
  `2024051` (132), `2025083` (121), and `2026122` (115).
- Do not decode these as confirmed collection years or accident periods without source metadata.
- Seoul duplicate counts after the first occurrence: place name 157 rows, exact lon/lat 27,
  exact polygon JSON string 19. Nationwide: place name 502, exact lon/lat 105, polygon string 74.
- These are additional repeated records, not counts of duplicate groups. String equality also
  does not capture all geometrically equivalent polygons.
- Thus the assumption of one independent physical location per row is unverified. The current
  comparison is record-level. Repeated locations may represent different periods or categories;
  neither explanation has been established. Do not blindly drop them or sum their accidents.

**Crosswalk data**

- Of 21,776 rows, one row lacks both X/Y; all other original columns have no missing values.
  The missing-coordinate record is 중랑구 / 서울중랑우체국 / `06-0000023497`.
- Earlier Section 4 already excluded that row from spatial matching, leaving 21,775 points.
- No duplicate crosswalk management IDs, fully duplicate rows, or identical valid XY positions.
- Pedestrian signal values are exclusively `유` (13,523) and `무` (8,253).
- No valid point falls outside a deliberately broad Seoul rectangle after coordinate conversion
  (longitude 126.7–127.3, latitude 37.4–37.75). This is NOT an exact administrative-boundary
  check or proof of positional accuracy.
- Joined no-signal fractions are missing for 101/693 records (14.57%), all because there are
  zero crosswalk points inside those polygons. This is not missing source signal information.
- Internal crosswalk count: 19 IQR candidates (10 or more crosswalks, maximum 13).
  Counts in 50 m and 100 m expanded polygons flag 3 and 1 records respectively.
- Nearest-distance Q1 and Q3 are both zero; IQR mechanically flags all 101 positive distances.
  This is a degenerate rule here, not evidence that those records are erroneous. Maximum
  distance is about 144.02 m.

**Elevation sources and estimated terrain slope**

- No attribute-column missing values in 13,704 contours or 76,580 spot heights.
- HEIGHT has no conversion failures or infinities. Contours span 0–835 m; spots span
  -1.73–835.60 m. Contour height zero: 10 rows; spot height zero: 1 row.
- One spot height is negative (-1.73 m), UFID `1000037608098F00210000000000347961`.
  A negative elevation is not automatically an error; retain pending verification.
- Height IQR candidates: contours 1,043 (above 487.5 m), spots 6,655 (above about 104.6 m).
  High-elevation terrain can be valid, so no mountain data were removed.
- Spot-point geometries have no missing, empty, or invalid features. No duplicate XY positions
  or conflicting spot heights at identical XY were found. Full contour topology and physical
  elevation accuracy have NOT been independently validated by this audit.
- Derived slope missingness: 15/693 (2.16%), all `격자충족부족`; these are coverage failures,
  not 15 missing HEIGHT values in the source.
- No negative/infinite derived slopes; slope-share and coverage fractions stay within [0, 1].
- Mean slope IQR candidates: 34/678 (5.01%), above about 9.2802%; maximum 26.6622%.
- P90 slope IQR candidates: 41/678 (6.05%), above about 17.8268%; maximum 49.9657%.
- Mean-slope extremes include multiple 홍은사거리 records. Terrain relief, interpolation,
  road structures, and repeated location records need inspection before calling these errors.

### 11.7 What to do next, and what not to infer

The most recent user request was to save this English handoff. Data-quality results have been
briefed; no additional data cleaning has been authorized or implemented in this turn.

For a future requested continuation, the highest-priority unresolved checks are:

1. Establish accident dataset selection criteria, the five repeated IDs' meanings, and time
   coverage; resolve the analysis unit before deduplicating or treating records as independent.
2. Inspect flagged accident and terrain records against source context. Keep a decision log
   distinguishing verified errors from valid extremes. Do not delete based solely on IQR.
3. If requested, examine slope interpolation support, settings, and spatial artifacts; the
   current terrain estimates cannot be described as measured road/crosswalk grades.
4. Keep original facility absence distinct from unknown attributes, and retain the nonrandom
   coverage issue when comparing terrain features.
5. Wait for the user's chosen patterns before hypotheses or inferential tests. If later testing
   patterns discovered in these same data, label the work exploratory and discuss independent
   validation, repeated/overlapping records, spatial dependence, and multiple comparisons.

No exposure data (pedestrian/vehicle volume) or confirmed accident period is available in the
current workflow. Crosswalks are dated 2026-08-24; temporal alignment is unresolved. Raw
accident counts are not exposure-adjusted risk, and these records were already selected as
hotspots. No conclusion about causes or visually impaired pedestrians specifically is justified.

### 11.8 Practical continuation notes

- Environment used: Windows PowerShell, Python 3.14; pandas, GeoPandas, Shapely, SciPy,
  matplotlib, pyogrio, and nbformat were available. This directory is not a Git repository.
- Read notebook JSON by cell ID to avoid dumping embedded base64 figures with broad `rg`
  searches. Preserve all unrelated existing cells and outputs when patching.
- PowerShell piping of literal Korean Python source caused `?` substitutions in this session.
  Setting only `PYTHONIOENCODING` fixes Python output, not necessarily the pipe input. Prefer
  reading/executing UTF-8 notebook sources by ASCII cell ID, a UTF-8 script file, or explicitly
  set the PowerShell pipeline encoding as well. Never infer corrupted CSV headers from a
  terminal-rendering problem; inspect Unicode escapes or decoded source names.
- Section 4 terrain calculation takes several minutes; Section 5 audits read the saved
  profiles and are much faster. Section 5 setup expands pandas display columns for inspection.
- When an IDE already has the notebook open, use its reload/revert-from-disk function only
  after protecting any unsaved user edits. Disk edits can otherwise appear absent in the UI.
- Revalidate notebook structure after edits. Existing output files are generated artifacts;
  rerunning Section 4 overwrites those named exports, while the audit reads them without changing them.

---

## 12. Cell reorder and data-quality cleaning moved before 3-1 (Claude session, 2026-09-21)

**What the user asked for:** missing-value / outlier checking had been done last (old Section 5). It
should come first. The user asked to (a) place those cells before `3-1`, (b) delete them if they were
not basic per-dataset checks, and (c) redo basic missing/outlier checking **and handling** for *every*
dataset the notebook uses (not only accidents, crosswalks and slope).

**What was done in `06_숭실대_반경_1-3단계.ipynb` (now 81 cells):**

- The old Section 5 (10 cells, ids `quality-audit-*`) was **deleted**. It was not a basic per-dataset check:
  it covered only 3 datasets, part of it read the Section 4 output `seoul_site_profiles.csv` (derived
  tables, so it cannot run before 3-1), and it did no handling. Its accident findings (repeated
  records, IQR candidates) are re-derived in the new cells. The derived-table checks (join-result
  missingness 101/693, slope-coverage missingness 15/693) are no longer in the notebook; §11.6 above
  still records them, and Section 4-4 shows missingness of the joined table.
- New cells `clean-*` (3-0-1 … 3-0-10) sit right after the 3-0 loading cell and before `3-1`.
  Each dataset has a Markdown cell (what is checked / what is done) and a code cell.
  The overview table in the step-3 intro cell (`a214a6b9`) has a new 3-0 row.
- **Principle:** raw variables (`acc`, `cross`, `aud`, `fac`, `disab_raw`, `vul`) are never modified.
  Handling produces `acc_clean`, `cross_clean`, `aud_clean`, `fac_clean`, `disab_clean`, `vul_clean`.
  No rows are deleted. Missing values stay missing (flagged), except one value derived by arithmetic.
  IQR outliers are only flagged. Every action is appended to `clean_log` and shown in 3-0-9.
- Cells 3-1 onward and Section 4 still use the **raw** variables. The notebook confirms that nothing
  in them changes: 69 crosswalks in the circle before and after; 24,075 facility rows with coordinates
  before and after; the 4 mislocated crosswalks are 200 m+ from every Seoul accident polygon.
  The visualisation/hypothesis step should use the `*_clean` frames.
- The `07_...` notebook copy was not touched.

**Findings that are new (not in earlier sections):**

| Dataset | Finding | Handling |
|---|---|---|
| Crosswalks | 4 rows sit 11–18 km from the other crosswalks of the same intersection (양천구 목동파크자이107동앞, 광진구 용곡삼거리(연등)1, 성북구 래미안아트리치 ×2). Everything else is within 198 m (99.9% within 104 m). The 1,000 m threshold sits in an empty gap. None is in the Soongsil circle. | coordinates blanked, `좌표상태='위치이상'`, originals kept in `X좌표_원본`/`Y좌표_원본` |
| Audible signals | Missingness of coordinates, direction (`DRN_CDE`, `POS`), status, `CTK_MGRNU`, `FRM_CDE` sits **100%** in `WORK_CDE=1` rows. `XGEO` is a junk object-reference string; `MNG_AGEN` is 99% empty. 30 rows have `ESB_YMD` later than `CAE_YMD`. `MK_CPY` has 143 spellings (93 after removing `(주)`/`㈜`). `SL_NUM='0'` (2,874 rows) looks like a placeholder. | flags; columns dropped in clean copy; `제조사` normalised; `'0'`→NaN. `CAE_YMD` meaning is not verified, so columns are named `ESB_날짜`/`CAE_날짜` |
| Facilities | 5,078 rows (17.4%) have (0, 0) coordinates but all have addresses (geocoding could recover them; not done). 42 impossible `설립일자` (e.g. 20201310). `시설대표자성명` is 100% empty. `?` in 9 `시설유형` values is a broken middle dot. 884 rows share a `시설ID` with another row but only 7 rows repeat (name, type, address). | (0,0)→NaN, dates→NaT, `?`→`·` in a new column, ID-repeat flag |
| Disability status | One cell `-` (용산구 안면 여자). `계 = 남자 + 여자` proves it is 0. After filling, all three sum identities hold (gender, type total, district total). | filled with 0 (arithmetically derived) |
| Vulnerable hotspots | `보 기` is 100% empty, `WALK_CNT` is constant 0. 15 repeated (구, 지점명); 1 pair is identical in every column (동작구 성대약국, 18 accidents). | columns dropped in clean copy; repeats flagged, not removed (keeps the 30-rows-per-district structure) |
| Slope layers | No missing values, no invalid/duplicate geometry, contour `HEIGHT` is always a multiple of 5 and equals `CONT`; spot `NUME` equals `HEIGHT`. 12 features have `HEIGHT ≤ 0` (10 contours, 2 spots), all ≥ 1.9 km from the circle. A "spot vs nearest contour" check was tried and dropped: 1,319 of 48,315 spots within 30 m differ by more than 5 m, the cause could not be separated, and it took 6 minutes. | kept; listed in `elev_review` |

Accident data: no missing values, no logic errors; repeated records and IQR candidates are only
flagged (`반복_*`, `IQR후보_*`, `서울여부`), consistent with §11.6. The analysis-unit question
(what the five `사고다발지id` values mean) is still open.

Subway voice-guidance CSV is not used in notebook 06, so it was not checked here.

**Reminder:** the notebook may be open in the IDE. Use **Revert File** before running or saving.
A backup of the notebook before this edit was written to the session scratchpad only.

---

## 13. Notebook 06 growth after §12: Sections 4-2-1 … 8 (2026-09-21, later sessions)

> Provenance: this section was written by reading `06_숭실대_반경_1-3단계.ipynb` (109 cells, last saved
> 22:26, no error outputs) and its saved outputs. The conversations that produced these cells were not
> available, so the *reasons* behind each step are taken from the notebook's own Markdown. Nothing was
> rerun while writing this. **Still no hypotheses and no significance tests anywhere in the notebook**
> (every step says so); all coefficients are descriptive Spearman/Pearson values.

### 13.1 Where the notebook stands

Cell count 81 → 109. Section numbering is now: 1 university district, 2 segments/distances,
3 data EDA (3-0 cleaning, 3-1 … 3-8), 4 Seoul hotspots × crosswalk/terrain, **5 ring slope retry,
6 hotspot typology, 7 intersection-type hotspots, 8 merged accident indicators**. The "old Section 5"
(quality audit) mentioned in §11/§12 is gone; the new Section 5 is unrelated to it. Cells 3-1 onward
still work on the raw frames (unchanged from §12); the notebook does not say the later sections use
`*_clean`, so verify before assuming.

Cell IDs by section: 4-2-1 `seoul-eda-cross21*`, 4-2-2 `seoul-eda-rel*`, 4-2-3 `seoul-eda-cnt*`,
4-3 `seoul-eda-terrain*`, 4-3-1 `seoul-eda-slope*`, 4-3-2 `seoul-eda-slope-bin*`, 5 `ring-*`,
6 `typ-*`, 7 `ix-*`, 8 `mg-*`. Markdown summaries: `typ-brief-md`, `ix-brief-md`, `mg-brief-md`.

The user's own note in cell `9aad8442` after 4-2-3: "솔직히 크게 유의미한 관계는 못발견함" (honestly, no
strongly meaningful relationship found).

### 13.2 Section 4 additions (crosswalk and slope, 9 accident indicators)

The nine accident indicators are the names used in 3-1-1: `사고_발생_규모`, `피해_규모`,
`중대도_사망자수`, `중대도_중상자수`, `사망자_비율`, `중상자_비율`, `경상자_비율`, `부상신고자_비율`,
`사고건수_대비_사상자수` (copies of Section 4-1 columns, not new variables).

- **4-2-1 crosswalks inside polygons:** 592 of 693 polygons contain crosswalks, 101 do not. Count per
  polygon: mean 3.62, median 3, max 13. 1,430 distinct crosswalks inside polygons (by management ID):
  이단(화살표있음) 57.2%, 일단(화살표없음) 34.6%, 이단(화살표없음) 4.1%, 일단(화살표있음) 3.1%,
  대각선 1.0%, 삼단 0 (Seoul-wide shares are close: 53.0 / 39.2 / 3.2 / 3.1 / 1.5). Pedestrian signal
  유 881 / 무 549 inside polygons. Per-point counts are per polygon, so overlapping polygons count a
  crosswalk twice; the composition table deduplicates by management ID.
- **4-2-2 / 4-2-3:** Spearman of crosswalk indicators (counts and shares by type, signal presence)
  against the nine indicators, plus crosswalk-count bins (0, 1–2, 3–4, 5–6, 7+). Largest |r| ≤ 0.20.
  The four ratio indicators sum to 1 and are not independent.
- **4-3-1 terrain slope × nine indicators:** Spearman and Pearson side by side, with a sign label
  (`+`, `-`, `엇갈림` when they disagree). 678 usable polygons; |r| ≤ 0.09. The 15 excluded polygons
  have median 10 accidents vs 7 (slope missingness is not random; do not generalise to all Seoul).
- **4-3-2 slope quintiles:** equal-count bins from 0.1–1.2% to 5.2–26.7% mean slope; indicator means
  barely move (e.g. accident count 8.29, 8.07, 8.48, 7.84, 7.78).

### 13.3 Section 5 — ring comparison (hotspot vs. surrounding ring)

Problem statement written by the user/assistant: no clear relation in Section 4, and the data are a hard
setting for finding one. Reasons listed: only already-selected hotspots (7+ accidents, so counts span
just 7–22), no exposure data, slope diluted by averaging over the whole polygon, five unexplained
`사고다발지id` values (unknown collection period).

Retry: compare each polygon's slope with the ring just outside it (100 m and 200 m wide, other hotspot
polygons removed from the ring), paired per site so hilly-vs-flat neighbourhoods do not mix in. Crosswalk
variables are not used here. Same slope method as 4-3 (20 m grid, ±10 m offsets, ≥10 valid cells and
≥80%); elevation samples taken within 310 m. The cell takes about 10 minutes.

Results (executed):

| | inside | ring 100 m | ring 200 m |
|---|---|---|---|
| usable / insufficient grid | 678 / 15 | 679 / 14 | 687 / 6 |

- Inside-mean slope matches the 4-3 value to within 0.035 percentage points (sanity check passed).
- Paired difference (inside − ring), mean slope: median −0.58 (100 m, n=666) and −1.24 (200 m, n=674);
  the hotspot is *less* steep than its ring in 68.8% and 76.0% of pairs. The 90th-percentile and
  share-above-5% metrics point the same way (ring steeper in 76–82% and 61–70%).
- Slope difference vs. the nine indicators: |Spearman| ≤ about 0.09 for both ring widths (e.g. 0.09 with
  `경상자_비율`, −0.08 with `중상자_비율` at 100 m).
- Caveats already in the notebook: terrain slope, not road slope; rings include buildings, rivers, parks;
  no exposure; "hotspot" means frequent, not dangerous. The observation that hotspots sit on flatter
  ground than their surroundings is descriptive and may just reflect that people walk on flat streets.

### 13.4 Section 6 — hotspot typology from accident columns

Goal: define what kind of place each hotspot is, using only the accident columns first (5 columns; total
casualties excluded as a sum of components). Notebook's own findings (Korean summary is in `typ-brief-md`):

- Accident count cannot exceed deaths + serious injuries: 563 of 693 records are equal, 130 are smaller
  (one accident with several deaths/serious injuries). All 155 records with minor/reported injuries have
  count below casualties, so count appears to be based on death/serious cases with minor/reported added on
  top (needs confirmation from the data documentation).
- Deaths and serious injuries share the accident count (death −0.37 correlation; mean count stays 8.1–8.2).
  Casualties per accident correlate 0.75 with minor injuries. Polygon area is essentially constant
  (19,519–19,721 m², CV 0.25%) so it cannot separate types.
- Type rule 1, damage composition: `중상 위주` 390 (56%), `사망 포함` 191 (28%), `경상·신고 포함` 112 (16%).
  Rule 2, scale: 7 accidents 392 (57%), 8–9 189, 10+ 112. Composition barely shifts with scale
  (death-included 26% → 29% → 31%). 130 records (18.8%) flagged as multi-victim.
- Place kind from the name in parentheses (keyword rules, first match wins): subway station 160, hospital/
  pharmacy 130, intersection 118, shops/buildings 74, market 59, school 34, other 118. Composition differs
  little by kind (death-included 21% school … 34% market; serious-dominant 51% subway … 64% hospital).
  These type names are this project's own, not official classes; the name-based classification is rough.

### 13.5 Section 7 — intersection-type hotspots joined to crosswalk data

Idea: hotspot names such as "…교차로/사거리/삼거리/오거리/네거리" identify intersection-type hotspots, which
can be tied to the crosswalk file's intersection (`교차로관리번호`). The link is done by **location**, not
by name: the intersection ID with the most crosswalks inside the polygon (ties → nearest to the polygon
center). The name is only a validation check.

- 254 of 693 (37%) names contain an intersection word; 238 link to an intersection, 16 have no crosswalk
  inside. Intersections touching a polygon: 1 → 136, 2 → 81, 3+ → 21 (polygon radius about 80 m does not
  fit one intersection exactly). Linked intersection name matches the hotspot name for 172 (72%); the rest
  are either spelling differences or wrong links (not removed).
- Death-included share: 31.5% for intersection-type vs 25.3% for others; serious-dominant 52.0% vs 58.8%;
  minor/reported 16.5% vs 15.9%; mean accident count 8.24 vs 8.08.
- Intersection crosswalk info (count, types, no-signal share) vs the nine indicators: |r| ≤ 0.16
  (largest −0.16 with `부상신고자_비율`, only 28 hotspots have reported injuries). On the 172 name-matched
  hotspots the largest is −0.23 (no-signal share vs casualties-per-accident; −0.11 on all 238), likely one
  of many cells. Composition group means are similar (crosswalk count 4.7–4.9, no-signal share 0.25–0.30).

### 13.6 Section 8 — merged accident indicators, re-examined

Because deaths/serious counts and ratios are sparse or overlapping, three merged variables were made:
`사망중상자수` = deaths + serious, `사망중상_비율` = death share + serious share, and dropped
`경상자_비율` (it is the remainder). Five indicators remain: `사고_발생_규모`, `피해_규모`,
`사고건수_대비_사상자수`, `사망중상자수`, `사망중상_비율`. The ring slope difference was not recomputed
(too slow).

- Result: the merge did not change the picture. Max |r|: crosswalks in polygon 0.18 (single-arrow type
  count vs accident scale, only 44 such crosswalks), terrain slope 0.09, intersection crosswalk info 0.15
  (no-signal count/share vs `사망중상_비율`, n=238). Nine-indicator maxima were 0.20, 0.09, 0.16.
- `사고_발생_규모` vs `사망중상자수` rank correlation is 0.92, i.e. nearly the same information.
- Intersection-type vs others: `사망중상_비율` 0.962 vs 0.967 and `사망중상자수` 8.43 vs 8.34 are equal; the
  6-point gap in death-included share (7-3) appears only when deaths are viewed alone (191 of 693 hotspots
  have a death, so it is unstable). Deaths plus serious injuries are 96–97% of casualties, so the merged
  variable is practically the serious-injury count.

### 13.7 Cumulative reading and what not to do

Across crosswalk variables, terrain slope, the paired ring slope difference, the typology, and the
intersection link, no simple monotonic relationship above |r| ≈ 0.2 has appeared. This is not proof of no
relationship and not a significance test. The limitations stay: hotspots were preselected (narrow 7–22
range), no exposure data, unknown collection period, terrain slope rather than road slope, crosswalk
file dated 2026-08-24, repeated records (§11.6), and the name-based typology is coarse.

Do not: propose hypotheses or run tests unless the user asks; delete or deduplicate records; treat an
isolated larger coefficient (−0.23, 0.18) as a finding; describe results as showing anything about
visually impaired pedestrians specifically. Note 8-2 and 7-5 already state that isolated cells are likely
chance among many comparisons.

Possible next steps (untaken, for the user to choose): resolve the meaning of `사고다발지id` and the
collection period; use a non-hotspot comparison group; attach the typology to Soongsil-area records;
return to the Soongsil edge-difficulty work in §5/§9.6 with the descriptive results as context.

**Reminder:** the notebook may be open in the IDE; use **Revert File** before running or saving.

---

## 14. Seoul-wide hypothesis verification — direction notebook (Claude session, 2026-09-22)

This section records **only one Claude Code session**: the creation of `08_서울전체_가설검증_방향.ipynb`.
It is a direction outline (12 Markdown cells, no code, nothing executed, no data loaded, no tests run).

### 14.1 What changed in scope

The user now wants four hypotheses verified (H5-H8, below) and wants the analysis to cover **all of Seoul**,
not only the Chung-Ang / Soongsil 800 m circles. This **supersedes** the "do not propose hypotheses or run
tests yet" instruction at the top of this file and in §11/§13. The user still asked only for a direction
outline in this session, so **no hypothesis test has been run yet.**

The user's hypothesis table (pasted into the session; Korean, quoted as given):

| # | Hypothesis |
|---|---|
| H5 | 버스정류장 50m 안 횡단보도는 그 외보다 음향신호기 설치율이 높다(또는 낮다). If used as an evaluation axis: public-transport accessibility |
| H6 | 중앙대와 숭실대는 같은 동작구인데도 위험도 점수에 유의미한 차이가 있다 |
| H7 | 같은 학교 안에서도 출입문마다 음향신호기 접근성 격차가 크다 |
| H8 | (음향신호기가 밀집한 구간에서도 무신호·음향 없는 횡단보도가 가까이 존재해서,) 설비의 밀집이 곧 통학로 전체의 안전을 뜻하지는 않을 것이다 |

Notebook 06 (`06_숭실대_반경_1-3단계.ipynb`) was read as reference and **not modified**. Its cleaned frames
(`cross_clean`, `aud_clean`, ...) and the 15 m audible-signal-to-crosswalk rule from 3-4-1 are the intended
inputs. Its Sections 4-8 (accident-hotspot exploration, no clear relationships) are explicitly **not** to be
reused as evidence for these tests.

### 14.2 File

`08_서울전체_가설검증_방향.ipynb`, created with `nbformat` (validated, not executed). Cell IDs: `h-title`,
`h-summary` (added later at index 1, a one-glance summary requested by the user), `h-table`, `h-common`,
`h-h5`, `h-h6`, `h-h7`, `h-h8`, `h-data`, `h-rules`, `h-decide`, `h-order`.
The notebook may be open in the IDE; use **Revert File** before running or saving (see §3).

### 14.3 Direction chosen for each hypothesis (draft, not confirmed by the user)

> **Superseded for H5-H8 wording, scope and tests by §14.9 (2026-09-22).** Keep this subsection only as the
> earlier draft; its data needs and pitfalls still apply.

- **Shared base:** a Seoul-wide crosswalk master table, one row per crosswalk: ID, district, EPSG:5186
  coordinates, pedestrian-signal flag, crosswalk type, audible signal within 15 m (sensitivity 10/20/30 m),
  bus stop within 50 m, nearest university/gate, high-density flag. The 4 mislocated crosswalks stay without
  coordinates.
- **H5:** unit = crosswalk. Compare audible-signal rate for crosswalks within 50 m of a bus stop vs others.
  Two-sided chi-square/Fisher with odds ratio and CI, plus logistic regression controlling for
  pedestrian-signal presence, crosswalk type and district. Audible signals only make sense at crosswalks that
  have a pedestrian signal (38% of Seoul crosswalks have none), so this must be controlled. Cluster by
  `교차로관리번호`. Repeat with 30 m and 100 m. Road width/lane count are unavailable (limitation).
  If significant, bus-stop proximity becomes a candidate "public-transport accessibility" axis of the index.
- **H6:** rewritten as "even within the same district, university areas differ in risk score", unit = university
  area (Kakao representative point + 800 m, applied uniformly). Candidate tests: variance decomposition
  (between-district vs within-district), permutation test on same-district pairs. Blocked until a risk score
  exists (team step 4). To avoid circularity, compare score **components** first. The CAU (OSM main gate) vs
  Soongsil (Kakao representative point) reference-point mismatch (§10.3) must be unified. Areas spanning two
  districts (Soongsil: Dongjak and Gwanak) need an assignment rule. Report effect size, not only p-values.
- **H7:** rewritten as "gate-to-gate access gaps inside Seoul universities", unit = gate. Metrics: share of
  crosswalks with an audible signal within R m (R = 100/200 m) of the gate, and walking distance to the nearest
  signalled crosswalk (straight-line buffer first, then the §10.4 network method extended to other
  universities). Candidate tests: mixed model with university random effect / ICC, with a baseline gap from
  random points on the campus boundary to define "large". Universities with only one Kakao gate cannot define
  a gap and drop out (count them first). Gates < 50 m apart share crosswalks (12.8% of Soongsil nodes were
  sensitive to this).
- **H8:** unit = grid cell (e.g. 250 m) or buffer. "Dense" = top 25% or 10% audible-signal density; also use a
  signal-to-crosswalk **ratio**, since counts scale with crosswalk number. "No signal / no audio" must be split
  into (a) no pedestrian signal and (b) pedestrian signal but no audible signal; which one the user means is
  open. Candidate analysis: no-audio share by density quantile with a trend test, share of dense cells that still
  contain a no-audio crosswalk with CI, distance from such crosswalks to the nearest signalled one. Results can
  say only that unsignalled crosswalks remain, not anything about safety itself.

### 14.4 Data status

| Needed | Used by | Status |
|---|---|---|
| Crosswalks (`cross_clean`) | H5-H8 | Available (21,775 rows with coordinates) |
| Audible signals (`aud_clean`) | H5-H8 | Available; 21% lack coordinates (concentrated in `WORK_CDE=자료입력`) |
| Seoul bus-stop coordinates | H5 | **Missing** (Seoul Open Data Plaza download needed; exact dataset not chosen) |
| Seoul university list and reference points | H6, H7 | **Missing** (Kakao Local API; only Soongsil exists) |
| University gate coordinates | H7 | **Missing** (Kakao `입출구`, Soongsil only) |
| University campus polygons | H7 walking-distance version | Soongsil only (OSM) |
| Risk-score definition | H6 | **Missing** (team step 4) |

### 14.5 Cross-cutting rules written into the notebook

Multiple-comparison correction across the four hypotheses (e.g. Holm); thresholds (50 m, 15 m, density
cutoff) fixed before looking at results, with later changes labelled exploratory; effect sizes and CIs, not only
p-values (Seoul-wide samples are large); cluster by intersection/grid for spatial dependence; missing
coordinates mean "location unknown", never "no device" (sensitivity analysis for the worst case); time bases
differ (crosswalks 2026-08-24, audible signals 2026-05-28, so later installations are absent); no claims about
visually impaired pedestrians' safety or accident risk.

### 14.6 Noted risk found while writing

In 3-4, 27% of crosswalks **without** a pedestrian signal still had an audible signal within 15 m, which
suggests the 15 m match can pick up a neighbouring crosswalk's device. The plan is to re-check the matching
rule (assign each signal to its single nearest crosswalk) when building the master table.

### 14.7 Open decisions for the user (not answered)

1. Whether the Seoul-wide rewrites of H6 and H7 match the intent.
2. Meaning of "무신호·음향 없음" in H8 (a, b, or both), and whether the parenthetical is part of the hypothesis.
3. University scope: all Seoul universities, four-year only, or only those with 2+ gates found.
4. Whether the risk score (index design) is in scope, or components are compared instead.
5. Download the bus-stop dataset for H5.

### 14.8 Suggested order (draft)

Confirm decisions and obtain bus stops; build the crosswalk master table (re-check signal matching); H5; H8;
collect universities and gates; H7; define risk score, then H6; apply multiple-comparison correction.

### 14.9 Direction change by the user (Claude session, 2026-09-22)

The user pasted a revised hypothesis table and asked to change the direction. `08_서울전체_가설검증_방향.ipynb`
(still 12 Markdown cells, no code, nothing executed) was rewritten to match; a backup of the previous version is
only in the session scratchpad. **These wordings and tests supersede §14.3.**

| # | New hypothesis (user wording, summarized) | Test given by the user | Scope |
|---|---|---|---|
| H5 | Crosswalks within 50 m of a bus stop have an audible-signal installation rate that **differs** from other crosswalks (two-sided). Evaluation axis: public-transport accessibility | Compare installation rates of the two groups, chi-square | Seoul-wide |
| H6 | CAU and Soongsil are in the same Dongjak-gu, but compared per commute-route segment their risk-score distributions differ | Compare per-segment/point risk-score distributions of the two schools, Mann-Whitney U | CAU vs Soongsil only |
| H7 | Gaps in audible-signal access between gates of the same school are large | Count audible signals per gate, compute coefficient of variation (CV) per school | Seoul universities |
| H8 | Even in dense audible-signal zones, no-signal/no-audio crosswalks are nearby, so density does not mean the whole commute route is safe | Mean distance from dense zones to the nearest no-audio crosswalk; whether one exists within 100 m | Seoul-wide |

**The pasted table mentioned "Tier1 6개교" (H7). The user then said to ignore it:** H7 is not restricted to six
schools (all Seoul universities; exact scope still open), and H5/H8 are Seoul-wide. H6 stays a two-school comparison
because that is how the new wording reads (§14.1's "H6 for all Seoul university districts" no longer applies).

Notebook 08 keeps the user's tests as the primary analysis and lists supplements as *proposals*, marked as such:

- **H5:** stratify or regress on pedestrian-signal presence (38% of Seoul crosswalks have none), cluster by
  `교차로관리번호`, sensitivity for 30/100 m and for signals with missing coordinates.
- **H6:** Mann-Whitney U assumes independence but segments are spatially adjacent, so p-values will be too small;
  add an effect size and a block-level permutation or intersection-level aggregation. Still needs a risk score,
  a definition of "commute route", and a CAU network rebuilt under the Soongsil rule (Kakao representative point +
  800 m, campus interior removed); the CAU vs Soongsil reference-point mismatch (§10.3) is unresolved.
- **H7:** CV is undefined for one-gate schools and for all-zero counts, unstable with two gates, and counts scale
  with nearby crosswalk numbers (also report the share of crosswalks with a signal). "Large" needs a threshold set
  before looking (or a random-boundary-point baseline). CV alone is descriptive, not a test.
- **H8:** without a comparison (low-density zones, all Seoul) the 100 m result cannot be interpreted, because dense
  urban crosswalks are often within 100 m anyway. "무신호·무음향" is computed both ways: (a) no pedestrian signal and
  no audible signal, (b) no audible signal regardless of pedestrian signal. Missing-coordinate signals can make
  crosswalks look "no-audio", which shortens the distance; needs a sensitivity analysis.

**Still open:** risk score inside scope or components only (H6); university scope for H7; whether CAU is also moved
to the Kakao representative point; bus-stop download (H5); thresholds for "large" (H7) and "dense" (H8).
**Data status is unchanged from §14.4 except:** H6 additionally needs a CAU network and a commute-route definition.
No test has been run. The notebook may be open in the IDE; use **Revert File** before running or saving (§3).

### 14.10 Bus data check and H6 ordering (Claude session, 2026-09-22, later)

- **H6 order:** the user wants H5, H7, H8 checked first, and H6 last, applied only to CAU and Soongsil. Notebook 08
  summary, decisions and order cells were updated. Whether H6's risk-score components should be chosen from the earlier
  results was not stated by the user (open).
- **Bus file placed by the user:** `2026년_버스노선별_정류장별_시간대별_승하차_인원_정보(08월) (1).csv`.
  CP949; 42,578 rows (route x stop sequence), 57 columns; usage month 2026-08, registered 2026-09-03; no missing,
  negative or non-numeric values; 12,524 stops (`표준버스정류장ID`, 9 digits), 12,349 ARS numbers.
  **It has no coordinate column, so it cannot build H5's "within 50 m of a bus stop" by itself.** It must be joined to
  a Seoul bus-stop location table on the standard ID (likely) or the ARS number; the key match is unverified.
- Cleaning notes: 120 `(가상)` stops (depot/terminal, ARS `~`) to drop; about 1,800 stops with IDs starting 2xx look
  non-Seoul; 1,237 rows repeat the same (stop, route) and must be aggregated per stop; 8 river-bus rows are not road
  stops; one ARS maps to several standard IDs in 84 cases; 98 standard IDs have more than one spelling of the name.
  Hourly boardings/alightings could be used to stratify by stop size (supplement only).
- Nothing in the notebook was executed; no crosswalk-to-stop join was made.

### 14.11 Bus-stop location file checked (Claude session, 2026-09-22, later)

- File: `서울시버스정류소위치정보(20260902).xlsx` (a real xlsx, sheet `Data`). Converted to
  `서울시버스정류소위치정보(20260902).csv` (UTF-8 BOM) in this folder; the xlsx is untouched.
- 11,236 rows; columns `NODE_ID`, `ARS_ID`, `정류소명`, `X좌표`, `Y좌표`, `정류소타입`; no missing values, no
  duplicate IDs. Coordinates are lon/lat (WGS84 by appearance), all inside Seoul, none 0/0. Types: 일반차로 6,251,
  마을버스 4,175, 중앙차로 405, 가로변시간 256, 가로변전일 141, 한강선착장 8 (drop).
- **Join key confirmed:** ridership `표준버스정류장ID` = `NODE_ID`. 10,656 of 12,524 ridership stops match, with 100%
  ARS agreement. The 1,868 that do not match: 120 virtual, 1,741 outside Seoul (ID 2xx), 7 Seoul stops. 580 location
  stops have no ridership (mostly 가로변시간/전일). H5 group definition needs only locations; ridership is an optional
  stratifier.
- **Group sizes for H5 (no outcome variable looked at):** of 21,775 crosswalks with coordinates, 9,717 (44.6%) are
  within 50 m of a stop and 12,058 are not; 30 m: 4,903; 100 m: 16,568 (76.1%). Median nearest-stop distance 56.1 m.
  Share within 50 m is 44.5% (pedestrian signal present) vs 44.9% (absent), so pedestrian signal is nearly unrelated
  to stop proximity, but it still determines whether an audible signal can exist; keep the stratification. District
  shares range 28.7% (중구) to 63.1% (동작구), so control for district.
- No test has been run; audible-signal outcomes were not joined. Open: whether 마을버스 stops count as "bus stops".

### 14.12 H5 now uses only the bus-stop location file (Claude session, 2026-09-22, later)

At the user's request, the H5 section of notebook 08 was rewritten around `서울시버스정류소위치정보(20260902)`
(xlsx, with the CSV conversion). The ridership CSV (`2026년_버스노선별_정류장별_시간대별_승하차_인원_정보(08월) (1).csv`)
is **not used** for H5 any more: it has no coordinates and the group definition does not need it. Consequences:
the `NODE_ID` join, virtual-stop and non-Seoul cleanup, and ridership stratification were removed from the plan.
H5 uses 11,228 stops (8 river-bus piers dropped). Group sizes recomputed on that set (same as before): 50 m: 9,717
near / 12,058 other of 21,775 crosswalks; 30 m: 4,903; 100 m: 16,568. Excluding 마을버스 stops (4,175) leaves 7,119
crosswalks within 50 m (32.7%), proposed as a sensitivity check. Stop-size (ridership) control is not available.
Nothing was executed as a test; no audible-signal outcome was joined.

### 14.13 H5 decision: 마을버스 stops included (2026-09-22)

The user confirmed that village-bus (마을버스) stops count as bus stops in H5. Primary analysis uses all 11,228 stops
(river-bus piers dropped); excluding 마을버스 (7,119 crosswalks within 50 m) and center-lane-only remain sensitivity checks.
Notebook 08 (`h-h5`, `h-decide`) was updated. No test has been run.

### 14.14 H5: pedestrian-signal column dropped from the main analysis (2026-09-22)

The user decided not to use the `보행등유무` column in H5's main analysis (§14.3/§14.9 had proposed stratifying on it).
Reasons recorded: share of crosswalks within 50 m of a stop is 44.5% (signal present) vs 44.9% (absent), so omitting it
should not bias the stop-proximity comparison; and 27% of crosswalks without a pedestrian signal still had an audible
signal within 15 m (06 §3-4), so the column or the matching rule is unreliable as a control.
- Main test: chi-square on near-stop vs other x audible signal matched (two-sided), odds ratio with CI; supplement:
  district stratification (CMH) or logistic regression on district only; cluster by `교차로관리번호`.
- Sensitivity only: restrict to crosswalks with a pedestrian signal (13,522). Also 30/100 m, excluding 마을버스, and the
  worst case for signals with missing coordinates.
- Limitation: the denominator includes crosswalks that cannot have an audible signal (about 38% of Seoul), so the rate is
  "share of all crosswalks with a matched signal", lower in level and noisier; do not describe it as a rate among
  signalled crosswalks. The column is still used in H8 (definition (a)) and stays in the master table.
- Notebook 08 updated: `h-summary`, `h-common`, `h-h5` (the user's inline note in `h-h5` was replaced by this decision).
  No test has been run.

### 14.15 H5 groups built and inspected visually, no test yet (Claude session, 2026-09-22)

New files (all in this folder):
- `h5_master.py`: builds the crosswalk master table (`build_master()`, `save_master()`). Reads the crosswalk CSV, `음향신호기_현황.csv`
  and the bus-stop location CSV; distances in EPSG:5186; same "wrong position" rule as 06 clean-cross (>1,000 m from the
  intersection median -> coordinates blanked, row kept). Constants: `BUS_GROUP_M=(30,50,100)`, `SIGNAL_MATCH_M=(10,15,20,30)`.
- `data/h5/crosswalk_master.csv`: 21,776 rows (21,771 with usable coordinates, 4 mislocated, 1 without coordinates).
- `09_H5_버스정류장_그룹_결과.ipynb`: executed, 20 cells, no errors, six figures saved in `figures/h5/`
  (01 group building, 02 Seoul map, 03 match rate by group, 04 by distance bin, 05 by district, 06 sensitivity).
  Colors: near-stop = blue `#2a78d6`, other = orange `#eb6834` (passed the dataviz palette validator, CVD/normal/contrast).
- The pasted-ID check: none of the audible-signal ID columns (`A062_MGRNU`, `CTK_MGRNU`, `SD_MGRNU`, `SIXID`, `HISID`, `MGRNU`)
  overlaps `횡단보도관리번호`, so there is no direct signal-to-crosswalk key; matching is spatial only.

**Decisions made while building (draft, the user did not choose them explicitly):**
- Signal-to-crosswalk rule: each signal (with coordinates) is assigned to its single nearest crosswalk; a crosswalk is
  "matched" if at least one assigned signal is within R m. Default R = 15 m (from 06); 10/20/30 m as sensitivity.
  The 06 rule (nearest signal within R m) is kept as `음향_단순_*` for comparison. Evidence: under the 06 rule 27.3% of
  crosswalks without a pedestrian signal were matched; under the assignment rule 11.3% (with a pedestrian signal 64.7% -> 59.5%).
  92.3% of the 16,847 signals with coordinates have a crosswalk within 15 m. 4,604 signals (21.5%) have no coordinates.
- The `보행등유무` column is not used for the groups or the outcome; it appears only in the rule check.

**Descriptive results (no test, assignment rule, 15 m):** 50 m: near 9,716 / other 12,055; matched 42.3% vs 40.3% (+2.0 pp).
30 m: 39.1% vs 41.8% (-2.7 pp); 100 m: 43.0% vs 35.4% (+7.6 pp); 50 m without 마을버스: 45.4% vs 39.2% (+6.2 pp). So the direction
depends on the distance threshold. By distance bin the rate is 28.1% (0-10 m, n=388), 39.1, 44.9, 45.5, 41.8, 37.0, 33.4% (150+ m):
no clean step at 50 m. Within districts near > other in 20 of 25 districts; the count-weighted within-district mean gap is +2.8 pp
(pooled +2.0). District near-share vs district match rate: Spearman -0.30 (25 districts, descriptive only). With the assignment rule the two
groups converge at 20-30 m (43.8% both at 30 m), while the 06 rule keeps a +3.6 pp gap at 30 m.

**Next:** chi-square (two-sided) with odds ratio and CI, district stratification (CMH) or logistic on district, cluster by
`교차로관리번호`, and the sensitivity runs; label results influenced by these observations as exploratory. Notebook 08 `h-h5`
has a progress note. The 08 and 09 notebooks may be open in the IDE; use **Revert File** before running or saving.

### 14.16 H5 work moved into notebook 08 section 2 (2026-09-22)

At the user's request the cells of `09_H5_버스정류장_그룹_결과.ipynb` were inserted into `08_서울전체_가설검증_방향.ipynb`
right after the `h-h5` direction cell (new subsections 2-0 to 2-5; cell ids keep the `h5-` prefix; 32 cells, 10 code cells,
all re-executed with no errors, figures regenerated in `figures/h5/`). The 08 title cell now says that only section 2
has executed code and that no test has been run. Code cells must run top to bottom (2-1 defines `m` and `d`).
Notebook 09 was **not deleted** (it is now a duplicate; ask the user before removing it). A pre-merge copy of 08 is only in
the session scratchpad. Use **Revert File** in the IDE before running or saving 08.

### 14.17 Audible-signal coordinate gaps filled from the original xls `XGEO` (Claude session, 2026-09-22)

A teammate proposed filling the 4,604 audible signals (21.5% of 21,451) whose `XCE`/`YCE` are empty by taking coordinates from
the `XGEO` column. Checked and implemented:

- **In `음향신호기_현황.csv` and in the shapefile's dbf, `XGEO` holds no coordinates**: it is a Java object reference such as
  `oracle.sql.STRUCT@15216338`, unique per row, identical in form for rows with and without coordinates (this is why 06 dropped it).
  The shapefile geometry is also missing for the same 4,604 rows.
- **The original `A073_P_음향신호기_현황/20260528_A073_P 음향신호기 현황/A073_P 음향신호기.xls` (a true BIFF xls, not xlsx)
  does contain coordinates in `XGEO`** for all 21,451 rows, as `MDSYS.SDO_GEOMETRY(2001, 2093, MDSYS.SDO_POINT_TYPE(x, y, NULL), NULL, NULL)`.
  `MGRNU` matches the CSV 100%. The SRID label 2093 does not match the real CRS: values equal `XCE`/`YCE` (EPSG:5186) for 81.1% of the
  16,847 rows that have both (within 0.01 m), so the numbers are treated as EPSG:5186.
- Differences where both exist: 0.01-1 m 6.5%, 1-5 m 8.6%, >5 m 632 rows (3.8%), >20 m 43 rows. Neither source can be called more accurate;
  nearest-crosswalk distance is the same for both (median 9.0 m, within 15 m 92.3% vs 92.6%).
- **Recovered 4,604 points:** nearest-crosswalk median 7.9 m, 91.9% within 15 m (similar to original coordinates), **but 192 (4.2%) are more
  than 40 m from any crosswalk versus 75 (0.4%) of the original ones**, concentrated in 2024-2025 installs. All recovered rows have `WORK_CDE=자료입력`.
- Rule implemented in `h5_master.py`: `load_xgeo_coords()` (reads the xls, caches `data/h5/aud_xgeo_coords.csv`) and
  `load_audible(use_xgeo=True)`: keep `XCE`/`YCE` when present, fill only empty rows from `XGEO`; column `좌표출처` = `XCE` / `XGEO복원` / `없음`,
  `좌표차이_m` = distance between the two sources where both exist. `build_master(use_xgeo=False)` reproduces the old XCE-only results.
- **Effect on H5 (assignment rule, 15 m):** crosswalks with a matched signal 8,975 (41.2%) -> 11,120 (51.1%); near-vs-other gap at 50 m
  +2.0 -> +2.9 pp; 30 m -2.7 -> -1.7; 100 m +7.6 -> +6.9; without 마을버스 +6.2 -> +5.8. Direction unchanged. Crosswalks without a pedestrian signal matched:
  11.3% -> 15.2% (assignment rule), 27.3% -> 35.5% (06 rule).
- **Corrections to earlier statements in this file:** §8/§10.5/§12/§14.4 say coordinate-less signals mean "location unknown" and 21% lack
  coordinates; that is true for the CSV/shp but they can be recovered from the xls. §12's note that `XGEO` is a junk object-reference string is true
  only for the CSV/shp. Notebook 06 was not changed, so its 85-in-circle audible count and 3-4/3-4-1 figures still use only the 16,847 located rows.
  Datasets used in H7/H8 should call `H.load_audible()` (recovered) and treat `XCE`-only as the sensitivity case.
- Notebook 08: new subsections 2-1-1 (`h5-xgeo-md`, `h5-xgeo`, `h5-xgeo-obs`) with figure `figures/h5/07_음향신호기_좌표복원.png`; 2-5 rewritten
  with the recovered-coordinate numbers; `h-h5`, `h-h7`, `h-h8`, `h-data`, `h-rules`, `h-summary` texts updated. No test has been run.
  Use **Revert File** in the IDE before running or saving 08.

### 14.18 Notion summary page created: 가설 검증 (2026-09-22)

A new Notion page "가설 검증" (Hypothesis Verification) was created to consolidate and communicate H5 work status to the team:

- **Blue callout summary:** H5 group construction and visualization are complete; statistical testing has not yet been conducted.
- **4-hypothesis table (H5-H8):** hypothesis, description, testing method, scope, and status columns.
- **Section 2: "H5에서 한 일" (Work completed in H5)** with four collapsible toggles:
  1. Data sources (21,776 crosswalks, 21,451 audible signals post-XGEO recovery, 11,228 bus stops including 마을버스, river piers excluded)
  2. Group definition method (50 m threshold: 9,716 crosswalks within bus-stop proximity vs 12,055 others)
  3. Matching rule selection and justification (assignment rule with 15 m threshold, reducing false positives from 35.5% to 15.2% for non-signalled crosswalks)
  4. XGEO coordinate recovery process and validation (extraction method, accuracy checks, known 4.2% outlier issue for 2024–2025 installations)
- **Section 3: "그림으로 본 결과" (Results shown in figures)** with 7 embedded PNG figures from `figures/h5/` directory with captions explaining each visualization.
- **Results summary table** showing H5 matching rates: 50 m criterion 52.7% near-vs-49.8%-other (+2.9 pp) with sensitivity analysis across distance thresholds.
- **Section 4: "정한 것들" (Decisions made)** listing 5 key decisions with rationales.
- **Section 5: "조심할 점" (Caveats)** listing 5 important limitations.
- **Section 6: "다음에 할 일" (Next steps)** outlining recommended order: H5 testing, then H8 and H7, then H6 last.
- **Two collapsible toggles** for terminology and file-location reference.

The page is designed to be readable to team members without technical depth and serves as a shared checkpoint before statistical testing proceeds.

### 14.19 H5 analysis finalized and merged into notebook 08, XGEO impact documented (2026-09-22)

`08_서울전체_가설검증_방향.ipynb` section 2 was completed with XGEO coordinate recovery fully integrated:

- **Subsection 2-1-1 added:** markdown description, executed code, and findings on XGEO recovery quality
  - Figure 07 (`figures/h5/07_음향신호기_좌표복원.png`): left cumulative distribution of distances from signal coordinates to nearest crosswalk (three lines: XCE only, XGEO for same rows, recovered XGEO); right histogram of coordinate differences in five bins (≤0.01 m, 0.01–1 m, 1–5 m, 5–10 m, 10–20 m, 20+ m).
  - Key findings: 81.1% of dual-source signals are identical within 0.01 m; recovered 4,604 signals are 91.9% within 15 m of crosswalks (vs 92.3% for originals); 4.2% of recovered coordinates >40 m from any crosswalk (vs 0.4% of originals, concentrated in 2024–2025 data-entry-stage installations).
  - Conclusion: XGEO coordinates are valid and yield similar cross-match patterns as original coordinates; outliers are expected given their stage in the data pipeline.
- **Subsection 2-5 ("Observations, not hypothesis tests") rewritten** with updated numbers reflecting XGEO recovery:
  - Signal matching 8,975 (41.2%) → 11,120 (51.1%); crosswalks without pedestrian signal matched 11.3% → 15.2% (assignment rule) or 27.3% → 35.5% (simple rule).
  - Near-vs-other gap at 50 m: +2.0 pp → +2.9 pp; at 30 m: −2.7 pp → −1.7 pp; at 100 m: +7.6 pp → +6.9 pp; excluding 마을버스: +6.2 pp → +5.8 pp.
  - Direction of the near-stop effect is **unchanged** by XGEO recovery across all distance thresholds.
  - Within-district analysis: 20 of 25 districts show higher near-stop match rates; weighted mean gap +2.8 pp (overall +2.9 pp); district differences suggest stratification will be needed in statistical testing.
  - Distance bin gradient (0–10 m to 150+ m) shows no sharp discontinuity at 50 m; rates rise to a peak at 25–75 m then decline.
- **All figures regenerated** with recovered coordinates (7 total in `figures/h5/`): 01 group membership by distance to nearest bus stop, 02 Seoul district map showing group composition, 03 match rates by group (bar chart), 04 rates by distance bin from nearest stop, 05 rates by district with district totals, 06 sensitivity to thresholds and rules, 07 XGEO recovery validation.
- **Progress updated** in notebook 08 header and summary: only section 2 (H5) contains executed code; H5–H8 direction and methods are documented but untested; section 2 runs code cells 2-1 through 2-5 sequentially (2-1 defines module `m` and district list `d`).

All 52 notebook cells (12 Markdown direction, 32 H5 execution from merged 09, 8 remaining direction) executed without errors. Notebook 09 retained as duplicate for reference (not deleted). Use **Revert File** in IDE before running or saving.

**Implication for H5 inference:** signal sample increased from 16,847 (78.5% with coordinates) to 21,451 (100% coverage after recovery). Coordinate source tracked in `좌표출처` column and pair-wise difference in `좌표차이_m` allow sensitivity analysis. XGEO recovery does not alter the direction of the near-vs-other comparison but increases the absolute matching rate, providing a more complete picture of audible-signal distribution.

### 14.20 Current state and next steps: H5 complete, H8–H7–H6 pending (2026-09-22, end of session)

Hypothesis verification (H5–H8) setup is now ready for statistical testing and subsequent hypothesis work:

**Completed in this session:**
- Notebook 08 direction outline: all four hypotheses (H5–H8) documented with scope, methods, and design rationale
- H5 groups constructed: 50 m proximity threshold yields 9,716 near-stop vs 12,055 other crosswalks; 30 m and 100 m available for sensitivity
- Audible-signal coordinates recovered from original `XGEO` column: 4,604 missing coordinates restored via regex extraction of Oracle SDO_GEOMETRY format, validated against original locations, cached in `data/h5/aud_xgeo_coords.csv`
- Signal-to-crosswalk matching rule finalized: assignment rule (each signal → nearest crosswalk, threshold 15 m) vs simple rule (nearest signal within R m) comparison completed; assignment rule reduces false-positive matches in non-signalled crosswalks
- H5 visualizations: 7 figures covering group composition, Seoul geography, match rates by distance/district/rule, sensitivity to thresholds, and XGEO validation
- `h5_master.py` module: functions `load_xgeo_coords()`, `load_audible(use_xgeo=True)`, `load_bus_stops()`, `build_master(use_xgeo=True)`, `save_master()` form a complete data pipeline from raw files to analysis-ready crosswalk master table (`data/h5/crosswalk_master.csv`)
- Notion page "가설 검증" published for team reference

**Not yet begun:**
- H5 hypothesis test: chi-square (two-sided) with odds ratio and confidence interval; district stratification via CMH or logistic regression; intersection-level clustering; sensitivity runs
- H8 (dense audible-signal zones): identify high-density regions, compute distance to nearest no-audio/no-pedestrian-signal crosswalk, compare with low-density baseline, assess whether density ensures route safety
- H7 (within-university access gaps): coefficient of variation in audible signals across gates per school; collect Seoul university coordinates and entrance gates; define "large gap" threshold
- H6 (CAU vs Soongsil per-route risk): requires risk-score definition (step 4 of team deliverables); CAU reference point unification (current: OSM main gate, to be shifted to Kakao representative point + 800 m); Mann-Whitney U with effect size; spatial-autocorrelation control (last hypothesis to run)

**Design decisions in place:**
- Signal-to-crosswalk matching: assignment rule (not nearest-signal rule) with 15 m default threshold (10/20/30 m sensitivity)
- Group definition: bus stops include 마을버스; river-bus piers excluded
- Pedestrian-signal control: `보행등유무` column not used in main H5 analysis (near-stop unrelated to signal presence); used only in sensitivity and H8 definition (a)
- Coordinate source tracking: three values (XCE, XGEO복원, 없음) recorded per signal; recovered vs original distance computed for validation
- Known outliers documented: 4.2% of recovered XGEO coordinates >40 m from crosswalks (2024–2025 data-entry stage, not matched due to 15 m threshold)
- Multiple-comparison correction planned but not yet applied (Holm method across H5–H8 after individual tests complete)

**File status:**
- Notebooks 08/09 may be open in IDE; use **Revert File** before modifying either
- All data outputs (crosswalk master, XGEO cache, figures) generated and stable
- `codex&claude.md` now fully documents hypothesis verification workflow, data recovery, and current state

**Recommended continuation:**
1. Run H5 chi-square test with odds ratio, district CMH, intersection clustering; complete sensitivity runs and label exploratory results
2. Proceed to H8 (simpler analysis, no new data required)
3. Collect Seoul university data and gate coordinates; complete H7
4. Define or adopt risk-score components; complete H6 last
5. Apply multiple-comparison correction across the four hypotheses before reporting results

---

## 15. H5 tested, H8 paused, H7 gate collection (Claude session, 2026-09-22 afternoon)

This section supersedes §14.19–14.20 wherever they conflict. Between sessions the user reset notebook 08 to four
Markdown cells of their own (title, summary, hypothesis table, `## 1. H5`), and everything below was rebuilt on top
of that. There is no "section 2-1 … 2-5 / 52 cells" layout any more. Notebook 09 was not touched in this session.

### 15.1 Working style the user asked for (apply to all future work)

- Put work into **notebook cells** (`08_서울전체_가설검증_방향.ipynb`), with a short Korean Markdown explanation for each step.
- Plain Korean explanations, no analogies. Use precise terms: the user corrected "음향 없는" → "**음향신호기 없는**"
  (write the full device name, never the abbreviation "음향").
- The user decides when a hypothesis is "kept/paused" (킵). When pausing, record exactly what was and was not done.
- The user reads the FRM_CDE codebook themselves; do not guess code meanings (codes 1/2/4/5/6 are not decoded in any
  project file).
- After editing the notebook, tell the user to **Revert File** in the IDE. In this session cells were edited with a
  notebook-edit tool, then the whole notebook was executed with `nbclient` (`resources={"metadata": {"path": "."}}`,
  cwd = project folder) and checked for error outputs. All 34 cells currently execute without errors.

### 15.2 Current notebook 08 layout (34 cells; cell ids for programmatic edits)

| idx | id | content |
|---|---|---|
| 0–3 | h-title, h-summary, h-table, h-h5 | User-written Markdown (do not rewrite). `h-h5` lists the two H5 directions: (1) the crosswalk's signal rate, (2) the signals' own ratio; and the coordinate-gap problem. |
| 4 | 3f8518d4 | `### 1-1` Markdown: XGEO gap filling explained |
| 5 | e661795c | `load_audible(use_xgeo=True)` → 21,451 signals: XCE 16,847 + XGEO복원 4,604, 0 missing |
| 6 | 6692090c | XCE vs XGEO agreement on the 16,847 rows that have both (defines `bins`, `labels`) |
| 7 | 151bf860 | `### 1-2` Markdown: where large XCE–XGEO differences occur (user's concern, method, result) |
| 8–10 | f7d9ac73, 298b6262, 280e479d | FRM_CDE / install-year breakdown; 20 m+ cases by install date; batch-risk mapping of the 4,604 filled rows |
| 11–12 | bb94cdda, 0f9904f8 | `## 2` crosswalk master table via `h5_master.build_master()` → `master`, `audible_final`, `bus`, `ok` |
| 13–16 | 26208c80 … a2fc647b | `## 3` H5 chi-square (crosswalk unit) + interpretation + figure 08 |
| 17–22 | cc345965 … 13cc5536 | `## 4` H5 signal-unit goodness-of-fit + plain-language explanation cell (8aca256a) + interpretation + figure 09 |
| 23–26 | 40a56b5d … 3bd2254c | `## 5` 30 m sensitivity for §3 and §4 + 50 m vs 30 m table |
| 27–30 | 8943c674 … 350f7e67 | `## 6` Mann-Whitney U on assigned-signal counts + interpretation + figure 10 |
| 31–33 | 32342972, 5dd8b882, d184d0c3 | `## 7` H8: definition of crosswalk with/without audible signal, ratio only, **paused** |

Cells run top to bottom and share variables (`ok`, `rate`, `n`, `chi2`, `p`, `BG/BLUE/ORANGE/INK/MUTED/GRID`, `idx`,
`aa`, `assigned`, `n_assigned`, `g0`, `g1` …). Running a later cell alone will fail.

### 15.3 XGEO gap filling — the check the user asked for

- `음향신호기_현황.csv` and the shapefile store `XGEO` as `oracle.sql.STRUCT@…` (unusable). The original `.xls` in
  `A073_P_음향신호기_현황/20260528_A073_P 음향신호기 현황/` holds `SDO_POINT_TYPE(x, y, …)` text;
  `h5_master.load_xgeo_coords()` extracts it (cache `data/h5/aud_xgeo_coords.csv`). There is no separate YGEO column:
  one XGEO string holds both x and y.
- Rule: XCE/YCE first; only rows without them get XGEO (`좌표출처 = 'XGEO복원'`). All 21,451 rows now have coordinates.
- Agreement on the 16,847 rows with both: 81.1% ≤ 0.01 m, 6.5% 0.01–1 m, 8.6% 1–5 m, 2.7% 5–10 m, 0.8% 10–20 m,
  0.3% (43) > 20 m; 99.0% within 10 m → XGEO treated as EPSG:5186 like XCE.
- **User's concern:** the 4,604 filled rows have no XCE to compare, so large errors could hide there. Checks done:
  - Direct cross-check: only 170 filled signals (3.7%) share an intersection id (`A062_MGRNU`) with an XCE signal;
    their nearest XCE peer is mean 3.0 m, max 22.8 m away. All 4,604 lie inside the XCE Seoul extent (±2 km).
  - Error pattern on the 16,847: FRM_CDE 4 is worse (70.4% identical vs 86.0% / 78.4% for codes 1 / 2); install
    years 2007–2022 mean error 0.2–0.8 m, **2023–2025 mean 2.6–3.8 m**. 20 m+ cases cluster by install date:
    **2023-12-11 (6 of 6 = 100%)**, **2024-12-31 (4 of 4 = 100%)**, 2015-09-04 (2 of 4), 2024-01-18 (4 of 19).
  - Batch-risk mapping of the 4,604 filled rows by install date (only dates with ≥ 3 both-rows are judged):
    high risk 24 (18 on 2023-12-11, 6 on 2024-12-31), medium 196, low 1,344, **not judgeable 3,040 (66%)**.
- Nothing was excluded; the user said to keep this as a documented finding. No `좌표신뢰도` column was added to
  `h5_master.py` (offered, not approved). Bug fixed on the way: `pd.cut` needs `include_lowest=True`, otherwise exact
  0.0 differences drop out of the first bin (showed 17.2% instead of 81.1%).
- No district boundary shapefile exists in the project, so the geographic distribution of errors was not checked.

### 15.4 H5 results (coordinate-valid crosswalks, n = 21,771; signal assignment rule 15 m)

| § | View | Test | Result | Effect size |
|---|---|---|---|---|
| 3 | Crosswalk has ≥ 1 assigned signal, near stop (≤ 50 m) vs other | chi-square 2×2 | 52.7% vs 49.8% (+2.9 pp), χ² = 17.84, p = 2.4e-5 | Cramér's V = 0.029 |
| 4 | Share of assigned signals (19,786 of 21,451) located at near-stop crosswalks vs crosswalk base rate 44.6% | chi-square goodness-of-fit | 45.31% vs 44.63% (+0.68 pp), χ² = 3.72, **p = 0.054** | Cohen's h = 0.014 |
| 5 | §3 at 30 m | chi-square 2×2 | 49.8% vs 51.5% (**−1.7 pp**), p = 0.038 | V = 0.014 |
| 5 | §4 at 30 m | goodness-of-fit | 21.44% vs 22.52% (**−1.08 pp**), p = 0.0003 | h = −0.026 |
| 6 | Number of assigned signals per crosswalk (0–5), near vs other | Mann-Whitney U | mean 0.923 vs 0.898, median 1 vs 0, U = 59,540,089.5, p = 0.021 | rank-biserial r = −0.017, CLES = 0.508 |

- §4 definition was chosen by the user: "of all audible signals, what share sits at near-stop crosswalks, compared
  with the share expected if signals simply followed crosswalks" — not "count inside vs count outside" (those always
  differ because they sum to 100%). Cell 8aca256a explains this in plain Korean.
- **The direction flips between 50 m and 30 m** in both the crosswalk view and the signal view.
- Conclusion written in the notebook (§6-1): large n makes p small, but every effect size is ≤ 0.03 and the sign is
  unstable → "statistically significant but practically unrelated / no consistent effect found".
- Not done for H5: 100 m run in the new layout, district stratification (CMH or logistic), intersection clustering,
  signal-rule sensitivity (10/20/30 m), Holm correction across H5–H8.
- Figures (palette taken from the earlier `figures/h5/0x` images: bg `#fcfcfb`, blue `#2A78D6`, orange `#EB6834`,
  gray `#B8B8B4`; blue/orange passed the dataviz CVD validator; font Malgun Gothic):
  `figures/h5/08_H5_카이제곱_결과.png`, `09_H5_신호기비율_결과.png`, `10_H5_신호기개수_분포.png`.

### 15.5 H8 — paused

- Wording (corrected by the user): "Even where audible signals are dense, is there a crosswalk **without an audible
  signal** nearby?"
- Step done: crosswalk "has audible signal" = nearest signal ≤ 15 m (`음향_단순_15m`, simple rule; stored as
  `ok['음향신호기있음']`). 13,512 with (62.1%), 8,259 without (37.9%). Nearest-signal distance: mean 42.4 m, median
  11.8 m, max 1,080 m. The simple and assignment rules disagree on 2,392 crosswalks (11.0%); the simple rule fits here
  because the question is "is there a signal near this crosswalk".
- Not done: dense-zone definition, distance to the nearest crosswalk without a signal, any test. The summary table
  says "without a comparison target this is not a test"; options were discussed (dense vs non-dense with
  Mann-Whitney U, or observed vs a random baseline) but **the user has not chosen**. Cell d184d0c3 records this.

### 15.6 H7 — Seoul university and gate collection (in progress, no test yet)

Question: "Within the same university, does the number of audible signals differ a lot between gates?" The
gate-to-signal linking rule is **not decided** (the user leans to simple nearest distance but wants to think about
reflecting distance, e.g. weighting). The user chose to collect all Seoul universities first, not a Soongsil pilot.

New script `collect_univ_gates.py` (outputs in `data/h7/`):

1. `collect_universities()`: Kakao keyword search "대학교" over `SEOUL_BBOX = (126.734, 37.413, 127.269, 37.715)`,
   0.02° grid, recursive 4-split when the 45-result cap is hit; keep `category_group_code == "SC4"` and a category
   containing "대학교". 81 candidates. User-approved filters (applied; file overwritten): drop 9 non-Seoul campuses
   (address not starting with 서울), 2 graduate-only schools (수도국제대학원대학교, 서울사회복지대학원대학교),
   4 non-regular institutions (KBS스포츠예술과학원 스포츠예술학부, SPC식품과학대학, 정석대학, 인덕학원), and
   2 department/building POIs duplicating a campus (연세대학교 생명시스템대학 생화학과, 홍익대학교 대학로DA동)
   → **`seoul_universities.csv`, 64 campuses**. Multi-campus universities stay as separate rows.
2. `collect_gates()`: queries "<name> <gate>" and "<core name> <gate>" for 정문/후문/동문/서문/남문/북문/중문.
   `core_name()` strips a trailing "…캠퍼스"/"…교정", because Kakao gate POIs are usually "경희대학교 정문", not
   "경희대학교 서울캠퍼스 정문". A result is kept only if its category starts with "교통,수송 > 입출구", the gate word
   is in its name, its name contains **no other university's core name**, and its distance to the campus point is
   ≤ 2,000 m when the core name is in the POI name, else ≤ 400 m.
   Iterations: exact-name match gave 42 gates / 24 campuses (missed Kyung Hee, Yonsei, HUFS); distance-only gave
   125 / 51 with false positives (HUFS got "경희대학교 남문", Konkuk got "어린이대공원 남문", Soongsil got
   "관악드림타운아파트 남문"). Final rule: **57 gates, 30 campuses with ≥ 1 gate, 18 campuses with ≥ 2 gates (CV
   computable)** → `seoul_univ_gates_kakao.csv`. Columns: univ_id, univ_name, gate_type, place_name, lat, lon,
   대학대표점_거리_m, 이름매칭. Only one row came in through the 400 m rule (한국외대정문, correct). 34 campuses have
   no Kakao gate (e.g. 건국대학교 서울캠퍼스 — Kakao has no gate POI for it).
3. OSM augmentation (the user asked for it): per-university Overpass queries hung (overpass-api.de took ~22 s per
   query and one run hung for 16 minutes; kumi.systems and private.coffee timed out). Replaced by one bulk query:
   `fetch_seoul_osm_entrances()` → all named `entrance` nodes in the Seoul bbox, cached at
   `data/h7/osm_seoul_named_entrances.json` (279 nodes); `augment_with_osm()` matches locally with the same rules and
   drops OSM gates within 50 m of a Kakao gate. It added 13 rows, but they are building entrances (연세대
   "제1공학관 정문", "과학관 정문", "도서관 정문" …), bare "정문"/"후문", and park gates (효창공원 near 숙명여대).
   Only one row is name-matched ("숭실대학교 후문"), and it sits ~330 m from the Kakao 후문, so one of the two is
   wrong. CV-computable campuses 18 → 19. **Claude recommended discarding the OSM rows** (they would inflate gate
   counts, e.g. Yonsei 5 → 14) **and proceeding with the Kakao 18; the user has not answered yet.**
4. File state right now: `seoul_univ_gates.csv` = Kakao + OSM merged (70 rows, has a `출처` column). The clean
   Kakao-only version is `seoul_univ_gates_kakao.csv` (57 rows). If the user accepts the recommendation, copy the
   Kakao file over `seoul_univ_gates.csv` (or read the Kakao file directly).

Script notes: `main()` collects universities (if missing) and Kakao gates only; OSM augmentation runs separately with
`augment_with_osm(pd.read_csv(UNIV_OUT), pd.read_csv(KAKAO_GATE_CACHE))`. Load `.env` with
`load_dotenv(PROJECT_DIR / ".env")`; `load_dotenv()` without a path fails when Python reads the script from stdin.
On Windows, print Korean with `sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', buffering=1)`. Long jobs
were run in the background; bash `ps` does not show the real Windows PID — use `tasklist`.

### 15.7 H6

Not started. Still last, after H5, H7 and H8 (§14.10).

### 15.8 Open decisions waiting for the user

1. H7: discard the OSM gate rows and use the Kakao 18 campuses? (Claude's recommendation: yes.)
2. H7: gate-to-signal linking rule — nearest-gate assignment within a radius, count within a fixed buffer, or a
   distance-weighted count — and the radius. Then the significance approach (per-school chi-square goodness-of-fit
   against equal counts per gate, and/or CV with a "large" threshold as in the summary table).
3. H7: Soongsil 후문 position conflict (Kakao vs OSM, ~330 m apart) — check on a map.
4. H8: comparison target for a real test (dense vs non-dense, or observed vs a random baseline) and the dense-zone
   definition.
5. H5: add district stratification / intersection clustering / a 100 m run, or accept the §6-1 conclusion.
6. Whether to add a `좌표신뢰도` (batch-risk) flag to `h5_master.load_audible()` for sensitivity runs.

### 15.9 Quick start for Codex

- Open `08_서울전체_가설검증_방향.ipynb`; it runs top to bottom in about a minute (`build_master` reads the
  21,776-row crosswalk CSV, the audible-signal CSV + XGEO cache, and the bus-stop CSV).
- H5 is done; H8 is paused at §7-2; the next work is **H7**. Start from `data/h7/seoul_univ_gates_kakao.csv` and
  `data/h7/seoul_universities.csv`. Signal coordinates come from `h5_master.load_audible(use_xgeo=True)` (EPSG:5186
  x/y); gates are WGS84 lat/lon → transform to EPSG:5186 before any distance calculation.
- Ask the user §15.8 items 1–2 before building the H7 test. Add a Korean Markdown cell before each step, and log every
  decision back into this file.

### 15.10 H7 coverage expansion review (Codex, 2026-09-22; proposal only)

- The user considers 18 campuses insufficient and requested data-based proposals for defining gates at other campuses. No test or gate-data replacement was performed.
- Recounted the Kakao CSV against 64 candidate campuses: 34 have 0 collected gates, 12 have 1, 13 have 2, 3 have 3, and 2 have 5. These are collection counts, not actual verified gate counts. The campus list is not a verified complete census.
- Coverage limits in code: seven directional gate keywords; five Kakao results per query without pagination; strict entrance-category filter; OSM requires both entrance and name tags, omitting barrier-only and unnamed candidates.
- SeoulTech has one gate in the CSV, but official notices identify Changui Gate, Hyeopdong Gate and other pedestrian approaches: https://www.seoultech.ac.kr/service/info/notice?bidx=891666&bnum=4691&do=commonview . This construction notice does not establish that all listed approaches are permanent gates.
- Konkuk has zero collected gates. Its university newspaper identifies Konkuk, Sanghuh and Ilgam gates: https://popkon.konkuk.ac.kr/news/articleView.html?idxno=1955 . This historical source supplies aliases, not current operating status or coordinates.
- Proposed definition: verified pedestrian connection between outside streets/walkways and campus at its boundary. Exclude internal building doors and vehicle-only/service-only access; record restricted hours and temporary access separately. Analyze building-based campuses separately.
- Proposed collection: official maps/notices for names and evidence; expanded Kakao searches for coordinates; campus polygons plus pedestrian-network boundary crossings and OSM barrier/entrance tags for unnamed candidates; map/imagery verification before inclusion. Geometry alone does not establish a usable entrance. Existing soongsil_campus_polygon.geojson can support a pilot after boundary-quality checks.
- Prioritize 12 one-gate campuses, then zero-gate conventional campuses; audit the original 18 with the same rules. Keep verification status, source URL/date, coordinate source and pedestrian-access status. Select gates independently of audible-signal outcomes. Expanded sample size remains unknown; these recommendations await the user's decision.

### 15.11 H7 gate re-investigation (Codex, 2026-09-22)

- User authorized investigating the 12 one-collected-gate campuses first, then the 34 zero-collected-gate campuses. Completed the first-pass search of all 46; this is not a field-verified gate census.
- Added `audit_univ_gates.py` for expanded Kakao queries (15 results/page, up to 3 pages, aliases, named gates, cache and truncation log) and OSM barrier/campus/path collection. Runs: 262 queries for group 1, 514 for group 0; raw school-result pairs 562 and 1,667 include unrelated facilities and MUST NOT be analyzed as gates.
- Added `gate_audit_evidence.py` for per-campus evidence/limitations and manual candidate decisions; `build_gate_audit.py` creates the review CSVs, README and Folium map without network access. All outputs are under `data/h7/gate_audit_20260922/`.
- Recovered additional coordinates at SeoulTech (Changui/Hyeopdong), Myongji (entrance distinct from existing rear gate), Sookmyung (Jihye), Konkuk (3 named gates plus 2 numbered candidates), SNUE (2 named gates plus side entrance), KNSU (main/rear OSM nodes). These six campuses are priorities, NOT six validated additions to the H7 sample.
- `reviewed_gate_candidates.csv`: 18 decision records, including 2 near-duplicate Konkuk entries excluded, Sookmyung second-campus rear gate held separately, and Catholic Songeui shared hospital/campus entrance held. All `analysis_ready=False`; 14 remaining coordinate candidates are not 14 verified public pedestrian gates.
- `campus_audit.csv`: all 46 campuses with status, source/reference URL, limitation, and next verification. Official name evidence without dependable coordinates exists for additional campuses (e.g. Duksung, Seokyeong, SWU, Sejong). Historical notices, search-index-only sources and parking directions are explicitly not evidence of current public pedestrian permission.
- Matched OSM polygons for 29/46 campuses. Extracted 10 nearby barrier/entrance nodes and 148 road-boundary intersection/contact records across 27 campuses. These records include duplicate approaches, restrictions, polygon errors and incomplete external connections; record counts are NOT gate counts. The remaining 17 campuses have unconfirmed boundaries, not zero gates.
- Issues: HUFS OSM alleged rear gate is outside the matched polygon; avoid automatic proximity assignment. Exclude parking/building/hospital doors without campus pedestrian evidence. Howon existing Hwagok POI conflicts with official Seongnae educational-facility address. Graduate-school-only and building-based campus units need a consistent inclusion rule, not ad hoc deletion.
- Correction to 15.10: SeoulTech notice bidx=891666 could not be reopened (post missing); retained separate official 2025 construction notice bidx=714956 and OSM/Kakao evidence. Myongji PDF text was retrieved but screenshot failed; its three parking-related labels are NOT counted as three pedestrian gates.
- Appended Korean explanatory and review-table cells to notebook 08, without changing prior cells. The new cell only reads audit files; existing gate CSVs and all hypothesis outputs remain unchanged. If notebook 08 is already open, save any unsaved personal edits elsewhere before Revert File/reopening the on-disk version.
- Next: verify the six priority campuses against current campus maps/street imagery and pedestrian connectivity; geocode named missing entrances, resolve special-campus scope, then audit the original 18 with the same rule. Do not run H7 or claim 24 validated campuses until those checks finish.

---

## 16. H7 gate audit extended to all 64 campuses (Claude, 2026-09-22 evening; continues Codex §15.10–15.11)

### 16.1 What Codex left unfinished (recovered from `~/.codex/thread_history_1.sqlite`)

- After §15.11 the user told Codex: "apply the same rule to all 64 campuses and define the gate points of all 64".
  Codex agreed on the rule (below), then hit its usage limit at 17:55 mid-task; the follow-up request to write this
  file failed too. So §15.11 is the last thing Codex documented.
- Done by Codex before the limit: Kakao re-search of the 18 campuses that already had ≥ 2 gates
  (`audit_univ_gates.py --group 2` → `kakao_candidates_2.csv`, 750 unverified candidates, 300 queries);
  `gate_evidence_all64.py` (`ADDITIONAL_EVIDENCE` for the 18 + `NAMED_GATE_EVIDENCE`: official gate names per campus);
  `audit_all_campuses.py` (`ALL_BOUNDARIES`: OSM campus polygons for 46 campuses).
- Not done by Codex: OSM path download for the 18 (`--osm-paths-all` failed twice with Overpass 504), any 64-campus
  output, coordinate selection for the 18, documentation. `build_gate_audit.py` still builds the 46-campus version only.
- Gate rule agreed with the user (Codex turn, 17:48): a gate is where the outside sidewalk/road and the inside walkway
  actually connect at the campus boundary; exclude building doors, vehicle-only access and duplicate names; mark
  timed/temporary access separately; place the coordinate where the walkway crosses the boundary; record source and
  date; keep "unconfirmed" when unclear. Surveying all 64 is not the same as putting all 64 into the H7 sample.

### 16.2 New script `audit_all64.py` (Codex files untouched; outputs in `data/h7/gate_audit_20260922/all64/`)

- `--fetch-paths`: downloads OSM walkways for the 17 new boundaries **one campus at a time** (a single 64-campus query
  gets 504). Caches per campus in `osm_paths_group2/<univ_id>.json`; several needed retries, all 17 succeeded.
  Merged with Codex's `osm_paths.json` into `osm_paths_all64.json` (4,710 ways). 장로회신학대학교 has no boundary
  (Codex: nearby unnamed polygon not attributable).
- Default run (no network): reuses Codex's `spatial_candidates()` and `crossing_candidates()` with `ALL_BOUNDARIES`,
  keeps Codex's manual decisions for the 46 (`SELECTED_KAKAO`, KNSU OSM nodes), and for the 18 applies a rule instead of
  hand picks: a Kakao POI is added only if its name contains the campus core name **and** an official gate name from
  `NAMED_GATE_EVIDENCE`, its category contains "입출구", it is > 50 m from an existing gate, and its name has none of
  주차장/부속/초등학교/중학교/고등학교/병원/ATM (first run wrongly added "이화여자대학교 후문 ECC주차장" and
  "홍익대학교 사범대학 부속초등학교 정문"). Result for the 18: 동국대 혜화문, 서강대 남문, 이화여대 북아현문 added;
  한양대 애지문 (subway connection) held as `지하접근_별도층_보류`. Not found in Kakao: 서울시립대 미래문·이음문·하늘문,
  성균관대 동문, 이화여대 서문·북문·공학관문, 한양대 사근동출입로·건축관출입로.
- Outputs: `campus_audit_all64.csv` (64 rows: review_status, unit_hold, gates_A/B/C/held, official names, boundary and
  path-record counts, findings, source URL), `gate_definition_all64.csv` (one row per gate with tier),
  `reviewed_gate_candidates.csv` (22 added/held coordinate rows), `osm_boundary_candidates.csv`,
  `osm_path_boundary_candidates.csv` (496 path–boundary records; **not** gate counts), `campus_boundaries.geojson`,
  `gate_review_map_all64.html`.

### 16.3 Gate tiers and current numbers (nothing is `analysis_ready`)

- **A** = official gate name matched by a coordinate POI name (45 gates); **B** = coordinate without an official-name
  match (29; e.g. 숭실대 후문, 경희대 남문, all gates of campuses with no official name list such as 고려대, 서울대 관악,
  서울교대); **C** = official name without coordinate (14); **held** = duplicates, second campus, hospital-shared, subway
  layer (5).
- Campus-level hold (`unit_hold`, Codex review_status 표본단위검토/공유부지검토/주소불일치검토/경계확인필요): **17 campuses**
  (e.g. KAIST 도곡, 가톨릭대 성의교정, 서울대 연건, 이화여대 의과대학, 홍익대 대학로, 호원대). Sample-unit rule still undecided.
- Of the 47 campuses without a unit hold: **≥ 2 A gates: 14**; **≥ 2 A+B gates: 24** (1 gate: 9, 0 gates: 14).
  The earlier Kakao-only count was 18 campuses with ≥ 2 collected gates.
- Soongsil: A = 정문·중문·남문·북문, B = 후문 (official AI-college map lists only four gates; Kakao 후문 and OSM 후문 are
  ~330 m apart — still unresolved, see §15.8 item 3).

### 16.4 Notebook 08

Two cells appended after Codex's cell `h7-gate-audit-20260922-table`: Markdown `aaff0a12` ("H7 보완 2: 64곳 전체를 같은
기준으로 출입문 정의") and code `5de57788` (reads the all64 CSVs, prints the counts above, shows per-campus tables and the
map link). Notebook now has 38 cells; the whole notebook was executed with nbclient, 0 errors.

### 16.5 Open decisions for the user (H7)

1. Which gates count for H7: A only (14 campuses) or A+B (24)? B includes real but unofficially named gates and some
   possibly wrong ones (Soongsil 후문).
2. Whether any of the 17 unit-hold campuses enter the sample, with one consistent rule.
3. Manual map/street-view check of new and B-tier gates (none has current pedestrian access confirmed).
4. Gate-to-signal linking rule and radius (still §15.8 item 2), then the significance approach.
5. The discarded OSM-name merge from §15.6 is superseded: `seoul_univ_gates.csv` still holds the 70-row Kakao+OSM file;
   use `gate_definition_all64.csv` instead for anything new.

### 16.6 Keyword criterion ('…문' / '게이트' / 'gate') and team Notion page (Claude, 2026-09-22 evening)

- User asked whether adding a name-keyword criterion finds more gates. `audit_gate_keywords.py`: `--fetch` ran new Kakao
  queries "<core/alias/short name> 게이트|gate|문" for all 64 campuses (cache `kakao_candidates_keyword.csv`); default run
  scans old + new Kakao results for names whose word ends in 문 or contains 게이트/gate, any category, school name required,
  shops/parking/apartments/attached schools/hospitals/car-sharing excluded, > 50 m from existing gates
  → `all64/keyword_gate_candidates.csv` (27 rows). OSM named entrance/barrier nodes near campus boundaries were also checked.
- Result: **no new campus reaches 2 gates** (still A-only 14, A+B 24). New hits only at campuses already ≥ 2 gates:
  고려대 정경관후문·의과대학 후문 (Kakao 입출구) — **user approved, added as B** via `KEYWORD_ADDITIONS` in `audit_all64.py`
  (고려대 B 2 → 4; total B 29 → 31); 서울대 관악 나들문 G1–G20 (not added: Codex judged them internal, entered from the ring
  road after the main gate); OSM boundary nodes at 연세대 (쪽문, 후문, 정문, dorm gates) and 숭실대 OSM 후문 (not added, need a
  map check). "게이트" queries returned only e-cigarette shops ("전담 GATE …").
- Current `all64` outputs regenerated; `figures/h7/01_캠퍼스별_출입문수.png` created; notebook 08 re-executed (38 cells, 0 errors).
- Team Notion page "가설 검증" (https://app.notion.com/p/3e3e935a81c9803d990cc5f92fe62083): user's sections 1–2 kept verbatim;
  everything below replaced with a short team summary (§3 status, §4 H5 results table + figures 4–6, §5 H8, §6 H7 tiers +
  figure 7 + CSV/HTML attachments, §7 open decisions). Notion cannot delete single image blocks via the API (signed URLs change
  on every fetch), so the whole page is rewritten with replace_content and all images re-uploaded each time. Section 1's
  "지금 상태" column (user-written) is outdated; left unchanged pending the user's decision.

### 16.7 Decision: H7 sample = A+B gates (user, 2026-09-22)

- The user decided H7 will be tested on **A+B tier gates** (A-only would leave 14 campuses). Sample = campuses without a
  unit hold and with >= 2 A+B gates: **24 campuses, 67 gates**. By gate count: 5 gates - 건국대(A3 B2), 숭실대(A4 B1),
  연세대(A5 B0); 4 - 고려대(A0 B4); 3 - 경희대, 동국대, 서강대, 서울과기대, 서울교대(A0 B3), 이화여대, 장신대(A0 B3), 중앙대;
  2 - 경기대, 국민대, 명지대(A0 B2), 삼육대, 서울대 관악(A0 B2), 서울시립대, 성균관대, 성신여대 돈암수정, 숙명여대(A0 B2),
  한체대, 한양대, 홍익대. Excluded: 9 campuses with 1 gate, 14 with 0, 17 unit-hold campuses.
- **No H7 test has been run.** Still open before testing: gate-to-signal linking rule/radius (§15.8 item 2) and the
  significance approach; unit-hold campuses stay out unless the user decides otherwise.
- Notebook 08 now ends with a Markdown + code cell pair (ids `h7-gate-count-summary-md`, `h7-gate-count-summary`)
  showing gate-count distributions (A vs A+B), the 24-campus list and the 17 unit-hold campuses (40 cells, 0 errors).
- Notion page updated with text-only `update_content` edits (images untouched): §3 status, §6 decision callout + 24-campus
  table, §7 item 1 struck through as decided.

### 16.8 H7 gate definition closed for now: limitations and follow-up (user decision, 2026-09-22)

The user stopped the gate-definition work here. Sample stays **24 campuses / 67 A+B gates** (§16.7). No H7 test yet.
Notebook 08 ends with a Korean Markdown cell `h7-gate-limits-todo` holding the same list (41 cells).

**Limitations**
1. Pedestrian access not verified: every gate is a Kakao/OSM point; opening hours, closure, vehicle-only status unchecked
   (`analysis_ready=False` everywhere).
2. Coordinates are Kakao pin positions, not the walkway/boundary crossing required by the agreed definition; offsets of
   tens of metres can change signal counts around a gate.
3. 31 B-tier gates have no official-name match; some may be wrong (숭실대 후문: Kakao vs OSM ~330 m apart; official AI-college
   map lists only 정문·중문·남문·북문).
4. Coverage depends on Kakao registration: the 9 one-gate and 14 zero-gate campuses dropped out because of missing data, not
   missing gates → possible selection bias toward large, well-known universities.
5. Official evidence is uneven (2005/2011/2018 sources, notices that could not be reopened, parking guides); per-campus URLs are
   in `campus_audit_all64.csv`.
6. No inclusion rule yet for the 17 unit-hold campuses.
7. OSM boundary crossings and unnamed barrier/entrance nodes were computed as reference only, never adopted.
8. Gate counts differ (2-5 per campus); CV-based comparisons must account for this.

**Follow-up (in priority order)**
1. Map/street-view check of the 67 sample gates (access + position); start with B-tier gates and the Soongsil 후문 conflict.
2. Decide whether to move coordinates to the actual boundary entry point.
3. To enlarge the sample, geocode officially named gates lacking coordinates — would lift one-gate campuses: 덕성여대 정문,
   서경대 정문, 서울여대 정문·남문, 세종대 후문; already in sample: 서울시립대 미래문·이음문·하늘문, 성균관대 동문,
   이화여대 서문·북문·공학관문, 한양대 사근동출입로·건축관출입로.
4. Review OSM candidates: 감리교신학대 2 barrier nodes, 한양여대 and 한예종 석관동 13 boundary crossings each, 연세대 boundary
   쪽문/dorm gates, 서울대 나들문 (re-confirm the internal-gate judgement). Candidates: `all64/osm_*_candidates.csv`,
   `all64/keyword_gate_candidates.csv`, map layer "도로-경계 기하 후보".
5. One consistent rule for the 17 unit-hold campuses.
6. Before testing: gate-to-signal linking rule (radius, distance weighting), significance approach, handling of unequal gate
   counts.
7. Report the limitations above with the results, especially the selection bias (item 4).

### 16.9 H7 test run and completed (Claude, 2026-09-22 night)

New module `h7_gate_signal.py`. Sample: 24 campuses / 67 A+B-tier gates (§16.7), joined to signals by straight-line
radius (EPSG:5186), default **300 m** (200 m unusable — 26 of 67 gates have 0 signals, only 9 campuses testable; 400 m
as sensitivity). Per-gate metrics: signal count, nearby crosswalk count, count of those crosswalks with an audible
signal, and the resulting installed-share.

**First pass (per-campus, abandoned as primary):** CV per campus (std/mean of gate signal counts) plus a Monte Carlo
chi-square (20,000 multinomial draws; H0 = signals split in proportion to nearby-crosswalk-count+1; expected-cell
counts too small for a normal chi-square approximation) with Holm correction across the 24 campuses (one test per
campus, repeated testing). Result at 300 m: 20 campuses testable (>=5 signals), only **중앙대 1 significant** after
Holm (raw p=0.002 -> 0.049), median CV 0.82, 14/24 campuses CV>=0.5. Not stable under the radius sensitivity
(0 significant at 200 m and 400 m) — low power from only 2-3 gates per campus, not evidence of no gap. Kept in notebook
§8 as the per-campus table/figure (`figures/h7/02_학교별_CV.png`), no longer the headline result.

**Final analysis (pooled, one test):** summed the per-campus chi-square statistics across all 67 gates into a single
statistic, compared to the same statistic under 20,000 joint Monte Carlo resamples (each campus resampled from its own
observed total) — no multiple-comparison correction needed, much higher power. Answers only "is there a within-school
gate gap overall", not which school. Two null-hypothesis bases reported together, since they answer different
questions:
- **basis="uniform"** (gates should have equal counts) — tests whether users encounter different signal counts
  depending on which gate they use.
- **basis="crosswalk"** (counts proportional to nearby crosswalk count) — tests whether the gap is unexplained by
  crosswalk supply (i.e. installation bias toward specific gates).

Also a binomial pooled test of installed-share (signal-bearing crosswalks / nearby crosswalks) across gates, same
uniform-share logic, n_sim=20,000.

**Result** (200/300/400 m):

| basis | 200 m | 300 m | 400 m |
|---|---|---|---|
| uniform | obs/exp 5.1x, p<0.0001 | 4.8x, p<0.0001 | 6.3x, p<0.0001 |
| crosswalk-proportional | 1.1x, p=0.29 | 1.2x, p=0.21 | 1.0x, p=0.51 |
| installed-share (300 m only) | — | p=0.83 | — |

**Conclusion:** gate-to-gate signal counts differ far beyond chance under the "should be equal" basis (stable across
radii) — H7's core claim ("access gap between gates within the same school") is supported. But under the
"proportional to nearby crosswalks" basis the gap is indistinguishable from random (obs/exp is about 1, p is about
0.2-0.5), and the installed-share test agrees (p=0.83). So the gap is **not** installation bias toward particular
gates; it is that gates simply sit in areas with different amounts of pedestrian infrastructure (crosswalk supply).
Practical implication noted: intervention should target crosswalk-poor gate areas' school routes, not redirect signal
installation toward specific gates.

**Limitations carried over:** gate coordinates are Kakao pins, not boundary-crossing points; radius is straight-line;
nearby gates can double-count the same signal; walking-path access to each gate was never verified (§16.8 list still
applies).

**Notebook 08** now 49 cells (§8 design, §8 per-campus table/figure, §8-1 pooled-test design, §8-2 pooled result +
figure `figures/h7/03_전체검정_기준별.png`), executed with 0 errors. Team Notion page "가설 검증" updated: §3 status row
(H7 -> 완료), §6 heading + intro (표본 확정 -> 완료, added "정하기->한계->결과" pointer), new "H7 검정 결과" block (design toggle,
2x3 result table, conclusion callout, pooled-test figure, per-campus CV toggle+figure, limitation note), §7 item 3
struck through as decided (300 m straight-line, test complete).

**Not yet decided:** whether/how to fold H7 into the final H5-H8 write-up scope of Holm correction across all four
hypotheses (§14.20's plan item 5); whether to verify sample gates on foot/street-view before reporting externally.

### 16.10 Side exploration: does crosswalk density itself relate to pedestrian risk (Claude, 2026-09-22 night)

**Where this came from:** H7's pooled test (§16.9) found the gate-to-gate signal gap is explained by nearby crosswalk
count, not installation bias. That raised the next question — is crosswalk density itself related to walking
difficulty/risk? The user's stated goal for the whole hypothesis-testing effort is "which variables most affect
visually-impaired walking difficulty, and how" — this is a step earlier in the causal chain than H5/H7 (which only
looked at signal presence).

**First attempt — reused existing data, failed to find anything:** `seoul_site_profiles.csv` (693 Seoul accident
hotspots, built 2026-09-21, already has `횡단보도수_0m/50m/100m`, `교차로수`). Ran Spearman correlation with p-values
(this session's rigor; the 2026-09-21 pass had only descriptive rho, no significance) against 4 outcomes (accident
count, casualties, casualties/accident, fatal+serious share): **16 combinations, 0 significant**, all |rho|<0.05.

**Diagnosed the problem — selection bias / range restriction:** these 693 sites are already government-designated
hotspots (nationwide threshold, min 7 incidents/yr — §10.5's "57% exactly 7" finding), so "safe" locations are absent
from the sample entirely. A null result here can't distinguish "no relationship" from "sample too narrow to see it."

**Redesigned — citywide 1 km grid, including zero-accident cells:** new module `seoul_grid_density.py`. Same 1 km
cell size as the H5 §2 Seoul map. No Seoul administrative-boundary shapefile exists in the project, so "urban Seoul"
was approximated as any 1 km cell containing >=1 crosswalk (539 such cells) — this is a stated limitation, not a
precise boundary. Per cell: crosswalk count, accident-hotspot count/sum, casualty sum, binary "has a hotspot".

**Result A (all 539 cells, hotspot presence as outcome):** strong and significant — Spearman rho=0.46 (p=1e-29,
crosswalk count vs hotspot count); hotspot-present cells average 55 crosswalks vs 33 for hotspot-absent (Mann-Whitney
p=2e-25, rank-biserial r=0.54, large); by crosswalk-count quartile, hotspot-presence rate rises 1.5% -> 32.3% ->
45.5% -> 61.5% (chi2 p=5e-25, Cramér's V=0.46, large). Flagged immediately as likely an **exposure confound**: busy
areas get more crosswalks AND more absolute accidents for the same reason (foot/vehicle traffic), not because
crosswalks cause danger.

**Result B (normalized by crosswalk count, to separate exposure from risk):** accidents-per-crosswalk across all 539
cells still correlates positively (rho=0.42) — but this is largely an artifact of the "0 vs nonzero" pattern from
cells with no hotspot. Restricting to the **189 cells that do have a hotspot** and recomputing: correlation
**reverses to weakly negative** (rho=-0.16, p=0.026, small effect); by quartile (hotspot cells only) the accidents-
per-crosswalk median goes 0.54 -> 0.36 -> 0.37 -> 0.39 — the crosswalk-poorest quartile has the highest per-crosswalk
accident density, not the richest.

**Conclusion (two layers):**
1. Whether an area has *any* accident hotspot tracks crosswalk density strongly, but this is best read as an
   urbanization/exposure proxy, not evidence that crosswalks cause danger.
2. Among areas that already have confirmed risk, crosswalk-poor spots show a modestly *higher* normalized accident
   density than crosswalk-rich spots — small effect, opposite sign from (1), consistent with the original intuition
   that under-provisioned infrastructure concentrates risk. Framed as: "not how many crosswalks an area has, but
   whether it has *few crosswalks relative to its risk level*" may be the more meaningful variable — flagged as a
   direction for further work, not a settled finding (small effect, n=189).

**Methodological lesson recorded in the notebook:** the same variable and the same accident data gave three different
answers depending on sampling — (1) hotspot-only comparison: no relationship; (2) full population incl. zero-accident
cells: strong positive relationship; (3) exposure-normalized, hotspot-only: weak negative relationship. Same pattern
of "answer depends on how you frame the test" as H5's radius sensitivity and H7's per-campus-vs-pooled test.

**Limitations:** no real Seoul administrative boundary (crosswalk-presence proxy can miss/include edge cells);
"no hotspot" cells are not proven zero-accident (hotspot designation itself has a nationwide threshold); crosswalks
and accident sites near a 1 km cell edge can fall into the neighboring cell; correlational, not causal — crosswalk
count is used as a rough proxy for exposure/foot traffic, not a real traffic-volume measurement.

Notebook 08 now has a new §9 ("곁가지 탐색 — 횡단보도 밀도는 보행 위험과 관련 있는가") with §9-1/9-2/9-3, 10 new cells
(id prefix `x-crosswalk-*`), 59 cells total, 0 errors. Figure `figures/h7/04_횡단보도밀도_사고위험.png` (two panels:
hotspot-presence rate by quartile; accidents-per-crosswalk by quartile, hotspot cells only). New script
`seoul_grid_density.py` (1 km grid builder, output cached at `data/seoul_relationship_eda/seoul_grid_1km.csv`).

Not yet reflected in the team Notion page (user asked to record this one in the notebook + this file only, not
explicitly Notion this time — confirm with the user before adding it there).

### 16.11 Follow-up: does crosswalk density relate to accident *severity*, not just frequency (Claude, 2026-09-23)

**Where this came from:** a Notion comment on §9's crosswalk-density finding, asking to extend it from "crosswalk-poor
hotspots have more accidents per crosswalk" (frequency/density) to accident *severity* (casualty/fatality counts).

**Method:** same `seoul_grid_1km.csv` (539 1km cells), which already has `사상자수합`/`사망자수합` per cell. Two layers,
same exposure-confound logic as §16.10:
1. Raw, all 539 cells: crosswalk count vs total casualties/fatalities (still exposure-confounded, expected to mirror
   the accident-count pattern).
2. Normalized by accident count (not by crosswalk count, a different axis from §16.10's normalization): restricted to
   the 189 hotspot cells with >=1 accident, computed casualties-per-accident and fatalities-per-accident, correlated
   each against crosswalk count.

**Result:**
- Raw (539 cells): crosswalk count vs total casualties rho=0.463 (medium, p=6e-30), vs total fatalities rho=0.288
  (small, p=1e-11) — same exposure-confound pattern as accident count in §16.10.
- Per-accident severity (189 hotspot cells): casualties-per-accident rho=0.147 (small, p=0.044, and in the *opposite*
  direction from §16.10's per-crosswalk risk-density finding — denser-crosswalk cells trend slightly higher, not
  lower); quartile medians nearly flat (1.00 -> 1.07). Fatalities-per-accident rho=-0.040, p=0.59, not significant.
  Only 87/189 hotspot cells have any fatality at all, so the fatality metric is thin/noisy.

**Conclusion:** crosswalk density looks like a frequency/density variable, not a severity variable. §9-3 (§16.10)
found crosswalk-poor hotspots have *more accidents per crosswalk*; this follow-up finds no meaningful relationship
between crosswalk density and how severe each individual accident is once it happens. Practical framing: a
crosswalk-poor spot isn't necessarily a spot where accidents are worse — it's a spot where they happen more often
relative to the infrastructure available.

**Notebook 08** now 64 cells (new §9-4: `x-severity-md`, `x-severity-run`, `x-severity-md2`, `x-severity-figure`,
`x-severity-conclusion-md`), 0 errors. New figure `figures/h7/05_횡단보도밀도_사고심각도.png` (two panels: casualties-
per-accident and fatalities-per-accident by crosswalk-density quartile, both flat). No new data files — reused
`seoul_grid_1km.csv`.

Also reflected as a reply to the user's Notion comment on §9, and will be added to the team Notion page (§9 gets a
new subsection).

### 16.12 Closing the crosswalk-density exploration: "is crosswalk supply insufficient relative to risk level" (Claude, 2026-09-23)

**Where this came from:** §9-3's conclusion suggested "not how many crosswalks an area has, but whether it has few
crosswalks relative to its risk level" might be the more meaningful variable. The user asked to directly test this
and use it to close out the whole crosswalk-density side-exploration (§9).

**Method:** on the 189 hotspot cells (same population as §16.10/16.11), defined "risk-relative infrastructure
deficiency" two independent ways and checked they agree (robustness):
1. Ratio-based (already used in §16.10): accidents per crosswalk = `사고건수합 / 횡단보도수`.
2. Rank-based: risk percentile (accident-count rank) minus infrastructure percentile (crosswalk-count rank).

Spearman rho between the two definitions = 0.864 (p=1e-57, large) — they agree strongly, so the concept is stable
regardless of how it's operationalized. Defined "deficient" cells as the top quartile by the ratio metric (48/189
cells, threshold >=0.72 accidents per crosswalk).

**Result:**
- Deficient cells are NOT simply "low-crosswalk neighborhoods" — their crosswalk count (51.3) is not significantly
  different from the rest (56.3, Mann-Whitney p=0.11, small effect). What distinguishes them is accident count: 64.7
  vs 18.0 (p=6e-21, large effect, r=-0.909).
- Concentration: these 48 cells are 25.4% of hotspot cells by count, but account for **55.1% of all accidents**
  while holding only **23.7% of crosswalk supply** — a policy-relevant asymmetry.
- Consistency check with §16.11: deficient cells are not more severe per accident (casualties-per-accident 1.07 vs
  1.08, p=0.505, negligible) — confirms again this is a frequency/concentration variable, not a severity variable.

**Conclusion:** "risk-relative crosswalk deficiency" is a statistically stable, well-defined concept (two independent
formulations agree, rho=0.864) and identifies a small set of cells (25% of hotspot cells) responsible for a majority
of accidents (55%) while holding a minority of infrastructure (24%). Framed as a possible prioritization variable:
more useful than raw crosswalk count for targeting where infrastructure investment might matter most, while still
carrying §9's overall limitations (correlational, no real Seoul boundary, crosswalk count as an imperfect exposure
proxy).

**Notebook 08** now 69 cells: new §9-5 (`x-deficit-md`, `x-deficit-run`, `x-deficit-md2`, `x-deficit-figure`,
`x-deficit-conclusion-md`) plus a closing `## 10. 곁가지 탐색 마무리` section summarizing 9-1 through 9-5 in one place.
0 errors. New figure `figures/h7/06_위험대비인프라부족.png` (100%-stacked bar: cell-share baseline vs accident-share vs
crosswalk-share for the deficient group).

**This closes the crosswalk-density side-exploration (§9) that started from a Notion comment on H7's conclusion.**
H5 and H7 remain the two completed formal hypotheses this session. H8 stays paused (comparison basis undecided), H6
(Chung-Ang vs Soongsil route comparison) was never started and is explicitly out of scope for this session — the user
asked to wrap up *this exploration thread*, not the full H5-H8 hypothesis suite.

Reflected in the team Notion page (new §9-5 + closing §10) and will be linked from the notebook's own closing section.

### 16.13 Rebuilt the deficiency measure at crosswalk unit, combined with signal-presence into a priority index (Claude, 2026-09-23)

**Where this came from:** after §16.12 closed the crosswalk-density exploration, the user asked how these findings
could feed an "ultimate visually-impaired walking-difficulty index." Claude recommended keeping only the two
variables that actually showed signal (§16.12's risk-relative deficiency measure, and the crosswalk's own audible-
signal presence from H5/H7), and flagged the main blocker: §16.12's deficiency measure was computed on a 1km grid,
which doesn't match the per-crosswalk unit a real index needs. User asked to rebuild it at crosswalk granularity.

**Method:** new module `crosswalk_deficiency.py`. For each of the 21,771 valid-position crosswalks (from
`h5_master.build_master()`), within radius R (moving window, not a fixed grid — avoids grid-boundary artifacts):
- 인프라_i (infrastructure) = count of other crosswalks within R
- 위험_i (risk) = sum of accident counts from `seoul_site_profiles.csv` hotspot sites within R

Crosswalks with 위험_i = 0 (no confirmed hotspot nearby) are excluded from the deficiency ratio, same logic as
§16.12's grid-hotspot restriction. Tested R = 300/500/800m for robustness (300m used by H7 gate↔signal linking, 1km
was the §16.10-16.12 grid size).

**Result (robustness across radii):** the two independent deficiency definitions (ratio-based, rank-based) agree
strongly at every radius (rho = 0.81–0.92, all large). At every radius, the top-quartile "deficient" crosswalks are
~25% of at-risk crosswalks by count but account for ~53% of risk (accident count) while holding only 21–25% of
infrastructure — reproducing §16.12's grid result (55.1% / 23.7%) almost exactly. One nuance: at the narrowest radius
(300m) deficient crosswalks also have modestly lower raw infrastructure than the rest (r=0.322, medium); this
shrinks to negligible (r=0.059) at 800m — narrow windows apparently catch some "low-risk, low-infra" neighborhoods
together by chance. Settled on **500m as the default** (9,183 at-risk crosswalks, 42% of the city total).

**New finding — the two candidate index components are independent:** cross-tabulated deficiency (top-25% at 500m)
against the crosswalk's own audible-signal presence (`음향_배정_15m` from `h5_master.py`, already established in H5).
Chi-square independence test: chi2=0.30, p=0.584, Cramér's V=0.006 (negligible) — whether an area is risk-deficient
and whether a specific crosswalk in it has its own audible signal are statistically unrelated. This means the two
variables carry non-redundant information and combine well as two axes rather than one substituting for the other.

**Built a 3-tier priority index from the 2x2 cross of the two independent axes** (radius=500m):
- Tier 1 (최우선/highest): deficient AND no signal — 1,141 crosswalks
- Tier 2 (주의/watch): exactly one of the two — 4,622 crosswalks
- Tier 3 (양호/ok): neither — 3,420 crosswalks
(12,588 of the 21,771 total crosswalks have no confirmed nearby risk and are out of scope for this index — no hotspot
within 500m, so "deficiency" isn't a meaningful label for them.)

**This is the session's proposed first-cut "궁극적 보행 난이도 지표" (ultimate walking-difficulty index) deliverable:**
Tier 1's 1,141 crosswalks are where confirmed accident risk, infrastructure under-provision relative to that risk,
and lack of the crosswalk's own audible signal all coincide.

**Limitations carried forward:** risk is bounded by the same 693 government-designated hotspots (nationwide >=7
incidents/yr threshold) used throughout §9 — risk below that threshold is invisible to this index; correlational,
not causal; radius-based neighborhoods still blend across areas near the boundary; neither infrastructure nor risk
captures true pedestrian/vehicle exposure; no on-the-ground verification of any Tier-1 crosswalk (same caveat as
H7's gate-verification limitation).

**Notebook 08** now 76 cells: new §11 (`x-unit-md`, `x-unit-run`, `x-unit-md2`, `x-unit-run2`, `x-unit-md3`,
`x-unit-figure`, `x-unit-conclusion-md`), 0 errors. New figure `figures/h7/07_횡단보도단위_우선순위.png` (tier counts;
radius-sensitivity share comparison). New script `crosswalk_deficiency.py`, output cached at
`data/seoul_relationship_eda/crosswalk_deficiency.csv` (9,183 rows, radius=500m, includes tier labels).

This closes out the whole H5/H7/§9 exploration arc for this session — the notebook's §11 conclusion cell explicitly
states hypothesis testing (H5, H7) and its side-explorations (§9, §11) are wrapped up. H8 stays paused, H6 was never
started.

### 16.14 Mapped the 1,141 Tier-1 crosswalks (Claude, 2026-09-23)

User asked to visualize the 1,141 Tier-1 (highest-priority) crosswalks from §16.13 on a map. Built two artifacts:

1. **Static overview** (`figures/h7/09_우선순위_지도_정적.png`, notebook §11-1): scatter in EPSG:5186 meters, no
   basemap (project still has no Seoul administrative-boundary shapefile) — 8,042 at-risk-but-lower-tier crosswalks
   in light gray as context, 1,141 Tier-1 crosswalks in orange on top. Road-network shape is visible from crosswalk
   point density even without a basemap.
2. **Interactive map** (`figures/h7/08_우선순위_지도.html`, new script `map_priority_crosswalks.py`): folium map on
   real OpenStreetMap tiles (had to switch from `cartodbpositron` to `OpenStreetMap` — CartoDB tiles now require an
   API key folium doesn't have configured). Three toggleable layers (1/2/3순위, colored orange/amber/blue, matching
   project palette) plus a background layer of the 693 accident hotspots (off by default). Each point's popup shows
   its risk count, infrastructure count, and signal presence. Custom HTML legend. 1순위 layer shown by default,
   others toggle-on. File is ~11MB (1,141+4,622+3,420+693 = ~9,876 markers total) — large but functional.

Coordinates reprojected from EPSG:5186 back to WGS84 (lon/lat) via pyproj for the folium map; matplotlib map kept in
projected meters (consistent with the project's established static-map style, e.g. H5's Seoul map).

**Notebook 08** now 79 cells (§11-1: `x-map-md`, `x-map-run`, `x-map-run2`), 0 errors.

Both files uploaded to the team Notion page as an inline image (static) and an embedded attachment (interactive
HTML), appended after §11.

### 16.15 Re-colored the priority map as a sequential ramp (Claude, 2026-09-23)

User asked to show 1/2/3-tier priority on the map using shades of one color instead of three distinct hues, since
the tiers are ordinal (a severity ramp), not unrelated categories.

**Method:** rewrote `map_priority_crosswalks.py` to use a single orange hue at three lightness steps
(Tier 1 #9A3B12 darkest → Tier 3 #F7C4A0 lightest) instead of orange/amber/blue. Also switched from
per-point `folium.CircleMarker` objects to `folium.GeoJson` + `style_function` (one compact GeoJSON blob per
tier instead of one JS marker object per point) — this cut the full 3-tier interactive map from 11MB down to
1.8MB, comfortably under Notion's file-attachment size limit, so the complete map (all 9,183 points, all three
tiers as toggleable layers) could be attached instead of the tier-1-only reduced version from §16.14.

Updated notebook §11-1 static map cell to plot all three tiers with the same sequential colors (light → dark
z-order so Tier 1 stays visible on top where points overlap).

**Notion friction:** tried to swap the old §11-1 images/embed in place via `update_content`, matching on the
original `file-upload://<id>` token used at write time. Failed — turns out once Notion stores an uploaded
image/embed, the fetched content shows either a resolved (and expiring) signed S3 URL (images) or a stable but
different `file://%7B"source":"attachment:<new-uuid>..."%7D` reference (embeds/files), never the original
upload token. Neither is reliably matchable as an old_str for later edits. Worked around it by appending a new
§13 section with the updated map rather than fighting in-place replacement — the same append-only pattern
used throughout this session's Notion updates, now with a concrete reason why in-place image replacement doesn't
work via this tool.

**Notebook 08** now 79 cells, 0 errors (cells x-map-run/x-map-run2 updated in place, not appended). New figures:
`figures/h7/09_우선순위_지도_정적.png` (v2, 3-tier shaded), `figures/h7/08_우선순위_지도.html` (v2, 1.8MB, all
3 tiers). Reflected in Notion §13.

### 16.16 Chung-Ang steps 1–2 and combined commute-route notebook (Codex, 2026-09-23)

The Soongsil step-1/2 method was applied to Chung-Ang University with a like-for-like comparison
rule: Kakao's `중앙대학교 서울캠퍼스` representative point (37.50514938189445,
126.95717341298158), 800 m radius, OSM campus polygon (way 284355223), and the three gates whose
names were confirmed by the 2026 official guide (Kakao coordinates for 정문, 중문, 후문).

New code/artifacts: `chungang_config.py`, `chungang_network.py`,
`data/chungang_campus_polygon.geojson`, `data/chungang_kakao_gates.csv`,
`data/chungang_center_candidates.csv`, and `data/chungang_network.gpkg`. The new Chung-Ang cells
were also inserted before section 3 in `06_숭실대_반경_1-3단계.ipynb` (IDs prefixed `cau-`).

Chung-Ang step-2 result: OSM graph 696 nodes/996 edges; 41 campus-interior edges (2,580 m)
removed; remaining graph 663 nodes/955 edges and one connected component; 333 in-radius,
outside-campus origin nodes and zero unreachable gates. Gate assignment: 후문 172 nodes, 정문 156,
중문 5. Straight-line vs walking-nearest gate differs for 17/333 (5.1%); 7/333 (2.1%) have a
first-vs-second gate gap under 50 m. The rear-gate virtual connector is 30.2 m, over the 25 m
warning threshold, and remains a map/field verification item.

At the user's request, `통학로규정.ipynb` was built as the focused deliverable containing all
Soongsil and Chung-Ang step-1/2 cells with their existing tables, static figures, and Folium map
outputs. It has 34 cells, zero error outputs, and ends with a same-rule comparison table. The
older Central-University 1 km/main-gate outputs must not be mixed with this new 800 m/Kakao-
representative-point comparison dataset.

The user-provided Notion page `중앙대 숭실대 통학로 결과`
(`3e4e935a81c980a8a956ca6bf3793804`) was filled as a team-sharing report. It includes the common
definition, per-campus results, a comparison table, limitations/verification items, and four uploaded
figures (campus-definition comparison and commute-route/overlap map for each university). Page icon
was set to 🗺️; database properties were updated to 상태=`완료`, 주제=`중앙대·숭실대 통학로 규정 및 비교`,
날짜=`2026-09-23`.

### 16.17 TMAP-as-validation / OSM-as-analysis commute-route pipeline started (Codex, 2026-09-23)

The user chose the hybrid design: TMAP selects/validates actual pedestrian routes, while OSM remains
the stable edge framework for attaching slope, crosswalk, audible-signal, and accident-risk variables.
The operational route definition is: for each real transit origin inside 800 m, request a TMAP
pedestrian route to every verified gate at that university and select the minimum walking-distance
gate/path. A main-gate-only analysis can be produced later by filtering the destination gate rather
than changing the base definition.

New module `tmap_commute_pipeline.py` implements origin collection, TMAP pedestrian calls,
minimum-distance gate selection, 10 m route sampling, and nearest-OSM-edge matching with a 20 m
tolerance and match-rate summary. `TMAP_APP_KEY=` was added to `.env.example`; the real `.env`
currently has no TMAP key, so no TMAP route request has been made yet. Raw TMAP paths are intentionally
kept in memory because the current TMAP terms say API-derived data may not be retained for over 24 h.

Initial origins are saved in `data/commute_origin_candidates.csv`: Soongsil 48 (44 OSM bus-stop
positions + all 4 Soongsil Univ. Station exits), Chung-Ang 73 (69 OSM bus-stop positions + all 4
Heukseok Station exits), 121 total. Opposite-direction stop positions remain distinct. With 5 and 3
gates respectively, a complete run will make 459 pedestrian-route calls, below the documented daily
free route allowance of 1,000.

`통학로규정.ipynb` now has 42 cells (8 new `tmap-*` cells), zero error outputs. It includes the route
definition, origin table/map, expected-call count, key status, and executable cells for TMAP request,
gate choice, and OSM matching. Synthetic-route validation of the matching function succeeded (88.9%
of 10 m samples matched within 20 m in the test). Next blocker: user must add `TMAP_APP_KEY` to `.env`;
then rerun `tmap-run-code` and inspect match rates before joining risk variables.

**Update later the same turn:** the user supplied a TMAP app key. It is stored separately in ignored
`.env.tmap` (never print it); `.gitignore` now excludes `.env` and `.env.tmap`. The first single-route
test succeeded (Soongsil middle-gate-front bus stop to main gate: 310 m / 236 s), then the full 459
origin-gate combinations were called. All 459 succeeded; one rerun was made within the 1,000/day free
limit after correcting an OSM match-rate tie-counting bug (equidistant edges duplicated sample rows).

Final TMAP choice results: Soongsil 48 origins -> 정문 12, 중문 13, 후문 13, 남문 7, 북문 3;
mean/median chosen-route distance 461.4/508 m, mean time 372.8 s. Chung-Ang 73 origins -> 정문 46,
중문 2, 후문 25; mean/median 682.6/661 m, mean time 528.8 s. TMAP-to-OSM matching at 10 m samples,
20 m tolerance: Soongsil mean 99.9%, median 100%, minimum 96.3%; Chung-Ang mean/median 100%,
minimum 97.6%. This validates the hybrid structure technically.

Raw TMAP geometries were discarded after aggregation. Persistent derived summaries only:
`data/tmap_gate_choice_summary.csv` and `data/tmap_osm_match_summary.csv`. `통학로규정.ipynb` now
has 43 cells, 0 error outputs, actual result tables in `tmap-results-md`, and `RUN_TMAP=False` by
default to prevent accidental quota-consuming reruns. Next work: join slope/crosswalk/audible-signal/
accident-risk attributes to the matched route edges.

### 16.18 Commute-route visualization completed (Codex, 2026-09-23)

The saved TMAP aggregate results and OSM network layers were visualized without any additional TMAP
API calls. New script `visualize_commute_routes.py` produces both a static comparison dashboard and
an interactive Folium map under `figures/commute_routes/`: `tmap_validated_commute_corridors.png`
and `tmap_validated_commute_corridors.html`.

The static dashboard shows each university's OSM commute corridor, colored by assigned gate and
weighted by shortest-path overlap, together with bus/subway origins, gates, TMAP gate-choice counts,
and mean route distance/time. The interactive map adds layer toggles and edge tooltips. It was opened
in Chrome and its six overlay layers, legend, and controls were confirmed.

`통학로규정.ipynb` now has 47 cells and a new section E (`commute-viz-*`) containing the rendered
static image, an interpretation table, the storage/representation caveat, and the interactive map.
The important caveat is explicit: the displayed lines are OSM-based commute corridors validated by
the 99.9–100% TMAP-to-OSM match rates, not retained individual TMAP route polylines. This avoids
overclaiming after the raw TMAP geometries were discarded.

### 16.19 Team briefing page created in Notion (Codex, 2026-09-23)

The previously blank Notion page `중앙대 숭실대 osm & 티맵`
(`3e4e935a81c9807a8a4fd48b47db5f2a`) was rewritten as a team briefing titled
`중앙대·숭실대 통학로 규정 및 TMAP 검증`. Database properties are now 상태=`완료`,
주제=`OSM 통학로 회랑 + TMAP 실제 도보경로 검증`, 날짜=`2026-09-23`, with a map icon.

The page covers the final definition, Kakao/OSM/TMAP role split, common 800 m rules, campus and
network statistics, 121 transit origins, all 459 successful route calls, gate-choice and distance/time
results, 99.9–100% OSM match rates, interpretation limits, and the next risk-variable joining steps.
The static commute-corridor dashboard was uploaded directly to Notion and embedded in the page.

**Notion completeness revision:** after the user noted sparse sections, the same page was expanded
with center/gate coordinates, gate-to-boundary validation, detailed radius-vs-polygon metrics for both
schools, per-gate OSM node/edge/distance statistics, origin/request counts, and a reproducibility table.
Four additional notebook figures were uploaded (two campus-definition comparisons and two school-
specific OSM corridor maps), and the interactive Folium map was uploaded as an embedded HTML
artifact. Verification fetch confirmed 12 main sections, five static images, and one interactive embed.

### 16.20 Final direction corrected to OSM-edge filtering with Option A origins (Codex, 2026-09-23)

The user clarified that TMAP should not define the analysis network. OSM remains the source of the
campus polygon, gate coordinates, nodes, and edges; TMAP actual pedestrian routes are a validation
filter used to retain OSM edges observed on real recommended walking paths. Origins use Option A:
stratified random coordinates in the 800 m, outside-campus area, snapped to the nearest OSM walk node.

New module `osm_tmap_edge_filter.py` implements: OSM path/campus-boundary gate coordinates (official
gate names are used only as nearest labels), 150 m stratified random point generation, OSM nearest-node
snapping and deduplication, OSM-network nearest-gate assignment, TMAP-to-OSM edge matching, and
`validated`/`unobserved` edge status. `unobserved` is deliberately not called non-walkable because
finite TMAP samples cannot prove that.

Local preparation (no external API calls) produced `data/soongsil_osm_gates.csv` (5 gates),
`data/chungang_osm_gates.csv` (3 gates), `data/option_a_random_origins.csv`, and
`data/option_a_origins_with_osm_gate.csv`. After snapping and deduplication there are 153 samples:
Soongsil 79 and Chung-Ang 74. Default validation uses one OSM-nearest gate per sample, requiring 153
TMAP calls; all-gates mode would require 617. `run_option_a_tmap_filter.py` is dry-run by default and
requires both `--execute` and exact `--confirm-calls 153` to make requests.

The preparation map is `figures/option_a/option_a_random_origins_osm_gates.png`. The focused notebook
now has 51 cells, zero error outputs, and a new final section F (`option-a-*`). Earlier transit-origin
TMAP work is explicitly relabeled as a preliminary match experiment. Per the user's instruction, no
TMAP/Kakao/OSM or other external API was called during the local code revision. Work is stopped before
the 153 TMAP requests; the Notion page was subsequently updated after the user explicitly allowed
Notion/Kakao API use.

**Permission update:** the user clarified that Kakao and Notion APIs are allowed; only TMAP calls are
forbidden without a new explicit go-ahead. The Notion briefing page was therefore corrected to the
Option A / OSM-edge-filter definition, its status was changed to `진행 중`, the earlier 121-origin
results were relabeled as a preliminary experiment, and the new 153-node preparation map was uploaded.
The page now clearly states that the real Option A TMAP filtering run is pending and no TMAP call was
made during the update.

### 16.21 Claude handoff (Codex, 2026-09-23)

#### Current truth / do not lose this distinction

The work is **not fully finished**. The implementation and local preparation are complete, but the
final TMAP filtering run has intentionally not been executed. Only TMAP calls are blocked unless the
user explicitly authorizes them. Kakao and Notion API calls are allowed by the user.

The earlier 459-call experiment is preliminary only: it used 121 real transit origins (48 Soongsil,
73 Chung-Ang) and Kakao gate coordinates, and proved that TMAP geometries can be matched to OSM edges.
Its aggregate files remain for reference, but they are not the final Option A result.

The final requested structure is:

```text
OSM campus polygon + OSM boundary/path gate coordinates
    -> OSM walk nodes/edges in 800 m outside-campus area
    -> Option A stratified random coordinates (150 m grid, seed=20260923)
    -> ox.distance.nearest_nodes snap + deduplicate
    -> OSM walking-nearest gate (one gate per origin in default mode)
    -> TMAP pedestrian route (ONLY remaining external call)
    -> sample route every 10 m; nearest OSM edge within 20 m
    -> edge status: validated (hit by >=1 TMAP route) / unobserved
    -> use validated edges for final distance/overlap/risk analysis
```

Do not call TMAP automatically, do not print the app key, and do not claim unobserved edges are
non-walkable. They are merely not observed in the finite sample.

#### Files created/changed

- `osm_tmap_edge_filter.py`: final Option A preparation, OSM gate derivation, graph reconstruction,
  random-origin generation, nearest-gate assignment, TMAP route wrapper, edge matching, and output save.
- `run_option_a_tmap_filter.py`: dry-run by default; prints expected calls. It refuses execution unless
  both `--execute` and the exact `--confirm-calls N` are supplied.
- `visualize_option_a_origins.py`: no-API sample/origin map.
- `update_option_a_notebook.py`: notebook update script.
- `통학로규정.ipynb`: now 51 cells, zero error outputs; section D/E are labelled preliminary and new
  section F (`option-a-*`) documents the final structure and current prepared sample.
- `data/soongsil_osm_gates.csv`: 5 OSM boundary/path crossing gate coordinates.
- `data/chungang_osm_gates.csv`: 3 OSM boundary/path crossing gate coordinates.
- `data/option_a_random_origins.csv`: raw grid sample and snapped-node records.
- `data/option_a_origins_with_osm_gate.csv`: 153 deduplicated snapped origins plus assigned OSM gate.
- `figures/option_a/option_a_random_origins_osm_gates.png`: prepared sample map.

Local preparation facts:

- Soongsil: 79 snapped sample nodes, expected default TMAP calls 79.
- Chung-Ang: 74 snapped sample nodes, expected default TMAP calls 74.
- Total default TMAP calls: 153.
- All-gates alternative would be 617 calls; do not use it unless the user specifically chooses it.
- `python -X utf8 run_option_a_tmap_filter.py` is a safe dry run and prints `DRY RUN`.
- Local checks passed: 153 rows, no duplicate school/node pairs, 8 OSM gates, notebook valid, zero errors.

#### Notion status

The page `https://app.notion.com/p/3e4e935a81c9807a8a4fd48b47db5f2a` is updated to title
`중앙대·숭실대 통학로 규정 — OSM 후보망과 TMAP 필터`, status=`진행 중`, and topic
`OSM 폴리곤·출입문·엣지 + Option A 임의점 + TMAP 경로 필터`. It includes the revised definition,
preliminary-vs-final distinction, 153-sample table, Option A image, and pending-call notice.

#### Safe next step for Claude

1. Read this handoff and inspect `osm_tmap_edge_filter.py` and the prepared CSVs.
2. Run only local dry-run/checks first; do not use TMAP.
3. Before any TMAP request, stop and ask the user to authorize exactly 153 calls, stating that the
   default mode requests one route per prepared origin to its OSM walking-nearest gate. If authorized,
   run `python -X utf8 run_option_a_tmap_filter.py --execute --confirm-calls 153`.
4. After the run, inspect route success, match-rate distribution, edge coverage, and disconnected
   components. Save only OSM edge aggregates and route summaries; discard raw TMAP geometry.
5. Update the notebook final section and the Notion page only after results pass QA. Keep the preliminary
   459-call tables clearly labelled as preliminary.

#### Prompt to give Claude

```text
Read C:/Users/kjyil/Documents/python_study/DartB_TOYPROJECT/codex&claude.md, especially §16.21, and continue the commute-route project from the current state.

The final requested design is OSM-first: OSM supplies campus polygons, OSM boundary/path gate coordinates, walk nodes, and candidate edges. Generate/use the prepared Option A 150 m stratified random origins in data/option_a_origins_with_osm_gate.csv, which contains 153 deduplicated origins snapped with ox.distance.nearest_nodes. Assign each origin to its OSM walking-nearest gate, then (only after I explicitly authorize it) request one TMAP pedestrian route per origin. Sample each route every 10 m, match samples to OSM edges within 20 m, mark edges hit by at least one route as validated and all others as unobserved, and use validated edges for the final analysis. Never call TMAP without first asking me and stating that the default run is exactly 153 calls. Never call the all-gates 617-call mode unless I explicitly request it. Kakao and Notion APIs are allowed; TMAP is the only prohibited API until authorization.

For now, do local QA only: inspect the code/CSV, run python -X utf8 run_option_a_tmap_filter.py (dry run), check duplicate nodes, gate assignments, graph connectivity, and notebook validity. Do not rerun the earlier 459-call experiment and do not treat its aggregates as the final result. Report findings and wait at the TMAP authorization boundary.
```

### 16.22 Local QA of Option A and main-gate snap fix (Claude, 2026-09-23)

No TMAP call was made. Local QA of §16.20–16.21 outputs: dry run OK (153 origins, 153 expected
calls); 0 duplicate (school, node) pairs (9 nodes appear in both schools because the 800 m buffers
overlap, which is expected); regeneration with seed 20260923 reproduces the same node set; both
graphs are one connected component containing every origin and gate node; notebook valid, 0 errors.

**Bug found and fixed:** `assign_osm_nearest_gate` snapped gates with plain
`ox.distance.nearest_nodes`. Soongsil 정문 landed on dead-end node `12794885931` (21.9 m, only edge is a
389.5 m footway) instead of the step-2 connector node `11413637697` (23.5 m); the two are 840 m apart on
the network, so 정문 received 0 origins. New helper `gate_nodes()` uses the step-2 `gate_connector`
node for each gate (fallback: nearest node with degree >= 2). The other 7 gates were already identical.
After the fix: Soongsil 정문 24 / 남문 21 / 후문 14 / 북문 10 / 중문 10 (24 moved: 북문→정문 10,
중문→정문 14; mean gate distance 629.3→588.8 m); Chung-Ang unchanged (정문 38 / 후문 34 / 중문 2).
Origins, gate CSVs and the 153 call count are unchanged. The assigned CSV now has a `gate_node` column.

Also: `run_tmap_filter_routes` now records per-request failures (`오류`) instead of aborting the whole
run, `validate_edges` skips failed routes and lists them in the summary, and the runner prints
success/failure counts. Verified offline with mocked routes (2 forced failures). Figure
`figures/option_a/option_a_random_origins_osm_gates.png` and notebook section F were regenerated
(51 cells, 0 errors).

Remaining notes: three origins sit at ~0–3 m from their gate (Soongsil 후문 0.0, 북문 0.6, 정문 2.9 m)
and may return a trivial or failed TMAP route; any edge within 20 m of a single sample is marked
validated, so cross streets at intersections can be over-validated (a minimum-samples-per-edge rule
is worth considering). The Notion page still shows the pre-fix gate breakdown. Next: user must
explicitly authorize exactly 153 TMAP calls
(`python -X utf8 run_option_a_tmap_filter.py --execute --confirm-calls 153`).

### 16.23 Option A TMAP filter run executed: 153 calls (Claude, 2026-09-23)

The user explicitly authorized exactly 153 calls and supplied a new TMAP key (stored only in `.env.tmap`).
Ran `python -X utf8 run_option_a_tmap_filter.py --execute --confirm-calls 153`: 153 succeeded, 0 failed.
Raw TMAP geometry was not saved. Outputs: `data/soongsil_tmap_validated_network.gpkg`,
`data/chungang_tmap_validated_network.gpkg` (layers `all_edges`, `validated_edges`),
`data/option_a_tmap_route_match_summary.csv`.

- Match rate (10 m samples, 20 m): Soongsil mean 98.7% (min 84.0%), Chung-Ang mean 99.7% (min 80.5%);
  only 2 routes below 90%.
- TMAP distance / OSM gate distance: median 1.05; 6 routes outside 0.67–1.5 (TMAP picked a different way).
- Three trivial routes (1–6 m) for origins sitting on the gate (Soongsil 후문/남문/북문).
- Validated edges: Soongsil 304/1,051 (22.8/66.6 km, 34.3%), Chung-Ang 272/955 (23.4/61.8 km, 37.3%);
  single-route edges 137 and 117.
- **QA issue:** validated edges are fragmented (Soongsil 14 components, Chung-Ang 13). Most minor
  components sit 0–10 m from the main component, i.e. short linking edges were missed by 10 m
  sampling or lost to a parallel nearest edge; a few gaps are ~100 m (TMAP likely used a way missing
  from OSM). Raw geometry is gone, so any repair must be OSM-only (e.g. bridge components within a
  small gap by OSM shortest path). Notebook/Notion not yet updated pending the user's decision.

### 16.24 15 m gap bridging, notebook F-2/F-3 and Notion update (Claude, 2026-09-23)

User approved bridging gaps <= 15 m. New `bridge_validated_gaps()` in `osm_tmap_edge_filter.py`
repeatedly joins the closest pair of validated components whose OSM network gap is <= 15 m, marking
the shortest-path edges `validation_status = 'bridged'`; `analysis_edge = validated | bridged`.
The runner now applies it automatically; `bridge_option_a_gaps.py` re-applies it to saved outputs
(idempotent, no TMAP). Results: Soongsil 11 bridged edges / 93.2 m, components 14 -> 3; Chung-Ang
8 / 39.1 m, 13 -> 5. Gaps left unbridged: Soongsil 18.9, 67.5 m; Chung-Ang 42.7, 105.2 m.
GPKGs now have layers `all_edges`, `validated_edges`, `analysis_edges`; log in
`data/option_a_bridged_gaps.csv`. Pre-bridge backups exist only in the session scratchpad.

Figure `figures/option_a/option_a_tmap_validated_edges.png` (`visualize_option_a_results.py`).
Notebook `통학로규정.ipynb`: 55 cells, 0 errors, new F-2 results / F-3 caveats (`option-a-result-*`,
`option-a-caveats`). Notion page updated (section 9 gate table, fix note, new 9-1 results with map,
limitations, status, files); status kept `진행 중` because risk-variable joining is next. The old
pre-fix origin image could not be removed via API (signed-URL match fails); a note marks it and the
corrected image sits below it — delete the old one manually in Notion.
Next: join slope / crosswalk / audible-signal / accident risk onto `analysis_edges`.

### 16.25 Final commute map secured; variable joining on hold (Claude, 2026-09-23)

User decision: secure the map only; slope/crosswalk/audible-signal/accident variables will be chosen
after a team discussion — do not join them until the user says so.
`export_option_a_map.py` (no API) writes the interactive map
`figures/option_a/option_a_commute_map.html` (OSM basemap; CartoDB now needs a key) and GIS layers in
`data/final_commute_map/`: `commute_analysis_edges.geojson` (595 edges = validated + bridged),
`commute_all_edges_with_status.geojson`, `osm_gates.geojson`, `option_a_origins.geojson`.
Rendered in headless Chrome and checked. The HTML was embedded in the Notion page under 9-1; the
status table marks variable joining as `보류 · 팀 논의 후 결정`.
Basemap note: opened as a local file, the official OSM tiles show "Access blocked" (no Referer), keyless
CartoDB shows an "API KEY REQUIRED" watermark, and Esri street/topo/gray have no Korean tiles. The map
now defaults to HOT tiles (`tile.openstreetmap.fr/hot`) with OSM standard and Esri imagery as options.
The copy embedded in Notion was uploaded before this change (OSM standard basemap).

### 16.26 Colab share notebook (Claude, 2026-09-23)

`make_colab_map_notebook.py` builds `통학로_최종지도_공유.ipynb` (1.6 MB, 2 cells): a Korean
explanation cell and a code cell whose **saved output** is the full interactive map (base64 iframe),
so it renders in Colab without running anything or uploading data. Re-running the cell needs
`option_a_commute_map.html` uploaded to the Colab session. Rendering was checked via nbconvert +
headless Chrome, not inside Colab itself. The user uploads it to Colab/Drive and shares it (no Google
Drive connector here). If the basemap does not load in Colab, switch the layer to "OSM 기본".

### 16.27 Session summary and current state (Claude, 2026-09-23) — read this first

**What was done this session (details in §16.22–16.26):**

1. Local QA of the Codex Option A preparation: dry run, duplicates, reproducibility, graph
   connectivity and notebook validity all passed.
2. **Bug fixed:** Soongsil 정문 had been snapped to a dead-end node 840 m (network) away from its real
   entrance, so it received 0 origins. Gates now use the step-2 `gate_connector` node
   (`gate_nodes()`). 24 Soongsil origins moved to 정문; Chung-Ang unchanged; still 153 origins/calls.
3. TMAP requests now record per-request failures instead of aborting the whole run.
4. With explicit user authorization and a **new TMAP key** (in `.env.tmap` only), exactly **153
   TMAP calls** were made: 153 success, 0 failure. Raw geometry was not saved.
5. The validated network was fragmented (14 / 13 components). With user approval, gaps <= 15 m were
   bridged by OSM shortest paths (`bridged` status). Components are now 3 / 5.
6. Final map secured as static PNG, interactive HTML, GeoJSON layers and a Colab share notebook.
   Notebook `통학로규정.ipynb` section F, the Notion page and this file were updated.

**Final numbers**

| | 숭실대 | 중앙대 |
|---|---|---|
| Origins / TMAP routes | 79 | 74 |
| Gate assignment | 정문 24 · 남문 21 · 후문 14 · 북문 10 · 중문 10 | 정문 38 · 후문 34 · 중문 2 |
| Match rate mean (min) | 98.7% (84.0%) | 99.7% (80.5%) |
| validated / bridged / unobserved edges | 304 / 11 / 736 | 272 / 8 / 675 |
| Analysis network (validated + bridged) | 315 edges · 22.9 km of 66.6 km | 280 edges · 23.4 km of 61.8 km |
| Components before → after bridging | 14 → 3 | 13 → 5 |

**Key files**

- Code: `osm_tmap_edge_filter.py` (`gate_nodes`, `bridge_validated_gaps`, error-tolerant
  `run_tmap_filter_routes`), `run_option_a_tmap_filter.py` (dry run by default; applies bridging),
  `bridge_option_a_gaps.py`, `visualize_option_a_results.py`, `export_option_a_map.py`,
  `make_colab_map_notebook.py`, `update_option_a_notebook.py`.
- Data: `data/{soongsil,chungang}_tmap_validated_network.gpkg` (layers `all_edges`,
  `validated_edges`, `analysis_edges`), `data/option_a_tmap_route_match_summary.csv`,
  `data/option_a_bridged_gaps.csv`, `data/option_a_origins_with_osm_gate.csv` (now has `gate_node`),
  `data/final_commute_map/*.geojson`.
- Maps: `figures/option_a/option_a_tmap_validated_edges.png`,
  `figures/option_a/option_a_commute_map.html`, `통학로_최종지도_공유.ipynb`.

**Decisions and rules still in force**

- TMAP is called only with explicit user authorization and a stated call count. Never use the
  617-call all-gates mode unless requested. Do not rerun the 153 calls without asking.
- `unobserved` means "not seen in this sample", never "not walkable".
- Joining slope / crosswalk / audible-signal / accident variables is **on hold until the team
  decides**. Do not start it on your own.
- The earlier 459-call transit-origin experiment stays labelled preliminary.

**Known limitations / open items**

- Unbridged gaps > 15 m: Soongsil 18.9, 67.5 m; Chung-Ang 42.7, 105.2 m (possibly ways missing from OSM).
- Nearest-edge matching can validate short side streets at intersections (137 / 117 single-route edges).
- Three Soongsil origins lie 0–6 m from their gate, so their routes carry almost no information.
- Notion: the old pre-fix origin image in section 9 must be deleted manually. The Notion interactive
  embed predates the basemap change and uses the OSM standard basemap.
- The TMAP key was pasted into chat; the user may want to reissue it later.
- If `통학로규정.ipynb` is open in VS Code, use Revert File before saving.

### 16.28 Risk-index direction for A/B/C fixed; nothing computed yet (Claude, 2026-09-24)

User decisions: A, B, C stay **separate** (no composite). H3 is dropped as the basis for A (installation bias /
reverse causation; accident data is not blind-specific). Full plan written to a private Notion draft
"보행 위험도 지표 A·B·C 진행 방향 (2026-09-24)" (https://app.notion.com/p/3e5e935a81c9815997ebfd4561b4ba4d) — read it
before starting. Summary:
- Common preprocessing: crossing-point layer on `analysis_edges` — Seoul crosswalks grouped by `교차로관리번호`,
  centroid snapped to nearest OSM node (<=30 m, check distribution first); "intersection without crosswalk" =
  node where >=2 car-road edges (residential+) meet with no matched crosswalk.
- A (횡단 위험): reuse §16.13 exactly — axis 1 = risk-relative infrastructure deficiency (500 m fixed, Seoul-wide
  top-25% threshold reused, no hotspot within 500 m -> "위험 미확인", not 0); axis 2 = support level (signal+audible /
  signal only / no signal / no crosswalk), ordered by nesting logic; tiers = §16.13 rule. Gates are not used.
- B (경사 위험): resample edges every 10 m, same interpolation as `compute_edge_slope.py`. B-1 grade by legal lines
  1/18 (5.6%) and 1/12 (8.3%); B-2 abrupt-change flag (adjacent 10 m segments jump <=5.6% <-> >8.3%), kept separate.
  Edges <20 m: change not computable. `highway=steps` flagged separately.
- C (인지 복잡성): event count per edge (crossing 1, two-stage 2 only if "이단" code is confirmed, sharp turn 1);
  decision nodes as a separate node layer. Sharp turn = net heading change >=45 deg within 10 m after 2 m resampling;
  basis = clock-direction logic + TMAP turn codes (verify), sensitivity 30/45/60 deg x 5/10/20 m.
- TMAP: user confirmed the key in `.env.tmap` (masked E4sw...7RPc, saved 2026-09-23) and said to proceed. A re-run
  of the same 153 routes to store guidance points (turn/stairs/crosswalk codes) is an optional C calibration; confirm
  the 153 count with the user right before running.

**§16.28 update (same day, user decisions):** A no longer uses the §16.13 binary 1/2/3 tiers. A risk score (0-4) =
support score (signal+audible 0 / signal only 1 / no signal 2 / no crosswalk 3) + deficiency score (Seoul-wide top-25%
= 1, else 0); the score is used as is, no grouping. No hotspot within 500 m -> "위험 미확인", type shown, no score.
Multiple crosswalks at one intersection: score each crosswalk, intersection takes the max. Mismatch type (보행등 무 but
audible signal within 15 m, ~27%) -> scored as "no signal" (2); the alternative (0) is reported as sensitivity only.
Seoul-wide crosswalks get rescored the same way for comparison. Notion page retitled by the user to
"보행 위험도 지표 A·B·C 진행 방향" and edited by hand — edit it with targeted update_content, never replace_content.

### 16.29 Indicator A computed in `위험도지표 생성.ipynb` (Claude, 2026-09-24)

User asked to run everything in `위험도지표 생성.ipynb` (was empty). Module `risk_a_crossing.py` implements §16.28's A;
notebook section A (A-1..A-5, 0 errors) is regenerated by a scratchpad script, so edit the notebook directly from now on.
Rule change found while running: crosswalk-group centroids are snapped to the nearest **route** node (<=30 m), not the
nearest node of the full graph — big intersections have several OSM nodes and 8 Soongsil groups were being lost.
Centroid->route-node distances: 0-20 m then a gap to 40 m+, so 30 m cuts almost nothing.
Results (500 m): Soongsil 42 crossing points (25 with crosswalks, 17 without) -> 0/1/2/3/4 pts = 1/1/5/9/0, 위험 미확인 26;
Chung-Ang 65 (36/29) -> 2/2/9/20/7, 미확인 25. Seoul q = 0.853. Route crossings skew higher than Seoul (3점 22%/50% vs 11%).
Mismatch under the 15 m assignment rule is 15.2% of 보행등 무 crosswalks (1,251/8,252), not ~27% (that was the 06 nearest rule).
Sensitivity: mismatch=0 changes almost nothing; radius is strong (800 m -> 미확인 2 per school; 300 m -> 31/41);
including `service` roads explodes "no-crosswalk intersections" (17->~126, 29->~157), mostly service roads joining a
car road (75/103 nodes) or service-only junctions (48/52). Open decision for the user: service handling.
Outputs: `data/risk_index/A_crossing_points.{csv,geojson}`, `figures/risk_index/A_횡단위험_지도.png`.
**§16.29 update — service decision (user, 2026-09-24):** car roads = residential+ plus `service=alley` only; untagged
service and parking_aisle are not car roads ("도로는 포함하지 않기로"). `car_degree`/`crossing_points` now take
`service_mode` ('alley' default, 'none'/'all' for sensitivity). Result: Soongsil 44 points (19 no-crosswalk; 3점 9->11),
Chung-Ang unchanged (65). Only 13/8 alley edges exist in the two OSM networks.
**§16.29 update — A-6 segment view and school score (2026-09-24):** notebook cells `a6-*` (before A-5 save). Edge A =
max A score of its end nodes; both ends 미확인 -> "위험 미확인"; no crossing at either end -> "교차 지점 없음".
School score = mean A over scored crossing points (bootstrap 95% CI, seed 20260924): Soongsil 2.44 (n=18), Chung-Ang
2.70 (n=40), Mann-Whitney p=0.269 (not significant). 3+ points per km: 0.48 vs 1.15. 미확인: 59% vs 38%.
Length share with score 3-4: Soongsil 6.2%, Chung-Ang 23.6%. Figures `figures/risk_index/A_구간별_지도.png`,
`A_구간길이_구성.png`, `A_학교_종합비교.png`.
**§16.29 update — scope of A (user, 2026-09-24):** A evaluates crossing points only. Segments with no crossing at either
end are labelled "A 적용 대상 아님" and get no A score (not "safe"); no segment-level A layer. School comparison uses
crossing points only; the segment map / length-share chart are reference views. (No-crossing segments are mostly
service 44-60% and residential 11-15% roads — a possible "walking beside traffic" risk, but outside A by decision.)

### 16.30 Indicator B started — data resolution blocks the 10 m design (Claude, 2026-09-24)

`risk_b_slope.py` implements §16.28's B (10 m pieces, same griddata interpolation as `compute_edge_slope.py`). Result was
implausible: "위험" = 86% (Soongsil) / 74% (Chung-Ang) of length, max piece grade up to 102%. Check (notebook B-0,
cells `b*`): predicting the 330 spot heights from contours only gives RMSE 1.98 m (median |err| 1.06 m), so grade error
is ~±28%p for 10 m pieces, ±14 (20 m), ±9 (30 m), ±5.6 (50 m). Results depend strongly on piece length (급변 358 -> 38
at 50 m). Conclusion: with the 5 m contours, 10 m grades and B-2 급변 are not reliable. Waiting for the user to choose:
better DEM vs longer pieces (B-2 likely dropped). Notion A section updated (alley rule, 15.2% mismatch, scope, results).
**§16.30 update — B finalized at 60 m (user, 2026-09-24):** NGII 공개DEM turned out to be a 90 m grid (sheets 37608/37612,
2014-2025; also a Bukhansan ASTER file) — unusable; project `DEM/` copy deleted, originals remain in ~/Downloads.
B = max grade over >=60 m baselines (`score_b`): edges >=60 m split into floor(L/60) pieces; edges <60 m measured over a
60 m line centred on the midpoint along start->end direction. B-2 (급변) dropped. `기준선_근처` flags edges within
±4.7%p of 5.6/8.3% (0.9-13% -> most edges). Results (length share 양호/주의/위험): Soongsil 27.3/22.1/50.6,
Chung-Ang 36.8/18.9/44.3; "certain 위험" (>13%) 24.6% vs 24.7%. Base 50/80 m changes 위험 by ~±4%p. Notebook cells
b1-b5, outputs `data/risk_index/B_edges.{csv,geojson}`, figures `B_경사위험_지도.png`, `B_구간길이_구성.png`.
Note: stairs flag comes from merged OSM edges whose highway list includes steps (one long Chung-Ang path edge).

### 16.31 Indicator C computed; Notion B updated (Claude, 2026-09-24)

Notion B section rewritten to the final 60 m method (why 60 m, B-2 dropped, 기준선 근처, results). `risk_c_complexity.py`
+ notebook cells `c*`: crossing = 1 per A crossing point ("이단" not weighted — meaning unconfirmed online, and 이단 is 91%
of signalled crosswalks, so unlikely to mean island two-stage crossings); sharp turn = heading change >=45 deg within
10 m after 2 m resampling, contiguous flags = 1 turn, only inside edges. Edge C = turns + crossing events split evenly
over the route edges touching that node (sums to totals). Junctions (full-network degree >=3) shown separately, not scored.
Results per km: Soongsil 5.55 (crossings 1.92 + turns 3.63), Chung-Ang 5.73 (2.78 + 2.95); junctions 11.6 vs 10.2.
Sensitivity (30/45/60 deg x 5/10/20 m): rank rho vs base 0.66-0.94; Soongsil has more turns/km in every setting except
30 deg/5 m. Outputs `data/risk_index/C_edges.{csv,geojson}`, figures `C_인지복잡성_지도.png`, `C_학교_종합비교.png`.
**§16.31 update — 이단 = two-stage crossing, weighted 2 (user/team, 2026-09-24):** team says 이단 = crosswalk - middle
point (island/median) - crosswalk. Official Seoul table definition (OA-15554 「교통안전시설물 테이블 정의서(횡단보도)」)
lists only code names 001 일단(화살표있음) / 002 이단(화살표있음) / 003 일단(화살표없음) / 004 이단(화살표없음) /
005 삼단(화살표있음); academic definition: 심관보 외(2013) 한국ITS학회 논문지 12(6) "보행자가 도로를 두 번에 나누어
횡단하게 하는 횡단보도". Data check: 이단 records are not paired with close 이단 neighbours (15 m neighbour 23.5% vs
일단 38.4%) -> one record likely = the whole split crossing. `risk_a_crossing` now outputs 횡단단수_최대/이단_수;
`score_c(stage_weight=True)` counts 일단 1 / 이단 2 / 삼단 3 (max at a point; unmarked = 1). C per km: Soongsil 6.51,
Chung-Ang 7.18 (all=1: 5.55 vs 5.73). Notion C section updated. A B-heading on Notion reads "…은 뺄다" (typo from an
earlier edit; could not be matched via API) — user to fix by hand.

### 16.32 Consolidated record: risk indicators A/B/C + public dashboard (Claude, 2026-09-24) — read this first

This section summarizes §16.28–16.31 and everything in `위험도지표 생성.ipynb`, then documents the dashboard.

#### 1. Why three separate indicators
- Original plan: rank four crossing types for A using H3 ("crosswalks without audible signals are near accident
  hotspots more often"). Seoul-wide H3 came out reversed (signals are 1.4–2.1x MORE likely near hotspots at 50/100/200 m).
  Signals are installed where risk is already high (reverse causation), so accident data cannot rank support levels.
  The user agreed not to re-shape hypotheses until they "work".
- Decision: A (crossing), B (slope), C (cognitive complexity) are computed and shown SEPARATELY, never summed.
- A's evidence base is the H7-derived "risk-relative infrastructure deficiency" (notebook 08 §9/§11; two definitions
  agree, rho=0.864), not H3.
- Unit of analysis: TMAP-validated OSM commute network (`analysis_edges`, §16.27): Soongsil 315 edges / 22.9 km,
  Chung-Ang 280 edges / 23.4 km.

#### 2. Notebook `위험도지표 생성.ipynb` (54 cells, runs top to bottom with 0 errors)
- `intro`, `process-log` (Korean narrative of every attempt and decision; keep it in sync), then sections A, B, C.
- Helper modules (project root): `risk_a_crossing.py`, `risk_b_slope.py`, `risk_c_complexity.py`.
- Outputs: `data/risk_index/A_crossing_points.{csv,geojson}` (109 points), `B_edges.{csv,geojson}` and
  `C_edges.{csv,geojson}` (595 edges each); figures in `figures/risk_index/`.
- Cells were generated by scratchpad scripts; from now on edit the notebook directly. The user keeps it open in
  VS Code: after any programmatic edit they must use "Revert File" before saving, or the stale buffer overwrites it.

#### 3. Common step — crossing points on the commute network
- Seoul crosswalks (21,771 valid) grouped by `교차로관리번호`; group centroid snapped to the nearest ROUTE node within
  30 m. (The first version snapped to the nearest node of the full graph and lost 8 Soongsil intersections because big
  intersections have several OSM nodes.) Centroid-to-route-node distances cluster at 0–20 m with a gap to 40 m.
- "Intersection without crosswalk" = route node where >=3 car-road edge ends meet, with no crosswalk group attached and
  no crosswalk within 30 m. Car roads = residential and above + `service=alley` only (user decision; counting all
  `service` roads inflated the count 19->126 / 29->157, mostly driveways and parking aisles). Only 13/8 alley edges exist.
- Result: Soongsil 44 points (25 with crosswalks, 19 without), Chung-Ang 65 (36, 29).

#### 4. A — crossing risk (points)
- A score 0–4 = support score + deficiency score, used as is (no tier grouping).
  Support: 0 signal+audible / 1 signal only / 2 no pedestrian signal / 3 no crosswalk (nesting logic: an audible signal
  needs a pedestrian signal, which needs a crosswalk). Deficiency +1 if (hotspot accidents within 500 m / crosswalks
  within 500 m) is in Seoul's top 25% (threshold 0.853, fixed from Seoul, not recomputed on the routes).
- No hotspot within 500 m -> "위험 미확인" (no score; not "safe"). Several crosswalks at a point -> max score.
- Mismatch (보행등 무 but an audible signal assigned within 15 m) = 15.2% (1,251/8,252) under the H5 assignment rule
  (the earlier "27%" came from notebook 06's nearest-signal rule) -> scored 2 (conservative); scoring it 0 changes almost nothing.
- Scope (user decision): A evaluates crossing points only. Edges with no crossing at either end are
  "A 적용 대상 아님" (48–67% of route length; mostly service/residential roads). Edge colouring by the max A of the
  end nodes is a reference view only.
- Radius fixed at 500 m (300 m -> 31/41 unknown points, 800 m -> 2/2).
- Results: counts for 0/1/2/3/4/unknown — Soongsil 1/1/5/11/0/26, Chung-Ang 2/2/9/20/7/25.
  School score = mean A of scored points: Chung-Ang 2.70 (bootstrap 95% 2.40–3.00, n=40), Soongsil 2.44 (2.06–2.78,
  n=18); Mann-Whitney p=0.27 (not significant). Points scoring 3+ per km: 1.15 vs 0.48. Unknown share 38% vs 59%.
  Crosswalk points on the routes score higher than Seoul overall (share scoring 3: Seoul 11%, Soongsil 22%, Chung-Ang 50%).

#### 5. B — slope risk (edges)
- The planned 10 m pieces gave implausible output (74–86% of length "위험", grades above 100%). Check: predicting the
  330 spot heights from the 5 m contours alone gives RMSE 1.98 m, so grade error ≈ sqrt(2)·RMSE/L = ±28%p at 10 m,
  ±9 at 30 m, ±4.7 at 60 m. The NGII "공개DEM" the user downloaded is a 90 m grid (sheets 37608/37612): unusable, deleted.
- Final: grade over >=60 m baselines (edges >=60 m split into floor(L/60) pieces, take max |grade|; edges <60 m measured
  over a 60 m line centred on the midpoint along the start->end direction). Same griddata interpolation as
  `compute_edge_slope.py`. Grades: 양호 <=5.6% (1/18), 주의 <=8.3% (1/12), 위험 >8.3%; source: 장애인등편의법 시행규칙
  [별표 1] 제1호 접근로 기울기. B-2 (abrupt change) dropped. `기준선_근처` flags edges within ±4.7%p of a threshold
  (grades 0.9–13%: 239/315 and 188/280 edges), drawn dashed. Stairs flagged separately (merged OSM edges can mark a
  long path as stairs).
- Results (length share 양호/주의/위험): Soongsil 27/22/51%, Chung-Ang 37/19/44%; "certain 위험" (>13%) 25% for both;
  length-weighted max grade 9.8% vs 8.9%. Baselines of 50/80 m move 위험 by about ±4%p; the school order is unchanged.

#### 6. C — cognitive complexity (edges)
- Crossing events: 1 per A crossing point, weighted by stage: 일단 1 / 이단 2 / 삼단 3 (max at a point; intersections
  without crosswalks count 1). 이단 = crosswalk – middle point (island/median) – crosswalk (confirmed by a teammate in the
  data; academic definition in 심관보·김중효·박경우·하동익 2013, 한국ITS학회 논문지 12(6); Seoul's OA-15554 table
  definition lists only the code names 001–005). Data check: 이단 records are not paired with nearby 이단 records, so one
  record = the whole split crossing. Caveat: 56% of Seoul crosswalks are 이단.
- Sharp turn = heading change >=45 deg within 10 m after 2 m resampling; contiguous flags count once (right angle 1,
  R=50 m curve 0). Basis for 45 deg: the TMAP pedestrian API `turnType` announces turns from 2/10 o'clock (codes 17/18)
  and has no 1/11 o'clock codes. Turns between edges at nodes depend on the route and are excluded. Junctions
  (full-network degree >=3) are shown but not scored.
- Edge C = turns + crossing events split evenly over the route edges touching the node (sums to the totals).
- Results per km: Chung-Ang 7.18 (crossings 4.23 + turns 2.95), Soongsil 6.51 (2.88 + 3.63). With all crossings = 1:
  5.73 vs 5.55, so the gap comes mostly from two-stage crossings (34 vs 22 points). Angle/window sensitivity
  (30/45/60 deg x 5/10/20 m): rank rho 0.66–0.94.

#### 7. Notion
- Final-method page "보행 위험도 지표 A·B·C 진행 방향" (https://app.notion.com/p/3e5e935a81c9815997ebfd4561b4ba4d) and
  process page "보행 위험도 지표 A·B·C 진행 과정 기록" (https://app.notion.com/p/3e5e935a81c981f19d25d78e155875ea), both in
  DartB workspace > DartB 세션 기록(개인) > 개인 기록 database. The user edits these pages by hand: use targeted
  `update_content` only, never `replace_content`. Image uploads failed (Notion `MemcachedCrossCellError`), so figures
  are not on Notion yet. One B-section heading has a typo left by an earlier edit; the user will fix it by hand.

#### 8. Dashboard (public page)
- URL: https://claude.ai/artifact/6ea3bkDBHU2F3zqQgJuMLe (Claude artifact; private until the user shares it from the
  page's Share menu).
- Files: `dashboard/build_dashboard.py` (Python: reads the risk_index outputs, the `all_edges` background network,
  campus polygons and OSM gates, computes school summaries with bootstrap seed 20260924, and injects one JSON blob into
  the template), `dashboard/template.html` (HTML/CSS/vanilla JS + d3 v7.9.0 from cdnjs), output `dashboard/index.html`
  (~300 KB, self-contained). Rebuild with `python -X utf8 dashboard/build_dashboard.py`, then republish index.html to
  the same artifact URL.
- Views: 소개 (purpose, criteria A/B/C, data sources, caveats) / 중앙대 / 숭실대 (map + score cards) / 두 학교 비교
  (same-axis bars, composition bars, interpretation, summary table, limitations). Hash deep links: #intro #chungang
  #soongsil #compare.
- Map: no tile basemap (the artifact CSP blocks external images), so the full OSM walk network is drawn faintly with
  the campus outline and gates; d3 zoom/pan; tooltips on edges and points. The A/B/C toggles combine through separate
  visual channels: B owns edge colour when on (dashed = 기준선 근처); otherwise A colours edges (max end-node score);
  C colours edges only when shown alone, otherwise it sets edge width; A always adds crossing-point markers
  (circle = crosswalk, square = no crosswalk, hollow = unknown). Legend and score cards follow the toggles.
- Style per the user: black background, white text, single dark theme. Ramps: A amber, B rose, C cyan.
- Headline interpretation on the page: Chung-Ang carries more crossing burden (A, C crossings); Soongsil more terrain
  (B) and winding paths (C turns); the indicators are not combined into one ranking.

#### 9. Open items
- Confirm the 이단 code meaning with Seoul if needed; check the public-sidewalk slope guideline
  (「보도 설치 및 관리 지침」); retry the figure upload to Notion; share the dashboard link when the user wants it public.

### 16.33 Dashboard moved to a real OpenStreetMap basemap and published on GitHub Pages (Claude, 2026-09-24)

- The user wanted a real map instead of the drawn network. The claude.ai artifact CSP blocks external images, so map
  tiles cannot load there. Solution: a second template for normal web hosting.
- `dashboard/template_osm.html` = same page (intro / 중앙대 / 숭실대 / 두 학교 비교, score cards, comparison, black
  background + white text) with the map section rewritten for Leaflet 1.9.4 (cdnjs) + OpenStreetMap standard tiles
  (`tile.openstreetmap.org`, attribution shown). Default is a darkened basemap (CSS filter on the tile pane) with a
  "밝은 지도 / 어두운 지도" toggle and a "전체 보기" (fit) button. Edges are Leaflet canvas polylines with a thin black
  casing; crossing points and gates are divIcons; tooltips on hover/tap. The A/B/C channel logic is unchanged from §16.32.
- `dashboard/build_dashboard.py` now writes both `dashboard/index.html` (artifact version, SVG, no tiles) and
  `dashboard/site/index.html` (OSM version, ~170 KB; the background network `bg` is dropped because the real map
  replaces it). Local check: served via `python -m http.server` and screenshotted in headless Chrome; tiles and layers
  render correctly (tiles need an http(s) origin; `file://` gets "Access blocked" from OSM).
- Published to the user's existing public repo `kjyilj0707/DartB_TP` (the user chose it; GitHub Pages was already on,
  branch main, root). The repo's existing root `index.html` ("Add accessibility safety dashboard") was left untouched;
  the dashboard lives in `commute-risk-dashboard/` (`index.html` + `README.md`), commit 29eeb5f.
  Public URL: https://kjyilj0707.github.io/DartB_TP/commute-risk-dashboard/
- To update: rebuild with `python -X utf8 dashboard/build_dashboard.py`, copy `dashboard/site/index.html` to
  `DartB_TP/commute-risk-dashboard/index.html`, commit, push (a clone lives only in the session scratchpad; re-clone
  with `gh repo clone kjyilj0707/DartB_TP`). The artifact version (https://claude.ai/artifact/6ea3bkDBHU2F3zqQgJuMLe)
  stays as a tile-free backup.

### 16.34 Tree-model validation of the risk indicators — planning decisions (Claude, 2026-09-25)

Context: A/B/C and the dashboard are considered done (the team may still revise them). The user wants two extensions:
(1) validate/evaluate the indicators with a tree-based ML model, (2) later, a TTS voice-guidance service for points on the
route (more fitting for blind users than a visual map). Order: tree model first, TTS planned afterwards.

**Label discussion (what the model predicts)**
- The indicators are rule-based, so there is no ground truth. Options considered: Seoul pedestrian accident hotspots
  (`보행자_사고_다발지역.csv`, 693 Seoul hotspots, all >=7 accidents); `교통약자다발지점_보행자.csv` (750 rows, no
  coordinates, only 지점명 -> needs geocoding); TAAS per-accident coordinates (usually requires a data request);
  blind users / O&M expert ratings (most valid, too small to train on); team labelling from Kakao road view with a
  checklist + Cohen's kappa; per-indicator checks (C: TMAP turnType points vs our sharp-turn detector, needs the 153
  calls again with approval; B: field slope measurements); surrogate shallow tree that reproduces the scores.
- User: road-view labelling is not feasible (little time left). **Decision: Seoul accident hotspots as the label.**

**Design (agreed)**
- Row = one Seoul intersection (`교차로관리번호` group with crosswalks, 7,592 groups; 21,776 crosswalks). Only
  intersections with crosswalks (no Seoul-wide OSM for no-crosswalk intersections).
- y = 1 if a Seoul pedestrian accident hotspot lies within 100 m of the group centroid (50/200 m as sensitivity only).
- X: A parts (support score 0-2, share of crosswalks with pedestrian signal, audible signal under the 15 m assignment
  rule, number of crosswalks); C parts (max stage count 일단1/이단2/삼단3, diagonal crosswalk); B part (60 m grade at the
  intersection from the 5 m contours); controls for exposure (bus stops and Aug-2026 boardings nearby, etc.).
  **Excluded: A's deficiency +1**, because it is built from the same accident hotspots (leakage).
- Models (sklearn only; lightgbm/xgboost/shap are not installed and not needed): main `HistGradientBoostingClassifier`
  (class_weight='balanced'), comparison `RandomForestClassifier`, a depth-3 `DecisionTreeClassifier` for a readable rule
  figure, logistic regression baseline. No monotonic constraints (we want to see the direction, not force it).
- Validation: spatial CV, group K-fold by 자치구 (neighbouring intersections share hotspots, random splits inflate scores).
  Metric: PR-AUC first (rare positives), ROC-AUC too. Interpretation: permutation importance + partial dependence.
- Questions: (1) incremental value — controls-only vs controls + A/B/C parts; (2) importance; (3) direction — does risk
  rise with support score, stage count, grade (support score is expected to come out reversed, as in H3 = reverse
  causation); (4) apply to the 61 route crosswalk points of the two schools, Spearman vs A score; sensitivity 50/200 m.

**What this adds / does not add (to be written on the slides/dashboard too — user decision)**
- Adds: an external evidence check of the indicator parts against observed accident locations; numbers behind design
  decisions (not ordering A by accidents, weighting 이단, keeping slope separate); component importance for team revisions.
- Does not add: proof of validity for blind users (accidents are not blind-specific); causality; any change to the school
  results (A/B/C stay separate, model output is not a new score); edge-level B/C (label is intersection-level).
  The user wants these limits reported as an insight, not hidden.

**Working files**: notebook `트리모델.ipynb` (user-created, empty at start). The user asked that this file
(`codex&claude.md`) be updated continuously while working, without being asked.

### 16.35 Tree-model validation run — results (Claude, 2026-09-25)

**Files**: module `ml_tree_validation.py` (`build_table`, `load_table`, `route_points`, feature lists); notebook
`트리모델.ipynb` (20 cells, runs with 0 errors, ~2 min; generated once by a scratchpad script, edit it directly from now on;
if it is open in VS Code use "Revert File" before saving). Table `data/tree_model/seoul_intersections.csv` (7,592 rows;
building it takes ~4 min because of the slope step), `data/tree_model/route_points_pred.csv`, figures
`figures/tree_model/1_모델비교.png` … `5_통학로_적용.png`.

**Implementation notes**
- Intersection = mean of crosswalk coordinates per `교차로관리번호` (normal-coordinate crosswalks from `h5_master`).
  Support score uses the same rule as `risk_a_crossing.support_score` (mismatch = 2).
- Label uses Seoul rows of the hotspot file (`시도시군구명` starts with 서울). Positives: 50 m 216 (2.8%),
  100 m 553 (7.3%), 200 m 1,049 (13.8%).
- `경사_60m` = max |grade| over four 60 m lines (0/45/90/135 deg) centred on the intersection, `risk_b_slope.interpolate`
  on contour+spot-height samples within 250 m (Seoul-wide contours = 11M vertices, so a global griddata is not used).
  7 NaN (flat Yeouido area etc.).
- Controls: bus stops within 100 m, Aug-2026 daily boardings+alightings within 200 m (ridership file joined on the
  5-digit ARS string — a numeric join silently gave all zeros at first), other intersections within 300 m.
  Subway stations (no coordinates in the folder) and the disability-facility list (mostly apartments/villas = buildings
  subject to the law, not facilities) were left out.
- Spatial CV = GroupKFold(5) by 자치구 (25 districts).

**Results**
- Controls only: ROC-AUC 0.77–0.81, PR-AUC 0.29–0.33 (base 0.073); boardings dominate (permutation importance 0.18,
  bus-stop count 0.04). Adding A/B/C parts: PR-AUC change −0.012 to −0.001 (better in 1/3/3 of 5 folds for HGB/RF/LR),
  ROC-AUC +0.01–0.03. A/B/C parts alone: PR-AUC 0.10–0.14. Same at 50 m and 200 m. Only positive A/B/C importance:
  횡단단수_최대 (0.004).
- Direction (partial dependence, HGB): 보행등_비율 0.16→0.08 (matches A); 지원점수 0/1/2 = 0.10/0.12/0.12 (weak);
  음향 0.105→0.119 (reversed, same reverse causation as H3); 이단 vs 일단 0.14 vs 0.04 (matches C weighting, but 이단 marks
  wide roads with medians, so traffic is mixed in); slope rises to ~5% then falls above 8% (steep = quiet residential
  hills) -> accidents cannot validate B.
- Depth-3 tree: splits on boardings first, then 횡단단수, slope, 보행등_비율; spatial CV ROC 0.79 / PR 0.23.
- Route points (61 crosswalk points): Spearman(support score, prediction) = 0.28 (p=0.028). Spearman with full A = 0.45
  but **contaminated** (A's deficiency +1 comes from the same hotspots) -> reference only. Median Seoul percentile of the
  prediction: Chung-Ang 0.55, Soongsil 0.41 (same direction as A, driven mostly by exposure).
- Conclusion written in notebook §8: accident hotspots cannot validate A/B/C (volume dominates; audible signal and slope
  come out reversed) — this re-confirms the decisions not to order A by accidents and not to combine A/B/C. 보행등 share
  and 이단 give weak external support. Blind-specific validity needs another label (user/expert ratings), not done for time.

**§16.35 update — Notion (2026-09-25):** full process-oriented Korean write-up (why → label options and decision → X/y
form → what it can/cannot add → model choice → data build incl. the ARS join bug → spatial CV and metric meanings →
results with all 5 figures → conclusion → file locations) written to the user's page "트리 모델 이용 방안"
(https://app.notion.com/p/3e6e935a81c9803590f0f3b2cf50484c, DartB 세션 기록(개인) > 개인 기록). Image upload via
`notion-create-file-upload` + curl POST worked this time (the earlier MemcachedCrossCellError did not recur).
Page properties (상태 "시작 전", 날짜 empty) were left for the user.

### 16.36 User proposal: use the tree model's predictions to evaluate the two schools — assessment (2026-09-25)

User's review of the whole project: topic = "시각장애인 입장에서 본 중앙대·숭실대 통학로"; part 1 (route network) done;
part 2 = indicators A/B/C, meant to be generalized with Seoul-wide data ("the larger A/B/C, the more inconvenient for
blind users") and then applied to the two schools. Two possible uses of a tree model: (1) support that generalization,
(2) train on A/B/C features only and use the model's predictions for route points/segments as the school evaluation.
The user preferred (2).
Claude's assessment (not yet decided by the user/team): (2) is not recommended as the conclusion. A prediction is only as
meaningful as its label: trained on accident hotspots, A/B/C-only features are weak (ROC 0.59–0.65) and the model learned
directions opposite to the premise (audible signal -> more hotspots, grade >8% -> fewer), and it predicts "near a general
pedestrian hotspot", not blind-user inconvenience; trained on the A/B/C scores themselves it only reproduces the rules.
Use (1) already ran (§16.35) and showed the generalization does not hold with accident data, so (2) loses its basis.
Recommendation: keep rule-based A/B/C (legal thresholds + nesting logic) for the school evaluation and report the tree
model as "validation attempted, not supported by accident data". Optional reference-only experiment: monotonic constraints
forcing the expected directions (effectively a learned composite of A/B/C — conflicts with the no-composite decision, and
the weights come from confounded accident data). A valid version of (2) needs a blind-user label (user/O&M expert ratings).
Waiting for the user/team decision.

**§16.36 update — search for a blind-user "inconvenient place" label (2026-09-25):** user asked whether data exists that
says where blind people felt inconvenience (not necessarily commute routes). Short web search found no public Seoul
dataset with point-level blind-user inconvenience + coordinates. Candidates: (1) tactile-block/sidewalk complaints
(국민신문고 / 서울시 응답소) — ACRC analysed 2,847 complaints 2018–2020 (damage 1,257, parking/obstruction 603, missing
596, wrong installation 325), published only in aggregate; addresses might be obtainable via an information-disclosure
request (10-day legal deadline, extendable) -> most realistic label; caveats: complaint topics (tactile blocks, parking)
don't match A/B/C inputs (signals, slope, turns, stages), reporting bias (needs exposure control), timeline;
(2) AI Hub 인도 보행 영상 (29 obstacle classes + surface incl. braille blocks) — no GPS/location described, can't map;
(3) KCA 시각장애인 보행 안전실태조사 — tens of sites only; (4) 교통약자 이동편의 실태조사 — region-level;
(5) apps like WalkWith — not public. Proposal to the user: file the disclosure request now (user must do it in their
own name; Claude offered to draft it), finalize school evaluation with rule-based A/B/C meanwhile, add the model if data
arrives in time, otherwise list it as future work. Waiting for the user.

**§16.36 update — Kaggle search (2026-09-25):** no usable label on Kaggle. Found only image datasets for recognition
(Kaggle "보도 장애물 인식 모델" competition — AI Hub-style Korean sidewalk images, no location; obstacles dataset;
Footpath Image Dataset 3k images; crosswalk-dataset; Pedestrian Dataset) and paper datasets (WOTR, SideGuide, GuideTWSI,
TactPav) — none tie a map location to blind-user inconvenience. Closest in form: Project Sidewalk (UW; >1M crowdsourced
GSV labels with lat/lng + severity 1–5, CC0, public API) but no Korean city (Asia: only Chandigarh), wheelchair-oriented
severity, and our Seoul-specific inputs (이단, audible 15 m, 60 m grade) don't exist there -> future-work mention only.
Still recommended: Seoul tactile-block/sidewalk complaint disclosure request. Offered to draft it; waiting for the user.

**§16.36 update — other ways to use the model for the school evaluation (2026-09-25):** proposed to the user:
(1) **school-discrimination tree** (no external label): inputs = A/B/C features of route edges (595) / crossing points
(109), y = Chung-Ang vs Soongsil; the splits and importance show *how* the two routes differ (checks the dashboard reading
"Chung-Ang = crossing burden, Soongsil = terrain + turns"); says "how they differ", not "which is worse" — direction still
comes from the rules. Doable today. (2) **scenario (conjoint-style) survey**: text profiles of A/B/C feature combinations,
blind users / O&M instructors / welfare-centre staff pick the harder one in pairs (Google Form, 10–15 min); train a tree on
the responses and apply it to route edges -> the closest valid form of the user's preferred direction; needs recruitment
(days). Not recommended: LLM/team judgments as labels (circular), installation locations as labels (reverse causation).
Recommendation: do (1) now, (2) if a partner organization can be reached. Waiting for the user.

**§16.36 decision (user, 2026-09-25):** no further tree-model work for now (neither the school-discrimination tree nor the
survey); **next: TTS voice-guidance service**. The tree-model work stays as the "validation of the generalization"
(use (1)) in `트리모델.ipynb`: HGB/RF in §2 (model comparison), HGB in §3 (permutation importance), §4 (partial
dependence), §6 (radius sensitivity), §7 (predictions for the 61 route points, not used as scores); depth-3 decision tree
in §5 (rule figure); logistic regression is only a non-tree baseline.

### 16.37 TTS voice-guidance service — direction (2026-09-25)

User decisions: real-time location-based guidance (phone GPS; announce when approaching a risk point), and use OpenAI
("GPT") TTS for the voice. Claude's proposal (awaiting user confirmation): do NOT call the OpenAI API live from the page —
the dashboard is static on GitHub Pages (key would be exposed; a server would be needed), live calls add latency and cost
per announcement. Instead: guidance sentences are fixed per point (A crossing points 109, B/C edges), so pre-generate the
audio once with OpenAI TTS (mp3, a few hundred short clips, negligible cost) and ship them with the page; the page tracks
GPS and plays the clip when within a trigger radius (~30 m, to tune for 5–20 m urban GPS error, with a no-repeat rule);
fallback = browser Web Speech API reading the same sentence. Accessibility: also put the sentence in an aria-live region
and offer "screen reader vs GPT voice" (blind users often run VoiceOver/TalkBack at high speed). Start with
"근처에 ○○이 있습니다" phrasing (walking direction unknown). State on the page that it is a project demo, not a mobility aid.
Needs an OpenAI API key — user should put it in a local file (e.g. `.env.openai`), not paste it into chat.
Next step once confirmed: draft the per-point guidance sentence list for review.

**§16.37 update — step 1 done: guidance cues and sentences (Claude, 2026-09-25).** User confirmed the proposal
(pre-generated OpenAI TTS + live GPS triggering) and also wants the finished service verified by simulation later.
`tts_guidance.py` -> `data/tts/cues.geojson` (EPSG:4326) + `data/tts/sentences.csv`.
- Cue kinds: 횡단 (A points; text = crosswalk yes/no, signal/audible, "중간 교통섬을 거쳐 두 번에 나누어 건넙니다" for
  이단+, prefix "주의." when A >= 3), 회전 (C sharp-turn locations, same rule as `risk_c_complexity.sharp_turns`, point at
  start + 5 m), 경사 (B 위험 edges merged into connected stretches, line geometry; 8.3–13% "급할 수 있는", 13–20% "가파른",
  >20% "매우 가파른"), 계단 (B stairs flag). Crossing/turn points within 15 m merged into one cue.
- Grade numbers are NOT spoken: first version produced "기울기 약 54퍼센트" etc. (60 m grade error ±4.7 pp, some outliers).
- Result: Soongsil 171 cues (횡단 42, 횡단+회전 2, 회전 74, 경사 50 stretches, 계단 3), Chung-Ang 153 (60/2/54/33/4).
  Only **16 unique sentences** -> 16 audio files. Slope stretches are up to 2.2 km long (announced once on entry).
Next: user reviews sentences; OpenAI key into `.env.openai`; generate mp3; page with GPS trigger; then simulation
(walk origin->gate paths on analysis_edges with GPS noise; measure hit rate, lead distance, false/duplicate announcements).

**§16.37 update — second purpose: low-risk route guidance (user, 2026-09-25).** The service should also guide a blind
user along the route with the lowest risk indicators to the school (using each school's network), not only announce
hazards. Claude's proposal (awaiting user decision):
- Route definition: a single cost would combine A/B/C and conflict with the no-composite decision. Recommended:
  **per-indicator alternative routes** — shortest, fewest risky crossings (A >= 3), shortest B-위험 length, fewest C events
  — each with a length cap (e.g. <= 1.3x shortest); voice describes each and the user chooses. Alternative: user-set
  priority order. Not recommended: fixed weighted sum.
- Network: A/B/C exist only on TMAP-validated `analysis_edges` (315/280 edges, 3/5 components -> many origins would get no
  route). Recommended: recompute A/B/C on the full OSM walk network in the radius (`all_edges`, 1,051/955 edges) with the
  same functions, keeping TMAP-validation as an attribute.
- Consequences: turn-by-turn voice ("50미터 앞에서 오른쪽으로") -> pre-generate OpenAI TTS clips as pieces (directions,
  distance buckets, hazard sentences) and concatenate; along a route the heading is known, so hazards can say "앞에".
  Routing (Dijkstra) runs in the browser on a small JSON graph, so GitHub Pages still works.
- Simulation becomes the main validation: for the 153 existing origins, shortest vs recommended routes (extra distance %
  vs fewer risky crossings / less steep length / fewer events), then the full service with GPS noise.
Planned order: (1) A/B/C on full network, (2) route calculator + route-level simulation, (3) voice clips (needs key),
(4) page (GPS, route choice, turn-by-turn, hazard alerts), (5) end-to-end simulation.

**§16.37 update — route modes decided and step 1–2 done (Claude, 2026-09-25).**
User decision: per-indicator routes with the **user choosing the indicator** — modes 최단 / A only / B only / C only
(never combined). Implementation:
- `risk_a_crossing.load_school/crossing_points` and `risk_c_complexity.score_c` got an optional `layer` argument
  (default `analysis_edges`, so earlier results are unchanged; `all_edges` = full OSM walk network in the radius).
- `route_guidance.py`: `build_network()` computes A/B/C on `all_edges` (single connected component for both schools) ->
  `data/route/{학교}_edges.geojson` + `{학교}_points.csv`. Full network: Soongsil 1,051 edges / 66.6 km, 81 crossing
  points (A 0/1/2/3/4/unknown = 3/2/8/25/2/41), B 위험 45.7% of length, 24 stairs edges, 249 sharp turns; Chung-Ang 955 /
  61.9 km, 111 points (3/5/16/31/12/44), B 위험 35.8%, 21 stairs, 191 turns.
- Mode metrics: A = sum of A scores of crossing nodes passed (unknown -> support score only); B = length of 위험 + stairs
  edges; C = sharp turns + crossing events (stage-weighted). Constrained search: cost = length + λ·metric for
  λ in (0…20000); pick min metric with length <= 1.3 × shortest (tie -> shorter). Destination = any gate of the school
  (gates from `option_a_origins_with_osm_gate.csv`: gate_node + OSM_최근접_문).
- Route-level simulation, 153 origins (`data/route/route_simulation.csv`), mean per route (Soongsil | Chung-Ang):
  shortest 589 m | 600 m. A mode: route changes for 57% | 49% of origins, +6.8% | +7.9% length, A sum 4.29->1.18 |
  9.36->4.47, A>=3 crossings 0.33->0.04 | 2.05->0.88. B mode: changes 34% | 36%, +5.2% | +4.6%, 위험 length
  306->265 m | 227->179 m. C mode: changes 59% | 61%, +8.6% | +8.8%, events 4.72->2.52 | 7.58->4.80.
  Trade-offs exist (e.g. Chung-Ang A mode raises B 위험 length 227->261 m) -> voice should state what each route gives up.
Next: voice clips (OpenAI key needed in `.env.openai`), then the page, then end-to-end GPS-noise simulation.

**§16.37 update — voice clips, engine, simulation (Claude, 2026-09-25).**
- OpenAI key: the user pasted it into chat (advised to rotate it later); saved to `.env.openai` (added to `.gitignore`),
  never printed. First call failed `credit_balance_exhausted`; user bought credits; then OK.
- `tts_clips.py`: 126 clips (hazard sentences in "근처에"/"앞에" versions + distance/direction/status/summary pieces),
  model `gpt-4o-mini-tts`, voice `coral`, Korean instructions -> `dashboard/nav/audio/{key}.mp3` (126 files, 9.1 MB);
  text list `data/tts/clips.json` (also `dashboard/nav/clips.json`). `generate()` only makes missing files.
- `tts_guidance.build(full=True)` -> cues on the full network (`data/tts/cues_full.geojson`, 19 sentences; 3 new vs the
  analysis-network set). `build_nav_data.py` -> `dashboard/nav/data_{soongsil,chungang}.json` (nodes, edges with u->v
  coords, B penalty/grade/stairs/turn positions/hazard key, crossing nodes with A/C and sentence keys, gates, free-walk
  cues, simulation origins).
- `dashboard/nav/nav_engine.js` (UMD, browser + Node): Graph.route (same rules as route_guidance.py — verified on
  153 origins x 4 modes: A/C identical, length diff <= 0.27 m from JSON rounding), plan (maneuvers at nodes: >=25 deg
  slight, >=60 turn, >=150 u-turn; hazards = crossings, slope-run starts, in-edge sharp turns, merged within 15 m),
  summaryKeys (mode, gate, total, extra distance, gain, trade-offs), Navigator (hazard at 30 m ahead, maneuver at 50 m
  and 15 m, off-route = max(30 m, 2.5 x GPS accuracy) for 5 consecutive fixes -> reroute, arrival 15 m, isStale drops
  passed announcements), FreeWalker (cues within 30 m, re-arm after 60 m), walkTrace (1 m/s, AR(1) GPS noise).
  Zero-length routes (origin = gate node, 3 Soongsil origins) handled.
- `dashboard/nav/simulate_nav.js` -> `data/route/nav_simulation.csv` (+ `nav_simulation_summary.csv`): 153 origins x
  4 modes x GPS noise 0/5/10/15 m = 2,448 runs; route summary heard before walking (median 12.9 s); speech length
  0.17 s/char + 0.3 s/clip, sequential playback. First run showed too-sensitive off-route (57%/98% of runs at 10/15 m)
  and long start summaries delaying alerts -> fixed as above. Final (noise 0/5/10/15 m): runs with a false off-route
  0/2.8/14.7/37.9%; maneuvers announced 100/99.6/98.3/97.6%, late <1%; hazards announced 99.8/99.5/97.2/94.9%, late 0%
  (median 24–39 m left when speech ends); arrival detected 99.3/98.0/97.7/96.9% (median 14–35 m before the gate — early
  at high noise); 45.9% of routes start inside a hazard stretch (mostly slope) -> said at start, counted separately.
Next: the page (`dashboard/nav/index.html`), local test, then publishing (ask the user first).

**§16.37 update — voice-guidance page built and tested locally (Claude, 2026-09-25).**
`dashboard/nav/index.html` (+ `nav_engine.js`, `clips.json`, `data_*.json`, `audio/*.mp3`; ~10 MB total), same black
style as the dashboard, Leaflet 1.9.4 + OSM tiles (needs http(s); `file://` will not load the JSON). Controls: school,
route criterion (최단 / A 횡단 / B 경사 / C 판단 — one at a time), destination (nearest gate or a specific gate),
location (virtual walk demo with origin picker/map click, GPS noise 0–20 m, 1–8x speed; or real GPS via
watchPosition), voice (GPT mp3 / browser Web Speech / screen reader only via aria-live), speech rate 0.8–2x;
buttons 안내 시작 / 멈춤 / 경로 없이 주변 위험만 듣기 (FreeWalker). Map shows the chosen route (bold), the other three
criteria (dashed), hazard markers; a table compares the 4 criteria for the current origin; log list of spoken lines.
Audio queue: sequential clips, stale announcements dropped (`nav.isStale`), mp3 failure -> Web Speech, safety timeouts
so a missing `ended` event cannot stall the queue. Test hook: `?demo=A&school=soongsil&speed=8` auto-starts a walk.
Local checks (python -m http.server 8765 + headless Chrome): desktop render OK; demo walk (Chung-Ang, A, 8x) produced
start summary -> maneuvers (50 m / 곧) -> hazards -> arrival "후문에 도착했습니다"; mp3 served as audio/mpeg; mobile width
has no horizontal overflow (headless Chrome's ~500 px minimum window made a 390 px screenshot look cropped).
Not yet done: publishing (ask the user; candidate `kjyilj0707/DartB_TP/commute-voice-nav/`), real-device GPS test,
Notion write-up. The OpenAI key should be rotated by the user (it was pasted in chat).

**§16.37 update — published + Notion (Claude, 2026-09-25).**
- User issued a new OpenAI key (again pasted in chat) -> saved to `.env.openai` (verified 200); old key replaced.
- Published with the user's go-ahead: `kjyilj0707/DartB_TP` commit fe655f3, folder `commute-voice-nav/` (index.html,
  nav_engine.js, clips.json, data_*.json, audio/ 126 mp3, README.md; 9.7 MB). Live:
  https://kjyilj0707.github.io/DartB_TP/commute-voice-nav/ (Korean audio filenames served fine). Headless check on the
  live URL: demo walk `?demo=A&speed=8` runs to "후문에 도착했습니다". The `?demo=` test hook is still in the live page.
  To update: copy `dashboard/nav/*` into the clone (scratchpad; re-clone with `gh repo clone kjyilj0707/DartB_TP`),
  commit, push.
- Notion: process-oriented write-up with 2 screenshots on "tts서비스 만들기"
  (https://app.notion.com/p/3e6e935a81c9809ebd2af0aa082d81aa, DartB 세션 기록(개인) > 개인 기록). Properties left as is.
Open: real-phone GPS test; blind-user usability feedback; dashboard link between the two pages (not added yet).

**§16.37 update — multi-criteria routes (user request, 2026-09-25).** User: keep the current TTS model
(`gpt-4o-mini-tts`; options discussed: pin `gpt-4o-mini-tts-2025-12-15`, `tts-1-hd`, `gpt-audio-1.5`, voice/instruction
tuning, whole-sentence turn clips, silence trimming, earcons — none applied yet). Change: route criteria are now
**checkboxes** (any subset of A/B/C; none = shortest).
- Rule (engine `route`): candidates = shortest paths with cost = length + Σ λ_k·metric_k (single criterion: previous
  LAMBDAS; several: product grid A/C [0,5,20,100,500,5000], B [0,0.5,2,5,20,200]), length <= 1.3 x shortest; choose the
  candidate where **no chosen metric is worse than on the shortest route** and Σ(metric_k / shortest metric_k) is minimal
  (tie -> shorter). Single criterion reproduces route_guidance.py exactly (612/612). Scores are not combined into an index;
  the combination only exists in route choice. Modes are strings "최단","A","B","C","AB","AC","BC","ABC".
- 4 new clips `mode_AB/AC/BC/ABC` generated (OpenAI, new key). Page: checkboxes with ✓ box, "선택: …" live text, combos
  drawn purple (#b79cff), comparison table shows the 4 single criteria + the chosen combination.
- Route effects (`data/route/route_combo_effects.csv`, mean per route): e.g. Chung-Ang AB: +8.2% length, A 9.36->5.81,
  B 227->192 m, C 7.58->5.81; ABC: +8.7%, A 5.35, B 201 m, C 5.12. Soongsil AB: +6.2%, A 4.29->2.16, B 306->264 m.
- Simulation rerun with 8 modes (4,896 runs): noise 0/5/10/15 m -> maneuvers 100/99.7/98.6/97.7%, hazards 99.8/99.5/97.4/
  94.9% (late 0%), false off-route 0/2.6/14.2/38.2%, arrival 99.3/98.0/97.7/96.8%.
- Republished: DartB_TP commit 2a8250e (live checked).

### 16.38 Whole-project overview page on Notion (Claude, 2026-09-25)
User asked for an easy, detailed, process-oriented write-up of everything done in DartB_TOYPROJECT, framed as: topic
"시각장애인 입장에서 본 중앙대·숭실대 통학로" = (1) secure/implement the commute routes (done) + (2) build and evaluate
indicators A/B/C, meant to be generalized with Seoul-wide data and applied to the two schools. Written to the user's
page "TOYPROJECT" (https://app.notion.com/p/3e6e935a81c980d49dbaceb5aa51621f, DartB 세션 기록(개인) > 학습) with 5 figures
(campus definition, TMAP-validated network, A/B/C maps), a mermaid flow, tables and a glossary. Structure: one-glance
callout / how to read / problem and the two big jobs / timeline 9/15–9/25 / part 1 routes (district, OSM network,
TMAP filter, results) / part 2 indicators (data, H5–H8 checks, how A/B/C were chosen incl. H3 reversal, A, B, C, school
results, dashboard) / **how far the "bigger = worse, generalized from Seoul data" premise was actually verified**
(per-indicator basis = law/logic; tree-model result; label search; conclusion) / TTS service / status, limits, next steps
/ plain-language glossary / links and files. Note kept honest: the direction "larger = more inconvenient" is a
rule-based design (legal thresholds + logic), not statistically derived from accident data.

**§16.38 update — page expanded (Claude, 2026-09-25).** User said the overview lacked per-dataset handling/observation/analysis,
the team's Notion pages (TOYPROJECT 방향 정리 및 EDA 3dfe935a…, tp_숭실 3e2e935a…, 가설 검증 3e3e935a…) and the trial-and-error.
Read all three pages + this file and added to the "TOYPROJECT" page: 3-5 (Soongsil per-gate segments), **ch.4 EDA**
(9 datasets table, audible signals codebook comparison, crosswalks, accident hotspots incl. 80 m circular polygons /
five survey editions / casualty composition, slope, facilities / subway voice guides / blind population / vulnerable-
pedestrian points / bus data, Soongsil step-3 attempts ①–⑤, common rules, decisions), **ch.5 hypothesis verification in
detail** (H5 incl. 35.5%→15.2% assignment rule and XGEO 41.2%→51.1%, H8 paused, H7 64 campuses → A/B/C gates → 24 campuses/67
gates, pooled test, side exploration 9-1..9-5, crosswalk-level 3-tier priority 1,141), **ch.9 trial and error** (data,
route building, hypotheses/indicators, tree model, voice service, working method, lessons). Later chapters renumbered:
6 indicators, 7 generalization check, 8 voice service, 10 status, 11 glossary, 12 links. 7 more figures uploaded.

**§16.38 update — Q&A on 3-3/3-4 and definition (Claude + user, 2026-09-25).** User asked what 153 means, what 미관찰 is and how
it arises, whether TMAP lacks those segments. Answers: 153 = number of TMAP route requests (one per sampled origin), not
segments; the routes touched 315 (Soongsil) + 280 (Chung-Ang) = 595 OSM edges (validated + bridged); 미관찰 (736 / 675 edges,
~70% by count, ~66% / ~62% by length) = OSM edges no TMAP route passed — not "non-walkable" and not "absent from TMAP"
(TMAP was asked for routes, not for segment existence); causes: only 153 origins, one route per origin, only the
walking-nearest gate asked (617-call all-gates mode not used), edges off any origin->gate path. User's conclusion (accepted
by Claude with wording fix): no need to restore 미관찰 edges because 통학로 is defined as "OSM edges passed by TMAP-recommended
routes from sampled origins to the nearest gate"; 15 m bridging only reconnects the network. Notion 3-3/3-4 updated with
the definition, the four causes, the three-type meanings and the sample-dependence limitation. Not done: optional TMAP
check of a few 미관찰 edges (would need a stated call count + approval).

**§16.38 update — Q&A on gates vs segments (Claude + user, 2026-09-25).** User asked whether the 3-5 limitation "각 문이 보행자
문인지는 확인하지 못함" contradicts TMAP having verified things, and then clarified it concerns the *gates*, not the segments.
Clarified: (1) **Segments** were verified as walkable to the extent that only OSM edges passed by TMAP pedestrian routes were
kept as 통학로. (2) **Gates** were not verified as pedestrian-accessible: gate coordinates come from OSM (campus-boundary/
path intersections, `data/{soongsil,chungang}_osm_gates.csv`) and were passed to TMAP as destinations (`endX/endY` in
`tmap_commute_pipeline.py`); all 153 requests succeeded and every gate received >= 1 route (Chung-Ang 중문 only 2), which shows
a walking route to the gate coordinate exists on TMAP's map, but not that the gate is open/pedestrian-usable (hours,
vehicle-only, locked). Also: 3 Soongsil origins lie 0–6 m from their gate (little information); Soongsil 후문 differs ~330 m
between Kakao and OSM. Consequence if a gate is not pedestrian-usable: the segments are still valid, but the origin->gate
assignment ("which gate does this route lead to") could be wrong. Planned Notion fix (awaiting the user's go-ahead):
3-5 limitation reworded as "구간은 TMAP으로 확인, 문은 미확인 (문 좌표까지 TMAP 경로가 도착했으므로 걸어서 접근하는 길이 있다는
것만 확인, 실제 개방·보행자 사용 여부는 현장·공식 안내로 확인 필요)", and 3-3 gets one line about it.

### 16.39 Tree-model follow-up: logistic check, per-indicator insights, Notion realigned (Claude, 2026-09-26)

**Q&A first (no code change).** (1) User asked whether "sharp change in slope" (not slope itself) is reflected. Answer: **no**. The original B-2
"급변" (10 m pieces, crossing the 5.6% / 8.3% legal thresholds between neighbours) was dropped from the final B because 10 m slopes have
about +-28 %p error (contour interval 5 m, RMSE 1.98 m). Final B = max absolute slope over >= 60 m base lengths (+-4.7 %p). `score_edges`
in `risk_b_slope.py` still computes `B2_급변` but `score_b` does not call it. `ml_tree_validation.add_slope` is also absolute slope (4 directions
through the intersection centre). Note the old B-2 meant "crossing a legal threshold", which is not the same as "slope changes sharply";
the slope is also unsigned (no uphill/downhill), so direction changes cannot be seen. (2) User asked for A/B/C-only prediction without
walking volume. Already in `트리모델.ipynb` cell 8 (input "A·B·C만", all three ctrl variables removed): PR-AUC / ROC-AUC = HistGB 0.105 / 0.594,
RF 0.110 / 0.627, logistic 0.135 / 0.646 (baseline 0.073 / 0.5). Accuracy was not used (7.3% positives -> all-zero guess = 92.7%).

**Model choice discussion.** Recommended logistic regression as the main model for *direction/size of effects* (highest scores: with ctrl+ABC
PR 0.330 / ROC 0.822; ctrl-only 0.331 / 0.814; simplest; coefficients readable) and tree models as the check for non-linear elements (slope).
Caveats: fold spread is large (logistic PR-AUC 0.204-0.385, RF 0.203-0.343), so model differences are not conclusive. The notebook's main model
is still HistGB (permutation importance, PDP); the Notion page says "direction/size from logistic coefficients, non-linear elements from trees"
without declaring one winner.

**Run added to `트리모델.ipynb` as section 9 (cells 21-24; original 21 cells untouched, backup in the session scratchpad
`트리모델_backup_before_sec9.ipynb`).** New figure `figures/tree_model/5_로지스틱_계수.png`.
- 9-1 log1p(승하차_200m) for logistic only (trees are invariant to monotone transforms). ctrl-only PR/ROC 0.331/0.814 -> 0.338/0.817;
  ctrl+ABC 0.330/0.822 -> 0.323/0.823. Adding A·B·C: PR-AUC diff -0.001 (raw) / -0.015 (log), ROC-AUC diff +0.008 / +0.006.
  Conclusion unchanged; log transform is not needed.
- 9-2 standardized logistic coefficients (log version, 5-fold sign consistency): log승하차 +2.018 (OR 7.5), 횡단단수 +0.245, 횡단보도수 +0.234,
  정류소수 +0.216, 교차로수 +0.025 (sign in 4/5 folds only), 음향 +0.052, 지원점수 -0.073, 대각선 -0.088, 경사 -0.214, 보행등 -0.316.
  Direction vs indicator expectation: 보행등 (match), 이단 (match), 음향 (opposite, reverse causality), 경사 (opposite), 지원점수 (opposite
  but **not interpreted**: Spearman -0.84 with 보행등_비율, collinearity). Correction to an earlier statement: logistic did not show "no
  slope effect"; it gave a negative coefficient (the falling part above ~8% dominates).
- Interpretation text is in notebook cell 24 (markdown). Not done: slope entered as bins, other walking-volume proxies (no subway coordinates in folder).

**Notion "TOYPROJECT" page (3e7e935a81c98126a294ed5ab03fe160) updated.** Section 7-2 rewritten as 7-2-1 (why tree model), 7-2-2 (what was used
and why, table), 7-2-3 (results: performance table incl. logistic + log, direction table), 7-2-4 (insights per A/B/C, common conclusion,
limits, files). Then aligned: ch.2 timeline (new 9/26 row), 5-3 (H2 conclusion cites logistic -0.214), 7-4 (per-indicator scope + robustness),
9-4 (3 new rows: 지원점수 collinearity, logistic slope sign, 승하차 skew), 9-6 (new lesson), 10 (status row, 2 limits, B-2 note; a 'tree-model reinforcement' next-step bullet was added and then removed at the user's request),
11 glossary (로지스틱 회귀, ROC-AUC·PR-AUC, 통제 변수, 공선성). Verified by re-fetch + diff: only intended lines changed.
Per-indicator insight (A: 보행등 supports, 음향 reverse causality, order stays logic-based; B: opposite direction, justified only by law
(walking burden), not by accident data; C: 이단 weight has weak external support, confounded by wide roads).
**Not done / open:** the Colab link "트리 모델로 A·B·C 검증" in ch.12 may be an older version without section 9 (unchecked); Notion 12 unchanged.

**§16.39 update — slope-segmentation limit and legal basis stressed on Notion (Claude + user, 2026-09-26).** User asked to (a) stress that the
originally planned slope segmentation could not be done because of a clear limit, and (b) make the legal basis of B (why slope reflects walking
difficulty) credible. Interpretation used: "slope segmentation" = the original 10 m pieces + B-2 sharp change (6-3 memo: "경사가 높았다가 낮아지는
급격한 변화"), which `risk_b_slope.py` docstring already says was dropped "for data-resolution limits". The earlier Notion sentence "reason not in the
work record" was therefore wrong and was replaced. The model-side "slope bins" check was never a recorded plan (it was proposed by Claude and
its next-step bullet was removed at the user's request); it is only written as a limit.
Notion changes: 6-5 got two callouts — blue "왜 법 기준인가" (no self-made thresholds; 시행규칙 [별표 1] 1/18 and 1/12 map to 양호 / 주의(exception
allowed only when terrain makes it hard) / 위험(not allowed even as exception); thresholds are written in law, not fitted to data; error shown via
dotted line + "확실히 위험" 13%; scope: a mobility-impairment access-road standard, not a visually-impaired-specific one, so it does not prove
that exceeding it burdens blind pedestrians) and orange "10 m 구간화·B-2를 못 한 한계" (5 m contours + spot heights -> RMSE 1.98 m -> +-28 %p on 10 m
pieces, ~10x the 2.7 %p gap between 5.6% and 8.3%; 74-86% "위험", slope > 100%; national DEM is 90 m; 60 m gives +-4.7 %p but averages away short
steep parts, so precision and sharp-change detection cannot be had together; even at 60 m the error exceeds the width of the 주의 band). Also
updated: 5-3 (B-2 line), 7-1 (B basis cites 별표 1), 7-2-4 (B row cells and the slope-limit bullet), ch.10 limits (B resolution + law scope).
Verified by re-fetch + diff (9 lines removed, 29 added, all intended).

### 16.40 Road-class check of the slope reversal: exclude "car roads" (OSM highway class) and re-test (Claude, 2026-09-26)

**Teammate's hypothesis.** "Steeper slope -> lower hotspot probability" may be because accidents mostly occur on car roads and car roads are flat.
If true: (1) hotspots concentrate on car roads, (2) car-road intersections are flatter, (3) controlling for / excluding car roads should weaken
or flip the slope effect. User asked to exclude car roads by OSM road class and re-verify.

**Method / code.** New module `ml_road_class.py`: downloads Seoul OSM ways with highway in motorway/trunk/primary/secondary/tertiary (+_link) from Overpass
(3x3 tiles, 20,702 ways, cached in `data/tree_model/osm_roads_major_seoul.gpkg`), assigns each intersection the highest class within R m of its centre
(1 간선 = motorway/trunk/primary/secondary, 2 보조간선 = tertiary, 3 그 밖; base R = 30 m, sensitivity 20/50 m). residential and below were NOT
downloaded (size), so "그 밖" = no major/tertiary road nearby. Table with classes: `data/tree_model/seoul_intersections_roadclass.csv`.
Unit of exclusion = intersection (not segment). Run in `트리모델.ipynb` section 10 (cells 25-30; earlier 25 cells untouched; backups in scratchpad
`트리모델_backup_before_sec10.ipynb`); figure `figures/tree_model/6_차도제외_경사_오즈비.png`. Statsmodels logit with district-clustered SE.
Interaction test and sensitivity analyses were added AFTER seeing the first results (exploratory) — stated in the notebook.

**Results.** (1) Premise 1 holds: hotspot-near rate 간선 9.5% (447/4711) > 보조간선 4.2% > 그 밖 2.6%; 400 of 693 Seoul hotspots lie within 30 m of a 간선.
(2) Premise 2 weak: median slope 간선 2.96 / 보조간선 2.23 / 그 밖 3.18 % (Kruskal p=1.4e-15 but 간선 is not the flattest). (3) Slope OR per 1 SD:
all 0.80 (p=.016); +road-class control 0.805 (p=.015, coefficient -0.222 -> -0.217); 간선 only 0.76 (p=.014); 간선 excluded 0.89 (95% CI 0.70-1.15, p=.38,
106 positives). Interaction slope x 간선 = -0.201, CI [-0.49, +0.09], p=.18. Sensitivity (radius 20/50 m; drop hotspots on 간선 from the label): -0.121 / -0.097 / -0.057,
all n.s.; sign never flips to positive. Slope bins (간선 excluded): <=2% 3.8, 2-5.6% 4.8, 5.6-8.3% 2.6, >8.3% 2.3 — same rise-then-fall shape.
Spatial CV on 간선-excluded set (n=2,881; base PR 0.037): ctrl -> ctrl+ABC PR-AUC HistGB .169->.163, RF .190->.229, logistic .208->.219; no consistent gain, folds very noisy;
ABC-only PR .05-.08, ROC .55-.62.
**Conclusion.** Hypothesis only partially supported: premise 1 yes, premise 2 weak; excluding 간선 weakens the slope effect to non-significance, which does not
contradict it, but the class control leaves the coefficient unchanged, the sign does not flip, and the 간선-vs-other difference is not established (low power) ->
cannot conclude "car roads caused the reversal", nor rule it out. In no subset does "steeper -> more hotspot" appear, so "B cannot be justified by accident
data" (7-4) stands. The earlier explanation "steep = residential hill roads" is not explained by road class alone (same direction inside 간선 intersections).
**Not done:** Notion not yet updated for this (5-3, 7-2, 7-4, 9-4, 10 would need it); residential-and-below road classes; road width/lane/traffic data.

### 16.41 Re-test without car roads: do steeper places have MORE accidents? (area level infeasible; hotspot-site level) (Claude, 2026-09-26)

User asked to re-verify, excluding car roads, whether accidents are more frequent in steeper places. §16.40 had used "intersection has a hotspot within 100 m
(yes/no)". This time: (a) area (250 m grid) level, (b) hotspot-site level with accident size as outcome. Notebook `트리모델.ipynb` section 11 (cells 31-36; earlier 31
cells untouched; backup `트리모델_backup_before_sec11.ipynb` in scratchpad), figure `figures/tree_model/7_사고다발지_경사_사고규모.png`.

**Findings.** (a) Area level cannot exclude car roads: of 627 hotspot records that fall in intersection-containing 250 m cells, 589 (94%) are in cells crossed by a 간선;
cells with only 보조간선 or none hold 32 + 6 records. (b) **The 693 Seoul "hotspots" are records, not places, and `지점코드` is NOT a place ID** — it is a per-district
sequence number (same code -> coordinates differ by median 1.8 km, max 7.3 km, different place names across editions). Grouping by coordinates within 30 m gives
**516 places** (384 appear once, 97 twice, 28 thrice, 4 four times, 3 five times); no same-edition merges up to 30 m (10 m: 623, 50 m: 430, 100 m: 338 with 9 merges).
Do not use `지점코드` for de-duplication. (Mid-session I first mis-grouped by 지점코드 and got "212 sites" — wrong, retracted; results from that and from the raw 693
records — pseudo-replicated, e.g. non-arterial Poisson ratio 0.74, p=0.006 — were discarded.) (c) Site level (30 m), slope = same 60 m 4-direction max as intersections,
Poisson on 총사고건수 (sum of edition counts) with 승하차/정류소/교차로 밀도 controls, district-clustered SE: ratio per 1 SD slope — all 0.94 (p=.035), 간선 위 (299) 0.95 (p=.15),
간선 아님 (217) 0.94 (95% CI 0.87-1.02, p=.11), with road-class control 0.944. Spearman (간선 아님): 총사고건수 -0.13 (p=.049), 총중상자 -0.15 (p=.024); 판본수 -0.04 (ns), 사망발생 +0.01 (ns).
Sensitivity to grouping distance (간선 아님): 10 m 0.952 (p=.040), 30 m 0.938 (p=.114), 50 m 0.879 (p=.012); ratio is always <= 1, p ranges .01-.11 (not robust).
**Conclusion.** No evidence that steeper places have more accidents after excluding car roads; weak/no negative relation in both "hotspot present" (§16.40) and "hotspot size" (this section).
7-4 stands (accident data cannot justify B). Limits: hotspots are pre-selected (>= 7 accidents, size range 7-22), OSM class only, residential-and-below missing,
site definition/30 m are choices, n=217, exploratory multiple looks.
**Not done:** Notion not updated. Notion 4-4 states "지점코드 788종이라 같은 지점이 판본마다 다시 나옴" — for Seoul, 지점코드 is not a place ID (see above), so that sentence
and the "693곳 = 693개 기록" wording should be corrected (Seoul: ~516 places by 30 m coordinates). 5-3, 7-2, 7-4, 9-4, ch.10 also pending.

**§16.41 update — Notion reflected (Claude, 2026-09-26).** Added 7-2-5 "팀원 의견 검증 — 차도를 제외하면 경사 방향이 바뀌는가" (callout, method, result table, conclusion, cautions) to the
"TOYPROJECT" Notion page and aligned: ch.2 timeline (9/26 row), 4-4 (지점코드 is not a place ID; Seoul ~516 places by 30 m coordinates), 5-3 (the "주거지 언덕길" explanation
is unconfirmed), 7-2-3 slope row, 7-4 (new bullet), ch.10 (status row, H2 re-run bullet). First batch failed with a validation error because the page had been edited
by someone else in the meantime (in 7-2-3 slope row someone appended "→ 차도 데이터 때문." and bolded some 6-5 bullets); nothing had been applied, so I re-sent after
checking the diff, kept their edits, and only appended "(팀원 의견. 차도를 제외해 검증했으나 확정하지 못함, 7-2-5)" after their note. Verified by re-fetch + diff.
**§16.41 update #2 — wording (2026-09-26).** The "→ 차도 데이터 때문." note in 7-2-3's slope row was the user's own edit. User asked to drop the assertive wording: it was a
question ("차도 데이터 때문이 아닐까?") that motivated the check. Row now reads "→ 차도 데이터 때문이 아닐까? 라는 의문으로 차도를 제외해 검증했으나 확정하지 못함(7-2-5)".
(Earlier note above calling it someone else's edit was wrong: it was the user's.)
**§16.41 update #3 — wording unified (2026-09-26).** Per user: everywhere on the Notion page the car-road check is now framed as starting from a question
("차도 데이터 때문이 아닐까?"), not as a "team member's opinion": ch.2 9/26 row, 7-2-5 heading/callout/premise bullet, 7-4 bullet, ch.10 status row (and the 7-2-3 slope row from update #2).
**§16.41 update #4 — Notion 6-5 tidy (2026-09-26).** User had bolded four 6-5 bullets (처음 설계 / 비현실적 / 원인 확인 / DEM 90 m; wording unchanged). Option A applied at the user's request:
removed the orange callout's items that duplicated them (원래 계획, 못 한 이유, 대안 자료), kept the non-duplicated point as one line ("오차가 법 기준선 간격보다 큼": +-28 %p is ~10x the 2.7 %p gap
between 5.6% and 8.3%), plus the 60 m trade-off / 결정 / B가 못 보는 것 items; the "최종" bullet is now fully bold like the others.
**§16.41 update #5 — full-page review of the Notion page and fixes (2026-09-26).** Read the whole page (ch.0-12). Fixed (verified by re-fetch + diff, 12 changed spots):
ch.10 H2 re-run bullet (my earlier wording "사고 건수 자체로 다시 확정하는 작업은 남아 있음" was wrong: section 11 already used 총사고건수; what remains is re-applying H2's original method:
elevation-point slope rate + negative binomial, to Seoul records); 9-4 row about logistic slope (removed my own "예상했는데"); 7-2-5 method list (①② -> (가)(나)) and a note that "차도" here = 간선/보조간선 only
(6-4/9-3 use "차도" = residential and above + alley); 5-3 callout and 9-1 H2 row (Seoul recompute now exists, original method rerun still pending); 5-3 awkward sentence; 7-2-3 slope row ("…주거지 언덕길로 추정");
"693곳" -> "기록 693개" in 4-1, 4-7 title, 5-9 step 1, 6-1. NOT done (left as minor): empty last row in the 6-4 A-score table; inconsistent "세 번 같은 방향" counting (5-3 vs 7-2-4);
glossary lacks "OSM 도로 등급"/"군집 표준오차"; ch.12 file list lacks `ml_road_class.py`; ch.12 Colab link possibly outdated (not opened).
