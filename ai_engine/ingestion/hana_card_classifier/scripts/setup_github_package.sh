#!/bin/bash
# ============================================================
# Hana_Card_GitHub 패키지 생성 스크립트 (Bash)
# ============================================================
#
# 사용법:
#   cd /path/to/Final_Project/Hana_Card_GitHub/scripts
#   chmod +x setup_github_package.sh
#   ./setup_github_package.sh
#
# ============================================================

set -e

# 경로 설정 (사용자 환경에 맞게 수정)
SOURCE_DIR="${SOURCE_DIR:-../Hana_Card}"
TARGET_DIR="${TARGET_DIR:-../Hana_Card_GitHub}"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  Hana_Card_GitHub 패키지 생성 스크립트${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""
echo -e "${YELLOW}Source: $SOURCE_DIR${NC}"
echo -e "${YELLOW}Target: $TARGET_DIR${NC}"
echo ""

# ============================================================
# 1. 폴더 구조 생성
# ============================================================
echo -e "${GREEN}[1/4] 폴더 구조 생성 중...${NC}"

mkdir -p "$TARGET_DIR/nlu_category"
mkdir -p "$TARGET_DIR/nlu_category/utils"
mkdir -p "$TARGET_DIR/nlu_category/docs"
mkdir -p "$TARGET_DIR/examples"
mkdir -p "$TARGET_DIR/scripts"

echo "  Created: nlu_category/"
echo "  Created: nlu_category/utils/"
echo "  Created: nlu_category/docs/"
echo "  Created: examples/"
echo "  Created: scripts/"

# ============================================================
# 2. nlu_category 핵심 파일 복사
# ============================================================
echo -e "${GREEN}[2/4] nlu_category 파일 복사 중...${NC}"

NLU_FILES=(
    "__init__.py"
    "types.py"
    "state.py"
    "config.py"
    "prompts.py"
    "nodes_preprocess.py"
    "nodes_category.py"
    "nodes_confidence.py"
    "nodes_rag.py"
    "nodes_llm.py"
    "model_service_electra.py"
    "conversation_utils.py"
    "llm_clarify.py"
    "llm_refine.py"
    "graph_builder.py"
)

for file in "${NLU_FILES[@]}"; do
    src="$SOURCE_DIR/nlu_category/$file"
    dst="$TARGET_DIR/nlu_category/$file"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        echo "  Copied: nlu_category/$file"
    else
        echo -e "  ${YELLOW}[SKIP] Not found: $src${NC}"
    fi
done

# ============================================================
# 3. examples 파일 복사
# ============================================================
echo -e "${GREEN}[3/4] examples 파일 복사 중...${NC}"

EXAMPLE_FILES=(
    "test_llm_refine_pipeline.py"
)

for file in "${EXAMPLE_FILES[@]}"; do
    src="$SOURCE_DIR/examples/$file"
    dst="$TARGET_DIR/examples/$file"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        echo "  Copied: examples/$file"
    else
        echo -e "  ${YELLOW}[SKIP] Not found: $src${NC}"
    fi
done

# test_queries.txt 복사 (루트로)
src_queries="$SOURCE_DIR/nlu_category/test_samples/test_queries.txt"
dst_queries="$TARGET_DIR/test_queries.txt"
if [ -f "$src_queries" ]; then
    cp "$src_queries" "$dst_queries"
    echo "  Copied: test_queries.txt (to root)"
fi

# ============================================================
# 4. 완료 메시지
# ============================================================
echo ""
echo -e "${GREEN}[4/4] 복사 완료!${NC}"
echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${YELLOW}  다음 파일들은 수동으로 확인/생성해주세요:${NC}"
echo -e "${CYAN}============================================================${NC}"
echo "  - README.md (이미 생성됨)"
echo "  - requirements.txt (이미 생성됨)"
echo "  - .gitignore (이미 생성됨)"
echo "  - nlu_category/utils/logger.py (이미 생성됨)"
echo "  - nlu_category/utils/text_normalizer.py (이미 생성됨)"
echo "  - nlu_category/docs/pipeline_overview.md (이미 생성됨)"
echo "  - examples/test_clarify_only.py (이미 생성됨)"
echo "  - examples/test_refine_only.py (이미 생성됨)"
echo ""
total_files=$((${#NLU_FILES[@]} + ${#EXAMPLE_FILES[@]} + 1))
echo -e "${CYAN}총 복사된 파일: ${total_files}개${NC}"
echo -e "${CYAN}============================================================${NC}"
