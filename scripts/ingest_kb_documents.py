"""Knowledge Base JSON을 Chroma 벡터 DB에 삽입하는 스크립트."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.ingestion.loader import iter_kb_files, load_kb_json
from ai_engine.ingestion.parser import parse_kb_document, extract_documents_from_payload
from ai_engine.vector_store import add_documents


def find_default_data_dir() -> Path:
    """KB 데이터가 있을만한 기본 경로를 추정한다."""
    candidates = [
        PROJECT_ROOT / "data" / "kb",
        PROJECT_ROOT / "data",
        PROJECT_ROOT / "docs" / "kb",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "기본 KB 데이터 디렉터리를 찾을 수 없습니다. --path 옵션을 사용해 주세요."
    )


def ingest_documents(
    target_path: Path,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> dict:
    """KB JSON 파일을 로드하여 벡터 DB에 추가한다."""
    file_paths = list(iter_kb_files(target_path))
    if not file_paths:
        raise FileNotFoundError(f"JSON 파일을 찾지 못했습니다: {target_path}")

    texts: List[str] = []
    metadatas: List[dict] = []
    total_documents = 0

    for path in file_paths:
        payload = load_kb_json(path)
        documents_in_file = extract_documents_from_payload(payload)
        if not documents_in_file:
            continue

        for doc_index, document in enumerate(documents_in_file):
            text, metadata = parse_kb_document(
                document,
                source_path=path,
                document_index=doc_index,
            )
            metadata["source_doc_total"] = len(documents_in_file)
            texts.append(text)
            metadatas.append(metadata)
            total_documents += 1

    ids = add_documents(
        texts=texts,
        metadatas=metadatas,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    return {
        "chunk_count": len(ids),
        "document_count": total_documents,
        "file_count": len(file_paths),
    }


def main():
    parser = argparse.ArgumentParser(description="KB JSON을 벡터 DB에 삽입")
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="KB JSON 파일 또는 디렉터리 경로 (기본값: data/kb 또는 data)",
    )
    parser.add_argument("--chunk-size", type=int, default=800, help="텍스트 청크 크기")
    parser.add_argument(
        "--chunk-overlap", type=int, default=150, help="텍스트 청크 겹침 길이"
    )

    args = parser.parse_args()

    try:
        target = Path(args.path).resolve() if args.path else find_default_data_dir()
        print(f"[INFO] KB 데이터 경로: {target}")

        summary = ingest_documents(
            target_path=target,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
        print(
            f"[OK] {summary['file_count']}개 파일, "
            f"{summary['document_count']}개 문서, "
            f"{summary['chunk_count']}개 청크를 벡터 DB에 추가했습니다."
        )
    except Exception as exc:
        print(f"[ERROR] KB 문서 삽입 중 오류 발생: {exc}")
        raise


if __name__ == "__main__":
    main()

