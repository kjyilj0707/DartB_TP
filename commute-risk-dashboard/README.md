# 통학로 보행 위험 지도 (Commute risk dashboard)

중앙대·숭실대 통학로를 시각장애인 보행 관점에서 세 가지 기준으로 평가한 대시보드입니다.

- A 횡단 위험: 교차 지점의 횡단 지원 수준(보행등·음향신호기) + 주변 위험 대비 횡단보도 부족도, 0~4점
- B 경사 위험: 60m 기준 최대 경사, 양호 ≤5.6% / 주의 ≤8.3% / 위험 >8.3%
- C 인지 복잡성: 횡단(이단 2) + 10m 안 45° 이상 급한 방향 전환, 1km당 이벤트 수

페이지: https://kjyilj0707.github.io/DartB_TP/commute-risk-dashboard/

지도: Leaflet + OpenStreetMap (© OpenStreetMap contributors). `index.html` 한 파일에 데이터가 들어 있으며,
원본 분석 프로젝트의 `dashboard/build_dashboard.py`로 다시 만든다.
