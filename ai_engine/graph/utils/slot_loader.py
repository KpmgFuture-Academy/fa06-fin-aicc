# ai_engine/graph/utils/slot_loader.py
"""도메인/카테고리별 슬롯 정의를 로드하는 유틸리티

slot_definitions.json: 도메인 → 카테고리 → 필수/선택 슬롯 매핑
slot_metadata.json: 슬롯별 라벨, 질문, 검증 규칙
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 설정 파일 경로
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
SLOT_DEFINITIONS_PATH = CONFIG_DIR / "slot_definitions.json"
SLOT_METADATA_PATH = CONFIG_DIR / "slot_metadata.json"


class SlotLoader:
    """도메인/카테고리별 슬롯을 로드하고 관리하는 클래스"""

    _instance: Optional["SlotLoader"] = None

    def __init__(self):
        self._definitions: Dict[str, Any] = {}
        self._metadata: Dict[str, Any] = {}
        self._category_to_domain: Dict[str, str] = {}  # 카테고리 → 도메인 매핑
        self._load_configs()

    @classmethod
    def get_instance(cls) -> "SlotLoader":
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_configs(self) -> None:
        """설정 파일들을 로드합니다."""
        try:
            # slot_definitions.json 로드
            if SLOT_DEFINITIONS_PATH.exists():
                with open(SLOT_DEFINITIONS_PATH, "r", encoding="utf-8") as f:
                    self._definitions = json.load(f)
                logger.info(f"슬롯 정의 로드 완료: {len(self._definitions)} 도메인")

                # 카테고리 → 도메인 매핑 생성
                for domain_code, domain_data in self._definitions.items():
                    if domain_code.startswith("_"):  # _DEFAULT 등 제외
                        continue
                    categories = domain_data.get("categories", {})
                    for category_name in categories.keys():
                        self._category_to_domain[category_name] = domain_code
            else:
                logger.warning(f"슬롯 정의 파일이 없습니다: {SLOT_DEFINITIONS_PATH}")

            # slot_metadata.json 로드
            if SLOT_METADATA_PATH.exists():
                with open(SLOT_METADATA_PATH, "r", encoding="utf-8") as f:
                    self._metadata = json.load(f)
                logger.info(f"슬롯 메타데이터 로드 완료: {len(self._metadata)} 슬롯")
            else:
                logger.warning(f"슬롯 메타데이터 파일이 없습니다: {SLOT_METADATA_PATH}")

        except Exception as e:
            logger.error(f"슬롯 설정 로드 실패: {e}", exc_info=True)

    def get_domain_by_category(self, category: str) -> Optional[str]:
        """카테고리명으로 도메인 코드를 찾습니다.

        Args:
            category: 카테고리명 (예: "도난/분실 신청/해제")

        Returns:
            도메인 코드 (예: "SEC_CARD") 또는 None
        """
        return self._category_to_domain.get(category)

    def get_domain_name(self, domain_code: str) -> str:
        """도메인 코드로 도메인 이름을 반환합니다.

        Args:
            domain_code: 도메인 코드 (예: "SEC_CARD")

        Returns:
            도메인 이름 (예: "분실/보안")
        """
        domain_data = self._definitions.get(domain_code, {})
        return domain_data.get("domain_name", "기타")

    def get_slots_for_category(self, category: str) -> Tuple[List[str], List[str]]:
        """카테고리에 필요한 슬롯 목록을 반환합니다.

        Args:
            category: 카테고리명 (예: "도난/분실 신청/해제")

        Returns:
            (required_slots, optional_slots) 튜플
        """
        domain_code = self.get_domain_by_category(category)

        if not domain_code:
            # 기본 슬롯 반환
            logger.warning(f"카테고리 '{category}'에 대한 도메인을 찾을 수 없음, 기본 슬롯 사용")
            default_data = self._definitions.get("_DEFAULT", {})
            default_category = default_data.get("categories", {}).get("기타 문의", {})
            return (
                default_category.get("required_slots", ["inquiry_detail"]),
                default_category.get("optional_slots", [])
            )

        domain_data = self._definitions.get(domain_code, {})
        categories = domain_data.get("categories", {})
        category_data = categories.get(category, {})

        required = category_data.get("required_slots", [])
        optional = category_data.get("optional_slots", [])

        return (required, optional)

    def get_slot_metadata(self, slot_name: str) -> Dict[str, Any]:
        """슬롯의 메타데이터(라벨, 질문 등)를 반환합니다.

        Args:
            slot_name: 슬롯 이름 (예: "card_last_4_digits")

        Returns:
            슬롯 메타데이터 딕셔너리
        """
        return self._metadata.get(slot_name, {
            "label": slot_name,
            "question": f"{slot_name}을(를) 알려주세요.",
            "validation": None
        })

    def get_slot_question(self, slot_name: str) -> str:
        """슬롯에 대한 질문을 반환합니다."""
        metadata = self.get_slot_metadata(slot_name)
        return metadata.get("question", f"{slot_name}을(를) 알려주세요.")

    def get_slot_label(self, slot_name: str) -> str:
        """슬롯의 라벨(한글명)을 반환합니다."""
        metadata = self.get_slot_metadata(slot_name)
        return metadata.get("label", slot_name)

    def get_all_slot_info_for_category(self, category: str) -> Dict[str, Any]:
        """카테고리에 필요한 모든 슬롯 정보를 반환합니다.

        UI 표시용으로 도메인명, 카테고리명, 슬롯 정보를 한 번에 반환합니다.

        Args:
            category: 카테고리명

        Returns:
            {
                "domain_code": "SEC_CARD",
                "domain_name": "인증/보안/카드관리",
                "category": "도난/분실 신청/해제",
                "required_slots": [
                    {"name": "card_last_4_digits", "label": "카드 뒤 4자리", "question": "..."},
                    {"name": "loss_date", "label": "분실 일시", "question": "..."},
                ],
                "optional_slots": [...]
            }
        """
        domain_code = self.get_domain_by_category(category) or "_DEFAULT"
        domain_name = self.get_domain_name(domain_code)
        required, optional = self.get_slots_for_category(category)

        def build_slot_info(slot_names: List[str]) -> List[Dict[str, Any]]:
            return [
                {
                    "name": name,
                    "label": self.get_slot_label(name),
                    "question": self.get_slot_question(name),
                    "validation": self.get_slot_metadata(name).get("validation")
                }
                for name in slot_names
            ]

        return {
            "domain_code": domain_code,
            "domain_name": domain_name,
            "category": category,
            "required_slots": build_slot_info(required),
            "optional_slots": build_slot_info(optional)
        }

    def get_missing_required_slots(self, category: str, collected_info: Dict[str, Any]) -> List[str]:
        """아직 수집되지 않은 필수 슬롯 목록을 반환합니다.

        Args:
            category: 카테고리명
            collected_info: 이미 수집된 정보 딕셔너리

        Returns:
            수집되지 않은 필수 슬롯 이름 목록
        """
        required_slots, _ = self.get_slots_for_category(category)

        missing = []
        for slot_name in required_slots:
            value = collected_info.get(slot_name)
            if not value or (isinstance(value, str) and not value.strip()):
                missing.append(slot_name)

        return missing

    def is_collection_complete(self, category: str, collected_info: Dict[str, Any]) -> bool:
        """필수 슬롯이 모두 수집되었는지 확인합니다."""
        missing = self.get_missing_required_slots(category, collected_info)
        return len(missing) == 0


# 편의 함수
def get_slot_loader() -> SlotLoader:
    """SlotLoader 싱글톤 인스턴스를 반환합니다."""
    return SlotLoader.get_instance()
