"""
카드사 E2E 테스트용 음성 파일 생성 스크립트

100개의 대화 시나리오 텍스트를 Google TTS로 변환하여 WAV/MP3 파일로 저장합니다.

사용법:
    python -m e2e_evaluation_pipeline.scripts.generate_audio_from_scenarios

    # 또는 직접 실행
    python e2e_evaluation_pipeline/scripts/generate_audio_from_scenarios.py

옵션:
    --format: 출력 포맷 (wav, mp3) - 기본값: wav
    --output-dir: 출력 디렉토리 - 기본값: e2e_evaluation_pipeline/datasets/card_e2e_test/audio
    --scenario-file: 시나리오 JSON 파일 경로
    --limit: 생성할 최대 파일 수 (테스트용)
    --dry-run: 실제 TTS 호출 없이 테스트
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def load_scenarios(scenario_file: Path) -> list[dict]:
    """시나리오 JSON 파일을 로드합니다."""
    with open(scenario_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("test_scenarios", [])


def get_tts_service():
    """TTS 서비스 인스턴스를 반환합니다."""
    try:
        from app.services.voice.tts_service_google import AICCGoogleTTSService
        return AICCGoogleTTSService.get_instance()
    except Exception as e:
        logger.error(f"Google TTS 초기화 실패: {e}")
        logger.info("OpenAI TTS로 폴백합니다...")
        try:
            from app.services.voice.tts_service import AICCTTSService
            return AICCTTSService.get_instance()
        except Exception as e2:
            logger.error(f"OpenAI TTS도 초기화 실패: {e2}")
            raise RuntimeError("TTS 서비스를 초기화할 수 없습니다. API 키를 확인하세요.")


def generate_audio_files(
    scenarios: list[dict],
    output_dir: Path,
    audio_format: str = "wav",
    limit: Optional[int] = None,
    dry_run: bool = False
) -> dict:
    """시나리오 텍스트를 음성 파일로 변환합니다.

    Args:
        scenarios: 시나리오 리스트
        output_dir: 출력 디렉토리
        audio_format: 출력 포맷 (wav, mp3)
        limit: 생성할 최대 파일 수
        dry_run: True면 실제 TTS 호출 없이 테스트

    Returns:
        생성 결과 통계
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if not dry_run:
        tts_service = get_tts_service()

    results = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
        "generated_files": []
    }

    scenarios_to_process = scenarios[:limit] if limit else scenarios
    total = len(scenarios_to_process)

    logger.info(f"총 {total}개 시나리오 처리 시작...")
    logger.info(f"출력 디렉토리: {output_dir}")
    logger.info(f"출력 포맷: {audio_format}")

    for idx, scenario in enumerate(scenarios_to_process, 1):
        scenario_id = scenario.get("scenario_id", f"unknown_{idx}")
        user_text = scenario.get("user_text", "")
        category = scenario.get("category", "unknown")

        if not user_text:
            logger.warning(f"[{idx}/{total}] {scenario_id}: 텍스트 없음, 건너뜀")
            results["skipped"] += 1
            continue

        # 카테고리별 서브 디렉토리 생성
        category_dir = output_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)

        # 출력 파일 경로
        output_file = category_dir / f"{scenario_id}.{audio_format}"

        # 이미 존재하면 건너뛰기 (옵션)
        if output_file.exists():
            logger.info(f"[{idx}/{total}] {scenario_id}: 이미 존재함, 건너뜀")
            results["skipped"] += 1
            results["generated_files"].append(str(output_file))
            continue

        results["total"] += 1

        if dry_run:
            logger.info(f"[{idx}/{total}] {scenario_id}: (DRY RUN) '{user_text[:30]}...'")
            results["success"] += 1
            results["generated_files"].append(str(output_file))
            continue

        try:
            logger.info(f"[{idx}/{total}] {scenario_id}: TTS 변환 중... '{user_text[:30]}...'")

            # TTS 변환
            start_time = time.time()
            audio_bytes = tts_service.synthesize(
                text=user_text,
                format=audio_format
            )
            elapsed = time.time() - start_time

            # 파일 저장
            output_file.write_bytes(audio_bytes)

            file_size_kb = len(audio_bytes) / 1024
            logger.info(
                f"[{idx}/{total}] {scenario_id}: 완료 "
                f"({file_size_kb:.1f}KB, {elapsed:.2f}초)"
            )

            results["success"] += 1
            results["generated_files"].append(str(output_file))

            # API 호출 간 짧은 대기 (rate limit 방지)
            time.sleep(0.2)

        except Exception as e:
            logger.error(f"[{idx}/{total}] {scenario_id}: 실패 - {e}")
            results["failed"] += 1
            results["errors"].append({
                "scenario_id": scenario_id,
                "error": str(e)
            })

    return results


