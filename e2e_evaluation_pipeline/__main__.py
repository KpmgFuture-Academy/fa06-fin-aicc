"""
E2E Evaluation Pipeline - Main Entry Point
===========================================

실행 예시:
    python -m e2e_evaluation_pipeline --mode full
    python -m e2e_evaluation_pipeline --mode quick
    python -m e2e_evaluation_pipeline --module stt
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from e2e_evaluation_pipeline.configs.config import EvaluationConfig, EvaluationMode
from e2e_evaluation_pipeline.runners.e2e_runner import E2EEvaluationRunner
from e2e_evaluation_pipeline.runners.module_runner import ModuleEvaluationRunner
from e2e_evaluation_pipeline.reports.report_generator import HTMLReportGenerator, JSONReportGenerator
from e2e_evaluation_pipeline.datasets.data_loader import DataLoader


def main():
    parser = argparse.ArgumentParser(
        description="AICC E2E Evaluation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 전체 평가 실행
    python -m e2e_evaluation_pipeline --mode full

    # 빠른 평가 (샘플링)
    python -m e2e_evaluation_pipeline --mode quick

    # 특정 모듈만 평가
    python -m e2e_evaluation_pipeline --module stt
    python -m e2e_evaluation_pipeline --module intent
    python -m e2e_evaluation_pipeline --module rag

    # CI/CD 모드 (P0 메트릭만)
    python -m e2e_evaluation_pipeline --mode ci

    # 리포트 형식 지정
    python -m e2e_evaluation_pipeline --mode full --report html json
        """
    )

    parser.add_argument(
        "--mode",
        choices=["full", "quick", "ci"],
        default="quick",
        help="평가 모드 (default: quick)"
    )

    parser.add_argument(
        "--module",
        choices=["stt", "tts", "intent", "rag", "slot_filling", "summary", "flow", "e2e"],
        help="특정 모듈만 평가"
    )

    parser.add_argument(
        "--report",
        nargs="+",
        choices=["html", "json", "md"],
        default=["html", "json"],
        help="리포트 형식 (default: html json)"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports",
        help="리포트 출력 디렉토리 (default: reports)"
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        help="테스트 데이터 디렉토리"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 출력"
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  KPMG 6기 2팀 - AICC E2E Evaluation Pipeline")
    print("=" * 60 + "\n")

    # 데이터 로더 초기화
    data_dir = Path(args.data_dir) if args.data_dir else None
    loader = DataLoader(data_dir)

    output_dir = Path(args.output_dir)

    if args.module:
        # 단일 모듈 평가
        print(f"Running {args.module.upper()} module evaluation...")

        # TTS는 별도 처리 (ModuleEvaluationRunner를 사용하지 않음)
        if args.module == "tts":
            from e2e_evaluation_pipeline.datasets.data_loader import get_sample_tts_data
            from e2e_evaluation_pipeline.adapters.tts_adapter import TTSAdapter

            test_texts = get_sample_tts_data()
            adapter = TTSAdapter(use_google=True)

            print(f"\nEvaluating {len(test_texts)} TTS samples...\n")

            # TTS 배치 평가 실행
            eval_result = adapter.evaluate_batch(test_texts)

            print("=" * 50)
            print("  TTS Evaluation Results")
            print("=" * 50)
            print(f"  Samples: {eval_result['count']}")
            print(f"  Success Rate: {eval_result['success_rate'] * 100:.1f}%")
            print(f"  Avg Synthesis Time: {eval_result['avg_synthesis_time_ms']:.1f}ms")
            print(f"  Avg Audio Size: {eval_result['avg_audio_size_bytes']:.0f} bytes")
            print(f"  Avg Chars/Second: {eval_result['avg_chars_per_second']:.1f}")
            print("=" * 50)

            # P0 기준: 성공률 95% 이상, 평균 합성 시간 2000ms 이하
            p0_passed = eval_result['success_rate'] >= 0.95 and eval_result['avg_synthesis_time_ms'] <= 2000
            print(f"\n  P0 Status: {'PASSED' if p0_passed else 'FAILED'}")
            print(f"    - Success Rate >= 95%: {'YES' if eval_result['success_rate'] >= 0.95 else 'NO'}")
            print(f"    - Avg Time <= 2000ms: {'YES' if eval_result['avg_synthesis_time_ms'] <= 2000 else 'NO'}")

            return  # TTS는 별도 처리 후 종료

        config = EvaluationConfig.for_module(args.module)
        runner = ModuleEvaluationRunner(args.module, config)

        # 모듈별 데이터 로드
        if args.module == "stt":
            from e2e_evaluation_pipeline.datasets.data_loader import get_sample_stt_pairs
            test_data = get_sample_stt_pairs()
        elif args.module == "intent":
            from e2e_evaluation_pipeline.datasets.data_loader import get_sample_intent_data
            test_data = get_sample_intent_data()
        elif args.module == "slot_filling":
            from e2e_evaluation_pipeline.datasets.data_loader import get_sample_slot_data
            test_data = get_sample_slot_data()
        elif args.module == "summary":
            from e2e_evaluation_pipeline.datasets.data_loader import get_sample_summary_data
            test_data = get_sample_summary_data()
        elif args.module == "flow":
            from e2e_evaluation_pipeline.datasets.data_loader import get_sample_flow_data
            test_data = get_sample_flow_data()
        else:
            test_data = loader.load_all().get(args.module, {})

        result = runner.run(test_data)

        print(f"\nModule: {args.module.upper()}")
        print(f"Passed: {'YES' if result.overall_passed else 'NO'}")
        print(f"P0 Passed: {'YES' if result.p0_passed else 'NO'}")

    else:
        # 전체 평가
        mode_map = {
            "full": EvaluationMode.FULL,
            "quick": EvaluationMode.QUICK,
            "ci": EvaluationMode.CI
        }

        mode = mode_map[args.mode]
        print(f"Running {args.mode.upper()} evaluation...")

        config = EvaluationConfig(mode=mode)
        runner = E2EEvaluationRunner(config)

        # 샘플 데이터로 평가
        test_data = loader.load_all()
        result = runner.run(test_data)

        # 리포트 생성
        for report_type in args.report:
            if report_type == "html":
                generator = HTMLReportGenerator(output_dir)
                report_path = generator.save_report(result)
                print(f"HTML Report: {report_path}")
            elif report_type == "json":
                generator = JSONReportGenerator(output_dir)
                report_path = generator.save_report(result)
                print(f"JSON Report: {report_path}")

        # 결과 요약
        print("\n" + "=" * 60)
        print("  Evaluation Summary")
        print("=" * 60)
        print(f"  Overall Status: {'PASSED' if result.overall_passed else 'FAILED'}")
        print(f"  P0 Status: {'PASSED' if result.p0_passed else 'FAILED'}")
        print(f"  Duration: {result.total_duration_seconds:.2f}s")

        stats = result.summary.get("overall_stats", {})
        print(f"\n  Metrics: {stats.get('passed_metrics', 0)}/{stats.get('total_metrics', 0)} passed")
        print(f"  Pass Rate: {stats.get('pass_rate', 0):.1f}%")
        print(f"  P0 Metrics: {stats.get('p0_passed', 0)}/{stats.get('p0_total', 0)} passed")
        print("=" * 60 + "\n")

        # CI/CD 모드에서 P0 실패 시 exit code 1
        if args.mode == "ci" and not result.p0_passed:
            print("CI/CD: P0 metrics failed!")
            sys.exit(1)


if __name__ == "__main__":
    main()
