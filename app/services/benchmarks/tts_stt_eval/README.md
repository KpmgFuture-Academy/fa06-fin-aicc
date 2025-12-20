# TTS/STT 벤치

## 준비
- Python 가상환경에서 requirements 설치: pip install -r requirements.txt
- env: OPENAI_API_KEY, (HUME_API_KEY/HUME_VOICE_ID), (GOOGLE_APPLICATION_CREDENTIALS)
- Zonos는 로컬 모델, speaker audio: app/services/Zonos/assets/exampleaudio.mp3

## TTS 역전사 평가
python run_tts_eval.py --sentences sentences_ko.txt --engines humelo,google,zonos --out-dir outputs --csv tts_eval_results.csv

## STT 평가
준비: manifest.csv (path,text)
python run_stt_eval.py --manifest manifest.csv --out stt_eval_results.csv
