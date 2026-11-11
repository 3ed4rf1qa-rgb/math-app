import argparse
import json
from pathlib import Path
from engine import create_store, generate_package

def main():
    parser = argparse.ArgumentParser(description="탐구 기반 수학 문항 생성 엔진")
    parser.add_argument("--data", default="data", help="지식 데이터 폴더")
    parser.add_argument("--course", required=True, help="예: HS-CALCULUS-1")
    parser.add_argument("--standard-code", required=True, help="공식 성취기준 코드")
    parser.add_argument("--mode", choices=["offline", "gemini"], default="offline")
    parser.add_argument("--output", default="generated_package.json")
    parser.add_argument("--requirements", default=None, help="교사의 추가 요구사항")
    args = parser.parse_args()

    store = create_store(args.data)
    package = generate_package(
        store, args.course, args.standard_code,
        mode=args.mode, user_requirements=args.requirements
    )
    Path(args.output).write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"저장 완료: {args.output}")
    print(f"상태: {package['validation']['status']}")
    print(f"문항 유형: {package['item']['item_type']}")

if __name__ == "__main__":
    main()