def update_scenarios_with_audio_paths(
    scenario_file: Path,
    output_dir: Path,
    audio_format: str = "wav"
) -> None:
    """시나리오 JSON에 audio_file 경로를 추가합니다."""
    with open(scenario_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenarios = data.get("test_scenarios", [])

    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id", "")
        category = scenario.get("category", "unknown")

        # 상대 경로로 audio_file 설정
        audio_path = f"audio/{category}/{scenario_id}.{audio_format}"
        scenario["audio_file"] = audio_path

    # 업데이트된 JSON 저장
    output_file = scenario_file.parent / f"{scenario_file.stem}_with_audio.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"업데이트된 시나리오 저장: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="카드사 E2E 테스트용 음성 파일 생성"
    )
    parser.add_argument(
        "--format",
        choices=["wav", "mp3"],
        default="wav",
        help="출력 포맷 (기본값: wav)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="출력 디렉토리"
    )
    parser.add_argument(
        "--scenario-file",
        type=Path,
        default=None,
        help="시나리오 JSON 파일 경로"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="생성할 최대 파일 수 (테스트용)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 TTS 호출 없이 테스트"
    )
    parser.add_argument(
        "--update-json",
        action="store_true",
        help="시나리오 JSON에 audio_file 경로 추가"
    )

    args = parser.parse_args()

    # 기본 경로 설정
    base_dir = PROJECT_ROOT / "e2e_evaluation_pipeline" / "datasets" / "card_e2e_test"

    scenario_file = args.scenario_file or (base_dir / "card_100_scenarios.json")
    output_dir = args.output_dir or (base_dir / "audio")

    if not scenario_file.exists():
        logger.error(f"시나리오 파일을 찾을 수 없습니다: {scenario_file}")
        sys.exit(1)

    # 시나리오 로드
    scenarios = load_scenarios(scenario_file)
    logger.info(f"로드된 시나리오: {len(scenarios)}개")

    # 음성 파일 생성
    results = generate_audio_files(
        scenarios=scenarios,
        output_dir=output_dir,
        audio_format=args.format,
        limit=args.limit,
        dry_run=args.dry_run
    )

    # 결과 출력
    print("\n" + "=" * 60)
    print("음성 파일 생성 결과")
    print("=" * 60)
    print(f"총 처리: {results['total']}개")
    print(f"성공: {results['success']}개")
    print(f"실패: {results['failed']}개")
    print(f"건너뜀: {results['skipped']}개")

    if results["errors"]:
        print("\n오류 목록:")
        for err in results["errors"][:10]:  # 최대 10개만 출력
            print(f"  - {err['scenario_id']}: {err['error']}")
        if len(results["errors"]) > 10:
            print(f"  ... 외 {len(results['errors']) - 10}개")

    print(f"\n출력 디렉토리: {output_dir}")

    # 시나리오 JSON 업데이트 (선택)
    if args.update_json and results["success"] > 0:
        update_scenarios_with_audio_paths(
            scenario_file=scenario_file,
            output_dir=output_dir,
            audio_format=args.format
        )

    # 성공률 확인
    if results["total"] > 0:
        success_rate = results["success"] / results["total"] * 100
        print(f"\n성공률: {success_rate:.1f}%")

        if success_rate < 95:
            logger.warning("성공률이 95% 미만입니다. 오류를 확인하세요.")
            sys.exit(1)

    print("\n완료!")


if __name__ == "__main__":
    main()
