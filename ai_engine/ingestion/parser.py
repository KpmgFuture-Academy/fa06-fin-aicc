
"""KB JSON 파서: 텍스트와 메타데이터를 추출합니다."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Tuple, List, Iterable


def _normalize_intents(value: Any) -> List[str]:
    """의도(intent) 필드를 문자열 리스트로 정규화한다."""
    if value is None:
        return []

    if isinstance(value, str):
        # '#' 기준으로 구분된 단일 문자열일 수 있음
        parts = [segment.strip() for segment in value.split("#") if segment.strip()]
        return [f"#{part}" if not part.startswith("#") else part for part in parts] or [value.strip()]

    if isinstance(value, Iterable):
        normalized = []
        for item in value:
            if not item:
                continue
            item_str = str(item).strip()
            if not item_str:
                continue
            normalized.append(item_str if item_str.startswith("#") else f"#{item_str}")
        return normalized

    return [str(value).strip()]


def extract_documents_from_payload(payload: Any) -> List[Dict[str, Any]]:
    """JSON 페이로드에서 하나 이상의 KB 문서를 추출한다.

    Args:
        payload: JSON에서 로드한 원시 데이터

    Returns:
        dict 리스트 (각 항목은 KB 문서)
    """
    if isinstance(payload, dict):
        documents = payload.get("documents")
        if isinstance(documents, list):
            return [doc for doc in documents if isinstance(doc, dict)]
        return [payload]

    if isinstance(payload, list):
        return [doc for doc in payload if isinstance(doc, dict)]

    raise ValueError("지원하지 않는 KB JSON 구조입니다. dict 또는 list 여야 합니다.")


def parse_kb_document(
    document: Dict[str, Any],
    source_path: Path | None = None,
    document_index: int | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """KB JSON dict에서 텍스트와 메타데이터를 추출한다."""
    if not isinstance(document, dict):
        raise ValueError("KB 문서는 dict 형태여야 합니다.")

    content = str(document.get("content", "")).strip()
    if not content:
        raise ValueError("KB 문서에 'content' 필드가 없습니다.")

    kb_id = document.get("kb_id")
    metadata: Dict[str, Any] = {
        "kb_id": document.get("kb_id"),
        "title": document.get("title"),
        "category": document.get("category"),
        "summary": document.get("summary"),
        "intents": _normalize_intents(document.get("intents", [])),
    }

    if source_path is not None:
        metadata["source"] = source_path.name
        metadata["source_path"] = str(source_path)

    if document_index is not None:
        metadata["source_doc_index"] = document_index

    if kb_id is not None:
        metadata["kb_id"] = str(kb_id)

    return content, metadata


def parse_multiple_documents(documents: List[Dict[str, Any]], sources: List[Path | None]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """여러 KB 문서를 일괄 파싱한다."""
    if len(documents) != len(sources):
        raise ValueError("documents와 sources 길이가 일치해야 합니다.")

    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for idx, (doc, source) in enumerate(zip(documents, sources)):
        text, metadata = parse_kb_document(doc, source, document_index=idx)
        texts.append(text)
        metadatas.append(metadata)

    return texts, metadatas

