"""문서 로더: KB JSON 파일을 디스크에서 읽어옵니다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Iterable, List


def _resolve_existing_path(path: str | Path) -> Path:
    """입력 경로를 절대경로로 변환하고 존재 여부를 검증한다."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"파일 또는 디렉터리를 찾을 수 없습니다: {resolved}")
    return resolved


def load_kb_json(file_path: str | Path) -> Dict[str, Any]:
    """단일 KB JSON 파일을 읽어 dict로 반환한다."""
    path = _resolve_existing_path(file_path)
    if not path.is_file():
        raise ValueError(f"JSON 파일 경로가 아닙니다: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_kb_files(target: str | Path) -> Iterable[Path]:
    """경로에서 모든 KB JSON 파일을 찾아 Iterator로 반환한다.

    Notes:
        - 디렉터리를 지정하면 하위 디렉터리를 포함해 모든 *.json 파일을 찾는다.
        - 반환 값은 정렬된 Path 리스트로, 다수의 KB 파일 확장을 고려한다.
    """
    path = _resolve_existing_path(target)

    if path.is_file():
        if path.suffix.lower() != ".json":
            raise ValueError(f"JSON 확장자가 아닌 파일입니다: {path}")
        return [path]

    if path.is_dir():
        files = sorted(path.rglob("*.json"))
        if not files:
            raise FileNotFoundError(f"디렉터리에서 JSON 파일을 찾지 못했습니다: {path}")
        return files

    raise ValueError(f"지원하지 않는 경로 유형입니다: {path}")


def load_kb_documents(target: str | Path) -> List[Dict[str, Any]]:
    """파일/디렉터리에서 모든 KB JSON 문서를 로드한다."""
    documents: List[Dict[str, Any]] = []
    for file_path in iter_kb_files(target):
        documents.append(load_kb_json(file_path))
    return documents

