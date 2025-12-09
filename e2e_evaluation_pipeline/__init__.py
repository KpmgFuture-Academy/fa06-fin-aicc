"""
E2E Evaluation Pipeline for AICC Voice Bot System
=================================================

카드사 AICC 자동화 시스템의 End-to-End 성능 평가 파이프라인

평가 대상 모듈:
    - STT (Speech-to-Text): VITO API
    - Intent Classification: KcELECTRA + LoRA
    - Triage Agent: 요청 분류
    - RAG Hybrid Search: ChromaDB + BM25 + Reranking
    - Slot Filling: 정보 수집
    - Summary Agent: 요약 및 감정 분석
    - LangGraph Flow: 워크플로우 전이
    - E2E: 전체 시스템 통합

Author: KPMG 6기 2팀 (유선 없는 무선팀)
Date: 2025-12-08
"""

__version__ = "1.0.0"
__author__ = "KPMG 6기 2팀"

from .configs.kpi_thresholds import KPIThresholds, BenchmarkStandards
