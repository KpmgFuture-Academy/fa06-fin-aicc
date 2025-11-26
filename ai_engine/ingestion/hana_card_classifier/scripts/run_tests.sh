#!/bin/bash
# ============================================================
# Hana_Card NLU Pipeline 테스트 실행 스크립트 (Linux/Mac)
# ============================================================
#
# 사용법:
#   cd /path/to/Hana_Card_GitHub
#   chmod +x scripts/run_tests.sh
#   ./scripts/run_tests.sh [옵션]
#
# 옵션:
#   --real-api    실제 Claude API 사용 (기본: Mock)
#   -v            상세 로그 출력
#
# ============================================================

set -e

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  Hana_Card NLU Pipeline Test Runner${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# 프로젝트 루트로 이동
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Python 확인
echo -e "${GREEN}[1/3] Python 환경 확인 중...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python3가 설치되어 있지 않습니다.${NC}"
    exit 1
fi
python3 --version
echo ""

# 의존성 확인
echo -e "${GREEN}[2/3] 의존성 확인 중...${NC}"
python3 -c "import torch; import transformers; print('  - PyTorch:', torch.__version__); print('  - Transformers:', transformers.__version__)" || {
    echo -e "${YELLOW}[WARNING] 일부 의존성이 누락되었습니다.${NC}"
    echo "          pip install -r requirements.txt 를 실행해주세요."
}
echo ""

# 테스트 실행
echo -e "${GREEN}[3/3] 테스트 실행 중...${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

python3 -m examples.test_llm_refine_pipeline "$@"

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  테스트 완료${NC}"
echo -e "${CYAN}============================================================${NC}"
