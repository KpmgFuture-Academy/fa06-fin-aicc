"""
NLU Category Pipeline - Text Normalizer
=======================================

텍스트 정규화 유틸리티
"""

import re
from typing import Optional


def normalize_text(text: str) -> str:
    """
    텍스트 정규화

    - 연속 공백 제거
    - 줄바꿈 정리
    - 앞뒤 공백 제거

    Args:
        text: 원본 텍스트

    Returns:
        정규화된 텍스트

    Example:
        >>> normalize_text("  카드   한도  올려주세요  ")
        '카드 한도 올려주세요'
    """
    if not text:
        return ""

    # 연속 공백을 단일 공백으로
    text = re.sub(r"\s+", " ", text)

    # 앞뒤 공백 제거
    text = text.strip()

    return text


def clean_whitespace(text: str) -> str:
    """
    공백 정리 (정규화보다 단순한 버전)

    Args:
        text: 원본 텍스트

    Returns:
        공백 정리된 텍스트
    """
    return " ".join(text.split())


def remove_special_chars(text: str, keep_korean: bool = True) -> str:
    """
    특수 문자 제거

    Args:
        text: 원본 텍스트
        keep_korean: 한글 유지 여부

    Returns:
        특수 문자 제거된 텍스트

    Example:
        >>> remove_special_chars("카드@한도#올려주세요!")
        '카드한도올려주세요'
    """
    if keep_korean:
        # 한글, 영문, 숫자, 공백만 유지
        pattern = r"[^가-힣a-zA-Z0-9\s]"
    else:
        # 영문, 숫자, 공백만 유지
        pattern = r"[^a-zA-Z0-9\s]"

    return re.sub(pattern, "", text)


def truncate_text(
    text: str,
    max_length: int = 100,
    suffix: str = "..."
) -> str:
    """
    텍스트 길이 제한

    Args:
        text: 원본 텍스트
        max_length: 최대 길이
        suffix: 잘릴 경우 추가할 접미사

    Returns:
        길이 제한된 텍스트

    Example:
        >>> truncate_text("아주 긴 텍스트입니다", max_length=10)
        '아주 긴 텍스...'
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def extract_keywords(text: str, min_length: int = 2) -> list[str]:
    """
    간단한 키워드 추출 (공백 기준)

    Args:
        text: 원본 텍스트
        min_length: 최소 키워드 길이

    Returns:
        키워드 리스트

    Example:
        >>> extract_keywords("카드 한도 상향 신청")
        ['카드', '한도', '상향', '신청']
    """
    words = text.split()
    return [w for w in words if len(w) >= min_length]


def mask_sensitive_info(
    text: str,
    mask_char: str = "*",
    patterns: Optional[list[str]] = None
) -> str:
    """
    민감 정보 마스킹

    기본 패턴:
    - 전화번호: 010-****-1234
    - 카드번호: ****-****-****-1234

    Args:
        text: 원본 텍스트
        mask_char: 마스킹 문자
        patterns: 추가 정규식 패턴 리스트

    Returns:
        마스킹된 텍스트
    """
    result = text

    # 전화번호 마스킹 (010-1234-5678 → 010-****-5678)
    phone_pattern = r"(01[0-9])-?(\d{4})-?(\d{4})"
    result = re.sub(
        phone_pattern,
        lambda m: f"{m.group(1)}-{mask_char*4}-{m.group(3)}",
        result
    )

    # 카드번호 마스킹 (1234-5678-9012-3456 → ****-****-****-3456)
    card_pattern = r"(\d{4})-?(\d{4})-?(\d{4})-?(\d{4})"
    result = re.sub(
        card_pattern,
        lambda m: f"{mask_char*4}-{mask_char*4}-{mask_char*4}-{m.group(4)}",
        result
    )

    # 추가 패턴 적용
    if patterns:
        for pattern in patterns:
            result = re.sub(pattern, mask_char * 4, result)

    return result
