"""
NLU Category Pipeline - Logger Utility
======================================

파이프라인 로깅 유틸리티
"""

import logging
import sys
from typing import Optional
from datetime import datetime


# 기본 로거 이름
DEFAULT_LOGGER_NAME = "nlu_category"

# 로그 포맷
DEFAULT_FORMAT = "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
SIMPLE_FORMAT = "[%(levelname)s] %(message)s"


def setup_logger(
    name: str = DEFAULT_LOGGER_NAME,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """
    로거 설정

    Args:
        name: 로거 이름
        level: 로그 레벨 (default: INFO)
        log_file: 로그 파일 경로 (None이면 콘솔만)
        format_string: 로그 포맷 문자열

    Returns:
        설정된 Logger 인스턴스

    Example:
        >>> logger = setup_logger("my_module", logging.DEBUG)
        >>> logger.info("Hello World")
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 기존 핸들러 제거
    logger.handlers.clear()

    # 포맷터 생성
    formatter = logging.Formatter(
        format_string or DEFAULT_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 (옵션)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = DEFAULT_LOGGER_NAME) -> logging.Logger:
    """
    로거 가져오기

    Args:
        name: 로거 이름

    Returns:
        Logger 인스턴스

    Example:
        >>> logger = get_logger("nlu_category.nodes")
        >>> logger.info("Processing...")
    """
    return logging.getLogger(name)


class PipelineLogger:
    """
    파이프라인 전용 로거

    노드별 로깅과 성능 측정 지원
    """

    def __init__(self, name: str = DEFAULT_LOGGER_NAME, verbose: bool = False):
        """
        Args:
            name: 로거 이름
            verbose: 상세 로그 출력 여부
        """
        self.logger = get_logger(name)
        self.verbose = verbose
        self._start_times: dict[str, datetime] = {}

    def node_start(self, node_name: str) -> None:
        """노드 시작 로깅"""
        self._start_times[node_name] = datetime.now()
        if self.verbose:
            self.logger.info(f"[{node_name}] 시작")

    def node_end(self, node_name: str, success: bool = True) -> float:
        """
        노드 종료 로깅

        Returns:
            소요 시간 (초)
        """
        start_time = self._start_times.pop(node_name, None)
        elapsed = 0.0

        if start_time:
            elapsed = (datetime.now() - start_time).total_seconds()

        status = "완료" if success else "실패"
        if self.verbose:
            self.logger.info(f"[{node_name}] {status} ({elapsed:.3f}s)")

        return elapsed

    def debug(self, msg: str) -> None:
        """디버그 로그"""
        if self.verbose:
            self.logger.debug(msg)

    def info(self, msg: str) -> None:
        """정보 로그"""
        self.logger.info(msg)

    def warning(self, msg: str) -> None:
        """경고 로그"""
        self.logger.warning(msg)

    def error(self, msg: str) -> None:
        """에러 로그"""
        self.logger.error(msg)
