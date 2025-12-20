from pathlib import Path

from pydub import AudioSegment

# 스크립트 위치 기준 경로 설정
BASE_DIR = Path(__file__).parent
SOURCE_DIR = BASE_DIR / "raw_files2"        # 원본 m4a
OUTPUT_DIR = BASE_DIR / "converted_wav"    # 변환된 wav

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

files = sorted(SOURCE_DIR.glob("*.m4a"))
total_count = len(files)

print(f"🔍 입력 폴더: {SOURCE_DIR}")
print(f"💾 출력 폴더: {OUTPUT_DIR}")
print(f"총 {total_count}개의 m4a 파일을 변환합니다.")
print("-" * 50)

if total_count == 0:
    print("변환할 m4a 파일이 없습니다. SOURCE_DIR을 확인하세요.")
else:
    for idx, input_path in enumerate(files, 1):
        new_file_name = input_path.stem + ".wav"
        output_path = OUTPUT_DIR / new_file_name
        try:
            sound = AudioSegment.from_file(input_path, format="m4a")
            sound = sound.set_frame_rate(16000).set_channels(1)
            sound.export(output_path, format="wav")
            print(f"[{idx}/{total_count}] 변환 완료: {input_path.name} -> {new_file_name}")
        except Exception as e:
            print(f"[{idx}/{total_count}] 변환 실패 ({input_path.name}): {e}")

print("-" * 50)
print("변환 작업이 완료되었습니다.")
