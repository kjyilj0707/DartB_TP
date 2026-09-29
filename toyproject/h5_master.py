"""H5 (버스정류장 50m 이내 횡단보도 vs 음향신호기 설치율)용 횡단보도 마스터 표.

08_서울전체_가설검증_방향.ipynb 1절의 마스터 표 규칙을 구현한다. 검정은 하지 않고, 그룹과 음향신호기 매칭 여부만 만든다.
좌표 기준: 거리 계산은 EPSG:5186(m). 버스정류소 위치정보는 WGS84 경위도이므로 5186으로 변환한다.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / 'data'
PROJ = 'EPSG:5186'

CROSS_CSV = PROJECT_DIR / '서울시_교차로_및_횡단보도_시설위치정보_20260824.csv'
AUD_CSV = PROJECT_DIR / '음향신호기_현황.csv'
BUS_CSV = PROJECT_DIR / '서울시버스정류소위치정보(20260902).csv'
MASTER_CSV = DATA_DIR / 'h5' / 'crosswalk_master.csv'
AUD_XLS_GLOB = 'A073_P_음향신호기_현황/**/*.xls'   # XGEO에 좌표 문자열이 들어 있는 원본 xls
XGEO_CACHE = DATA_DIR / 'h5' / 'aud_xgeo_coords.csv'
_XGEO_PAT = re.compile(r'SDO_POINT_TYPE\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)')

BUS_GROUP_M = (30, 50, 100)          # 50m가 기본, 30·100m는 민감도
SIGNAL_MATCH_M = (10, 15, 20, 30)    # 15m가 기본(06 3-4-1의 임시 기준), 나머지는 민감도
WRONG_POSITION_M = 1000              # 같은 교차로 중심에서 이만큼 떨어진 횡단보도는 위치 오류(06 clean-cross와 같은 규칙)


def _read_csv(path, **kw):
    for enc in ('utf-8-sig', 'cp949'):
        try:
            return pd.read_csv(path, encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    raise ValueError(f'인코딩을 읽지 못함: {path}')


def load_crosswalks():
    """횡단보도. 좌표 결측·위치 이상 행은 x, y를 비우고 좌표상태로 표시한다(행은 삭제하지 않는다)."""
    c = _read_csv(CROSS_CSV)
    c['x'] = pd.to_numeric(c['X좌표'], errors='coerce')
    c['y'] = pd.to_numeric(c['Y좌표'], errors='coerce')
    has_xy = c[['x', 'y']].notna().all(axis=1)
    med = c.groupby('교차로관리번호')[['x', 'y']].transform('median')
    dist = np.hypot(c['x'] - med['x'], c['y'] - med['y'])
    wrong = dist > WRONG_POSITION_M
    c['좌표상태'] = np.select([~has_xy, wrong], ['결측', '위치이상'], default='정상')
    c.loc[c['좌표상태'] != '정상', ['x', 'y']] = np.nan
    return c


def load_xgeo_coords(refresh=False):
    """원본 shapefile 폴더의 .xls에서 XGEO(오라클 SDO_GEOMETRY 문자열)의 점 좌표를 뽑는다.

    CSV·shp의 XGEO는 `oracle.sql.STRUCT@...` 같은 객체 참조 문자열이라 좌표가 없다. .xls에는 21,451행 모두 좌표가 들어 있다.
    좌표값은 XCE/YCE와 같은 좌표계(EPSG:5186)로 보인다. 문자열의 SRID 2093 표기와는 다르다(XCE와 값이 같은 행이 대부분).
    읽는 데 몇 초 걸려서 data/h5/aud_xgeo_coords.csv에 저장해 두고 다음부터는 그 파일을 쓴다.
    """
    if XGEO_CACHE.exists() and not refresh:
        return pd.read_csv(XGEO_CACHE, dtype={'MGRNU': str}, encoding='utf-8-sig')
    f = next(PROJECT_DIR.glob(AUD_XLS_GLOB))
    x = pd.read_excel(f, dtype=str, usecols=['MGRNU', 'XGEO'])
    xy = x['XGEO'].str.extract(_XGEO_PAT).astype(float)
    out = pd.DataFrame({'MGRNU': x['MGRNU'], 'xgeo_x': xy[0], 'xgeo_y': xy[1]})
    XGEO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(XGEO_CACHE, index=False, encoding='utf-8-sig')
    return out


def load_audible(use_xgeo=True):
    """음향신호기. XCE·YCE를 우선 쓰고, 이 좌표가 빈 행만 XGEO 좌표로 채운다(use_xgeo=True).

    좌표출처: 'XCE'(원래 좌표), 'XGEO복원'(XCE가 비어 XGEO로 채움), '없음'(둘 다 없음, 위치 모름).
    XCE와 XGEO가 둘 다 있는 행은 좌표를 바꾸지 않고 두 값의 차이만 `좌표차이_m`에 남긴다.
    """
    a = _read_csv(AUD_CSV, low_memory=False)
    a['x'] = pd.to_numeric(a['XCE'], errors='coerce')
    a['y'] = pd.to_numeric(a['YCE'], errors='coerce')
    a['좌표출처'] = np.where(a[['x', 'y']].isna().any(axis=1), '없음', 'XCE')
    if use_xgeo:
        g = load_xgeo_coords()
        a = a.merge(g, on='MGRNU', how='left')
        a['좌표차이_m'] = np.hypot(a['x'] - a['xgeo_x'], a['y'] - a['xgeo_y'])
        fill = (a['좌표출처'] == '없음') & a[['xgeo_x', 'xgeo_y']].notna().all(axis=1)
        a.loc[fill, 'x'] = a.loc[fill, 'xgeo_x']
        a.loc[fill, 'y'] = a.loc[fill, 'xgeo_y']
        a.loc[fill, '좌표출처'] = 'XGEO복원'
    a['좌표결측'] = a[['x', 'y']].isna().any(axis=1)
    return a


def load_bus_stops():
    """버스정류소 위치정보. 한강선착장 8개는 도로 정류장이 아니라 제외한다. 좌표는 5186으로 변환."""
    b = _read_csv(BUS_CSV, dtype=str)
    b = b[b['정류소타입'] != '한강선착장'].copy()
    t = Transformer.from_crs('EPSG:4326', PROJ, always_xy=True)
    b['x'], b['y'] = t.transform(b['X좌표'].astype(float).values, b['Y좌표'].astype(float).values)
    return b.reset_index(drop=True)


def build_master(use_xgeo=True):
    """횡단보도 1행 = 1개. 그룹(정류장 근처)과 음향신호기 매칭 여부를 붙인다."""
    c = load_crosswalks()
    a = load_audible(use_xgeo=use_xgeo)
    b = load_bus_stops()

    ok = c['좌표상태'] == '정상'
    cxy = c.loc[ok, ['x', 'y']].to_numpy()
    m = c.copy()

    # 버스정류소
    bt = cKDTree(b[['x', 'y']].to_numpy())
    d, i = bt.query(cxy)
    m.loc[ok, '최근접정류소_m'] = d
    m.loc[ok, '최근접정류소_유형'] = b['정류소타입'].to_numpy()[i]
    m.loc[ok, '정류소수_50m'] = [len(v) for v in bt.query_ball_point(cxy, 50)]
    for r in BUS_GROUP_M:
        m[f'정류장근처_{r}m'] = np.where(ok, m['최근접정류소_m'] <= r, np.nan)
    # 마을버스를 뺀 민감도용(주 분석은 마을버스 포함)
    nb = b[b['정류소타입'] != '마을버스']
    d2, _ = cKDTree(nb[['x', 'y']].to_numpy()).query(cxy)
    m.loc[ok, '최근접정류소_마을버스제외_m'] = d2
    m['정류장근처_50m_마을버스제외'] = np.where(ok, m['최근접정류소_마을버스제외_m'] <= 50, np.nan)

    # 음향신호기 (좌표 있는 신호기만)
    aa = a[~a['좌표결측']]
    axy = aa[['x', 'y']].to_numpy()
    ct = cKDTree(cxy)
    # (1) 단순 규칙: 횡단보도에서 가장 가까운 신호기까지 거리 (06 3-4-1과 같은 방식)
    ad = cKDTree(axy)
    m.loc[ok, '음향신호기_최근접_m'] = ad.query(cxy)[0]
    # (2) 배정 규칙: 신호기를 가장 가까운 횡단보도 하나에만 배정
    sd, si = ct.query(axy)
    assigned = pd.DataFrame({'pos': si, 'd': sd})
    cnt = {r: assigned[assigned['d'] <= r].groupby('pos').size() for r in SIGNAL_MATCH_M}
    pos_of_ok = np.flatnonzero(ok.to_numpy())
    for r in SIGNAL_MATCH_M:
        n = cnt[r].reindex(range(len(cxy)), fill_value=0).to_numpy()
        m.loc[ok, f'배정신호기수_{r}m'] = n
        m[f'음향_배정_{r}m'] = np.where(ok, m[f'배정신호기수_{r}m'] > 0, np.nan)
        m[f'음향_단순_{r}m'] = np.where(ok, m['음향신호기_최근접_m'] <= r, np.nan)
    m = m.drop(columns=['X좌표', 'Y좌표'])
    return m, a, b


def save_master(m):
    MASTER_CSV.parent.mkdir(parents=True, exist_ok=True)
    m.to_csv(MASTER_CSV, index=False, encoding='utf-8-sig')
    return MASTER_CSV
