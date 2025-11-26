@echo off
REM ============================================================
REM Hana_Card NLU Pipeline 테스트 실행 스크립트 (Windows)
REM ============================================================
REM
REM 사용법:
REM   cd C:\Users\Admin\workplace\Final_Project\Hana_Card_GitHub
REM   scripts\run_tests.bat [옵션]
REM
REM 옵션:
REM   --real-api    실제 Claude API 사용 (기본: Mock)
REM   -v            상세 로그 출력
REM
REM ============================================================

setlocal enabledelayedexpansion

echo ============================================================
echo   Hana_Card NLU Pipeline Test Runner
echo ============================================================
echo.

REM 프로젝트 루트로 이동
cd /d "%~dp0\.."

REM Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python이 설치되어 있지 않습니다.
    exit /b 1
)

echo [1/3] Python 환경 확인 완료
echo.

REM 의존성 확인
echo [2/3] 의존성 확인 중...
python -c "import torch; import transformers; print('  - PyTorch:', torch.__version__); print('  - Transformers:', transformers.__version__)"
if errorlevel 1 (
    echo [WARNING] 일부 의존성이 누락되었습니다.
    echo           pip install -r requirements.txt 를 실행해주세요.
)
echo.

REM 테스트 실행
echo [3/3] 테스트 실행 중...
echo ============================================================
echo.

python -m examples.test_llm_refine_pipeline %*

echo.
echo ============================================================
echo   테스트 완료
echo ============================================================

endlocal
