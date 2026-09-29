# DartB TOYPROJECT — 시각장애인 보행 접근성 (중앙대·숭실대 통학로)

시각장애인 입장에서 본 **중앙대·숭실대 통학로**를 서울시 공공데이터로 분석한 프로젝트의 코드·노트북·결과물 모음.
저장소 루트의 `index.html`, `commute-risk-dashboard/`, `commute-voice-nav/`는 이 프로젝트 결과를 GitHub Pages로 공개한 것이다.

- 위험도 대시보드: https://kjyilj0707.github.io/DartB_TP/commute-risk-dashboard/
- 음성 안내 데모: https://kjyilj0707.github.io/DartB_TP/commute-voice-nav/

## 프로젝트 흐름

| 단계 | 내용 | 코드 / 노트북 |
|---|---|---|
| 0. 구상·데이터 조사 | 아이디어 평가, 공공데이터·OSM 실측 | `docs/accessibility_project_plan.md` |
| 1. 인프라 수집 | 카카오 로컬 API로 POI 수집 | `collect_infra_places.py`, `01_인프라_수집.ipynb`, `docs/step1_*.md` |
| 2. 보행망 스냅 | osmnx 보행 그래프 + POI를 노드에 스냅 | `snap_infra_to_network.py`, `02_도로망_스냅.ipynb`, `docs/step2_*.md` |
| 3. 구간 정의 | "인프라 쌍"이 아니라 "그래프 edge에 점수" 방식으로 결정 | `docs/step3_구간_정의_결정.md`, `통학로규정.ipynb` |
| 4. 경사도 결합 | 등고선·표고점 보간 → edge 경사 | `compute_edge_slope.py`, `04_경사도_결합.ipynb`, `docs/step4_*.md` |
| 5. 보조데이터 EDA | 음향신호기·편의시설·사고다발지·횡단보도 | `05_보조데이터_EDA.ipynb`, `06_숭실대_반경_1-3단계.ipynb` |
| 6. 서울 전체 가설검증 | H5(정류장 근처 음향신호기), H7(대학 출입문 간 격차) 등 | `08_서울전체_가설검증_방향.ipynb`, `09_H5_버스정류장_그룹_결과.ipynb`, `h5_master.py`, `h7_gate_signal.py` |
| 7. 통학로 네트워크 | 대학 반경·출입문·TMAP 검증으로 통학로 edge 확정 | `soongsil_*.py`, `chungang_*.py`, `tmap_commute_pipeline.py`, `osm_tmap_edge_filter.py`, `통학로_최종지도_공유.ipynb` |
| 8. 위험도 지표 A/B/C | A 횡단, B 경사, C 인지복잡성 (합산하지 않고 따로 표시) | `위험도지표 생성.ipynb`, `risk_a_crossing.py`, `risk_b_slope.py`, `risk_c_complexity.py` |
| 9. 트리모델 검증 | 사고다발지를 라벨로 지표 검증 (지표를 뒷받침하지 못함) | `트리모델.ipynb`, `ml_tree_validation.py`, `ml_road_class.py` |
| 10. 대시보드·음성안내 | 지도 대시보드, TTS 경로 안내 | `dashboard/`, `build_accessibility_dashboard.py`, `route_guidance.py`, `tts_*.py`, `build_nav_data.py` |

## 폴더 구조

```
toyproject/
├── docs/            프로젝트 구상, 단계별 설명, 작업 인수인계 기록(codex&claude.md)
├── *.ipynb          분석 노트북 (번호 순서대로 읽기)
├── *.py             파이프라인·분석 모듈 (노트북이 import)
├── data/            중간·최종 산출물 (그래프, 지표, 가설검증 결과, h7 출입문 감사 자료)
├── figures/         시각화 결과 (h5, h7, risk_index, tree_model, 통학로 지도 등)
├── dashboard/       대시보드 빌드 스크립트·템플릿·음성안내 서브앱 (오디오는 commute-voice-nav/에 있음)
├── *.csv            원본 공공데이터 중 용량이 작은 것
└── 보행_접근성_안전_대시보드.html   초기 버전 대시보드
```

노트북과 스크립트는 **이 폴더를 작업 디렉터리로 두고** 상대경로로 파일을 읽는다.

## 저장소에 넣지 않은 것

| 항목 | 이유 / 구하는 곳 |
|---|---|
| `서울시_경사도_등고선.csv`(416MB), `서울시_경사도/` shapefile | GitHub 100MB 제한. 공공데이터포털 "서울특별시_경사도" (수치지형도 등고선·표고, EPSG:5174) |
| `A073_P_음향신호기_현황/` 원본 shapefile·xls | 용량. 서울 열린데이터광장 음향신호기 현황. 좌표 복원용 XGEO는 `data/h5/aud_xgeo_coords.csv`에 결과 저장 |
| API 키(`.env`, `.env.tmap`, `.env.openai`) | 비밀값. `.env.example` 참고해서 `KAKAO_REST_API_KEY`, `TMAP_APP_KEY` 등을 직접 설정 |
| 캐시·`__pycache__`, `제출자료/`(중복본), 카카오 요청 캐시 | 재생성 가능하거나 중복 |

## 주요 결과 요약

- **H5**: 정류장 근처 횡단보도에 음향신호기가 더 많다는 가설 — 표본이 커서 p는 작지만 효과크기 ≤ 0.03이고 50 m/30 m에서 방향이 뒤집힘 → 일관된 효과 없음.
- **H7**: 같은 학교 출입문 간 신호기 수 격차는 우연 이상(균등 기준). 다만 주변 횡단보도 수 기준으로는 우연과 구분되지 않음 → 설치 편향이 아니라 인프라 분포 차이.
- **위험도 A/B/C**: 중앙대는 횡단 부담(A, C의 횡단), 숭실대는 지형(B)·꺾임(C의 회전) 쪽이 큼. 학교 간 A 점수 차이는 유의하지 않음(Mann-Whitney p=0.27).
- **트리모델 검증**: 승하차(보행량)가 압도적, A/B/C 추가 시 PR-AUC 개선 없음. 사고다발지로는 A/B/C를 검증할 수 없다는 결론.

한계와 결정 이유는 `docs/codex&claude.md`(§16.32 종합, §16.35–16.41 검증)에 자세히 있다.
