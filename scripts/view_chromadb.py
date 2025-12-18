"""
ChromaDB 문서 조회 스크립트
사용법: python scripts/view_chromadb.py
옵션: python scripts/view_chromadb.py --output result.txt
"""

import chromadb
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description='ChromaDB 문서 조회')
    parser.add_argument('--output', '-o', type=str, help='출력 파일 경로 (예: result.txt)')
    args = parser.parse_args()

    client = chromadb.PersistentClient(path='./chroma_db')
    collection = client.get_collection('financial_documents')
    results = collection.get()

    output_lines = []
    output_lines.append(f'Total documents: {len(results["ids"])}')

    for i, (id, doc, meta) in enumerate(zip(results['ids'], results['documents'], results['metadatas'])):
        output_lines.append(f'\n[{i+1}] ID: {id}')
        output_lines.append(f'    Metadata: {meta}')
        output_lines.append(f'    Content: {doc[:100]}...' if len(doc) > 100 else f'    Content: {doc}')

    output_text = '\n'.join(output_lines)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f'결과가 {args.output}에 저장되었습니다.')
    else:
        print(output_text)

if __name__ == '__main__':
    main()
