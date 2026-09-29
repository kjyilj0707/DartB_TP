"""음성 안내 조각 목록과 OpenAI TTS 생성 (codex&claude.md §16.37).

페이지는 조각을 이어 붙여 말한다(예: "d_50" + "turn_right" = "50미터 앞에서 / 오른쪽으로 도세요").
mp3가 없으면 페이지가 같은 문장을 브라우저 내장 음성(Web Speech API)으로 읽는다.
키는 .env.openai(OPENAI_API_KEY=...)에서 읽고, 화면에 출력하지 않는다.
"""
import hashlib
import json
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
AUDIO_DIR = ROOT / "dashboard" / "nav" / "audio"
CLIPS_JSON = ROOT / "data" / "tts" / "clips.json"
MODEL = "gpt-4o-mini-tts"
VOICE = "coral"
INSTRUCTIONS = "한국어 보행 안내 음성입니다. 또렷하고 차분하게, 약간 빠른 속도로 말하세요."
GATES = ["정문", "후문", "남문", "북문", "중문"]
KOR_COUNT = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟"}
DIST_STEPS = [10, 20, 30, 50, 100, 150, 200, 300]
TOTAL_STEPS = list(range(100, 2100, 100))
EXTRA_STEPS = [10, 20, 30, 50, 100, 150, 200, 300, 400, 500]
GAIN_B_STEPS = [50, 100, 150, 200, 300, 400, 500]


def hazard_key(text):
    return "haz_" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def ahead_version(text):
    """경로를 따라갈 때는 걷는 방향을 알므로 '근처에'를 '앞에'로 바꾼다."""
    return text.replace("근처에", "앞에")


def library():
    clips = {}
    texts = pd.concat([pd.read_csv(ROOT / "data" / "tts" / f, encoding="utf-8-sig")["text"]
                       for f in ("sentences.csv", "sentences_full.csv")]).drop_duplicates()
    for t in texts:
        for v in (t, ahead_version(t)):
            clips[hazard_key(v)] = v
    clips["d_soon"] = "곧"
    for d in DIST_STEPS:
        clips[f"d_{d}"] = f"{d}미터 앞에서"
    clips.update({
        "turn_right": "오른쪽으로 도세요.",
        "turn_left": "왼쪽으로 도세요.",
        "slight_right": "오른쪽으로 조금 틀어 가세요.",
        "slight_left": "왼쪽으로 조금 틀어 가세요.",
        "straight": "계속 직진하세요.",
        "uturn": "뒤로 돌아서 가세요.",
        "start": "경로 안내를 시작합니다.",
        "offroute": "경로를 벗어났습니다. 경로를 다시 찾습니다.",
        "locating": "현재 위치를 찾고 있습니다.",
        "low_accuracy": "위치 정확도가 낮습니다. 안내가 늦을 수 있습니다.",
        "outside": "현재 위치가 안내할 수 있는 지역 밖입니다.",
        "mode_최단": "최단 경로입니다.",
        "mode_A": "횡단 위험이 가장 적은 경로입니다.",
        "mode_B": "경사 위험이 가장 적은 경로입니다.",
        "mode_C": "방향 전환과 횡단이 가장 적은 경로입니다.",
        "mode_AB": "횡단 위험과 경사를 함께 줄인 경로입니다.",
        "mode_AC": "횡단 위험과 판단할 곳을 함께 줄인 경로입니다.",
        "mode_BC": "경사와 판단할 곳을 함께 줄인 경로입니다.",
        "mode_ABC": "횡단 위험, 경사, 판단할 곳을 모두 줄인 경로입니다.",
        "same_as_shortest": "이 기준으로는 최단 경로가 가장 좋습니다.",
        "gainA_score": "횡단 위험 점수가 낮아집니다.",
        "trade_A": "대신 위험한 횡단이 조금 더 많습니다.",
        "trade_B": "대신 경사 구간이 조금 더 깁니다.",
        "trade_C": "대신 방향 전환이나 횡단이 조금 더 많습니다.",
    })
    for g in GATES:
        clips[f"dest_{g}"] = f"목적지는 {g}입니다."
        clips[f"arrive_{g}"] = f"{g}에 도착했습니다. 안내를 마칩니다."
    for n in TOTAL_STEPS:
        clips[f"total_{n}"] = f"총 거리 약 {n}미터입니다."
    for n in EXTRA_STEPS:
        clips[f"extra_{n}"] = f"최단 경로보다 약 {n}미터 더 걷습니다."
    for k, w in KOR_COUNT.items():
        clips[f"gainA_{k}"] = f"위험도가 높은 횡단이 {w} 곳 줄어듭니다."
        clips[f"gainC_{k}"] = f"판단할 곳이 {w} 곳 줄어듭니다."
    for n in GAIN_B_STEPS:
        clips[f"gainB_{n}"] = f"경사 위험 구간이 약 {n}미터 줄어듭니다."
    return clips


def save_library():
    clips = library()
    CLIPS_JSON.parent.mkdir(parents=True, exist_ok=True)
    CLIPS_JSON.write_text(json.dumps(clips, ensure_ascii=False, indent=1), encoding="utf-8")
    return clips


def _key():
    for line in (ROOT / ".env.openai").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(".env.openai에 OPENAI_API_KEY가 없음")


def generate(overwrite=False, limit=None):
    """없는 mp3만 만든다. 반환: (만든 수, 실패 목록)."""
    clips = save_library()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    key, made, failed = _key(), 0, []
    for k, text in list(clips.items())[:limit]:
        path = AUDIO_DIR / f"{k}.mp3"
        if path.exists() and not overwrite:
            continue
        r = requests.post("https://api.openai.com/v1/audio/speech",
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": MODEL, "voice": VOICE, "input": text,
                                "instructions": INSTRUCTIONS, "response_format": "mp3"},
                          timeout=60)
        if r.status_code != 200:
            failed.append((k, r.status_code, r.json().get("error", {}).get("code")))
            if r.status_code in (401, 429):
                break
            continue
        path.write_bytes(r.content)
        made += 1
    return made, failed
