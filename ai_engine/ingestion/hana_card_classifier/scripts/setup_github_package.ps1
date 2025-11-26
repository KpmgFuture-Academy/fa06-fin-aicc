# ============================================================
# Hana_Card_GitHub 패키지 생성 스크립트 (PowerShell)
# ============================================================
#
# 사용법:
#   cd C:\Users\Admin\workplace\Final_Project\Hana_Card_GitHub\scripts
#   .\setup_github_package.ps1
#
# ============================================================

$ErrorActionPreference = "Stop"

# 경로 설정
$SOURCE_DIR = "C:\Users\Admin\workplace\Final_Project\Hana_Card"
$TARGET_DIR = "C:\Users\Admin\workplace\Final_Project\Hana_Card_GitHub"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Hana_Card_GitHub 패키지 생성 스크립트" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Source: $SOURCE_DIR" -ForegroundColor Yellow
Write-Host "Target: $TARGET_DIR" -ForegroundColor Yellow
Write-Host ""

# ============================================================
# 1. 폴더 구조 생성
# ============================================================
Write-Host "[1/4] 폴더 구조 생성 중..." -ForegroundColor Green

$folders = @(
    "$TARGET_DIR\nlu_category",
    "$TARGET_DIR\nlu_category\utils",
    "$TARGET_DIR\nlu_category\docs",
    "$TARGET_DIR\examples",
    "$TARGET_DIR\scripts"
)

foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        Write-Host "  Created: $folder" -ForegroundColor Gray
    }
}

# ============================================================
# 2. nlu_category 핵심 파일 복사
# ============================================================
Write-Host "[2/4] nlu_category 파일 복사 중..." -ForegroundColor Green

$nlu_files = @(
    "__init__.py",
    "types.py",
    "state.py",
    "config.py",
    "prompts.py",
    "nodes_preprocess.py",
    "nodes_category.py",
    "nodes_confidence.py",
    "nodes_rag.py",
    "nodes_llm.py",
    "model_service_electra.py",
    "conversation_utils.py",
    "llm_clarify.py",
    "llm_refine.py",
    "graph_builder.py"
)

foreach ($file in $nlu_files) {
    $src = "$SOURCE_DIR\nlu_category\$file"
    $dst = "$TARGET_DIR\nlu_category\$file"
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "  Copied: nlu_category\$file" -ForegroundColor Gray
    } else {
        Write-Host "  [SKIP] Not found: $src" -ForegroundColor Yellow
    }
}

# ============================================================
# 3. examples 파일 복사
# ============================================================
Write-Host "[3/4] examples 파일 복사 중..." -ForegroundColor Green

$example_files = @(
    "test_llm_refine_pipeline.py"
)

foreach ($file in $example_files) {
    $src = "$SOURCE_DIR\examples\$file"
    $dst = "$TARGET_DIR\examples\$file"
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "  Copied: examples\$file" -ForegroundColor Gray
    } else {
        Write-Host "  [SKIP] Not found: $src" -ForegroundColor Yellow
    }
}

# test_queries.txt 복사 (루트로)
$src_queries = "$SOURCE_DIR\nlu_category\test_samples\test_queries.txt"
$dst_queries = "$TARGET_DIR\test_queries.txt"
if (Test-Path $src_queries) {
    Copy-Item -Path $src_queries -Destination $dst_queries -Force
    Write-Host "  Copied: test_queries.txt (to root)" -ForegroundColor Gray
}

# ============================================================
# 4. 완료 메시지
# ============================================================
Write-Host ""
Write-Host "[4/4] 복사 완료!" -ForegroundColor Green
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  다음 파일들은 수동으로 확인/생성해주세요:" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  - README.md (이미 생성됨)" -ForegroundColor Gray
Write-Host "  - requirements.txt (이미 생성됨)" -ForegroundColor Gray
Write-Host "  - .gitignore (이미 생성됨)" -ForegroundColor Gray
Write-Host "  - nlu_category/utils/logger.py (이미 생성됨)" -ForegroundColor Gray
Write-Host "  - nlu_category/utils/text_normalizer.py (이미 생성됨)" -ForegroundColor Gray
Write-Host "  - nlu_category/docs/pipeline_overview.md (이미 생성됨)" -ForegroundColor Gray
Write-Host "  - examples/test_clarify_only.py (이미 생성됨)" -ForegroundColor Gray
Write-Host "  - examples/test_refine_only.py (이미 생성됨)" -ForegroundColor Gray
Write-Host ""
Write-Host "총 복사된 파일: $($nlu_files.Count + $example_files.Count + 1)개" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
