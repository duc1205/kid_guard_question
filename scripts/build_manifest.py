#!/usr/bin/env python3
"""Kiểm tra các file grade_N.json và tạo lại manifest.json.

    python3 scripts/build_manifest.py [--previous <manifest đã phát hành>] [--check]

- Luật kiểm tra nằm trong check_questions.py (gồm luật của app QuestionFileParser
  và luật chất lượng). Có lỗi thì dừng, không ghi gì; cảnh báo chỉ in ra.
- Có file đổi so với bản đã phát hành → tăng `version`. Không bao giờ giảm
  `version` (máy đang ở bản cao hơn sẽ bỏ qua bản thấp hơn).
- --check: chỉ kiểm tra, báo lỗi nếu manifest.json chưa khớp với các file.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_questions  # noqa: E402  (cùng thư mục; một bộ luật duy nhất)


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def hashes(manifest):
    return {k: v.get("sha256") for k, v in (manifest.get("grades") or {}).items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--previous", help="manifest.json của bản đã phát hành (trước lần push này)")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    current = load_json(MANIFEST)
    previous = load_json(args.previous) if args.previous else current

    report, counts = check_questions.check_directory(ROOT)
    for w in report.warnings:
        print(f"CẢNH BÁO  {w}")
    if report.errors:
        print("Câu hỏi không hợp lệ, KHÔNG phát hành:", file=sys.stderr)
        for e in report.errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    grades = {}
    for grade, path in check_questions.grade_files(ROOT):
        raw = path.read_bytes()
        grades[str(grade)] = {
            "file": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "count": counts[grade],
        }

    prev_version = int(previous.get("version") or 0)
    cur_version = int(current.get("version") or 0)
    changed = hashes(previous) != {k: v["sha256"] for k, v in grades.items()}
    if changed:
        version = max(prev_version + 1, cur_version)
        updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        version = max(prev_version, cur_version, 1)
        updated_at = current.get("updatedAt") or previous.get("updatedAt")

    manifest = {"version": version, "updatedAt": updated_at, "grades": grades}
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        stale = hashes(current) != hashes(manifest) or (changed and cur_version <= prev_version)
        if stale:
            print("manifest.json chưa khớp với các file grade_N.json", file=sys.stderr)
            return 1
        print(f"OK: {len(grades)} file, manifest version {cur_version}")
        return 0

    if MANIFEST.exists() and MANIFEST.read_text(encoding="utf-8") == text:
        print(f"manifest.json không đổi (version {version})")
    else:
        MANIFEST.write_text(text, encoding="utf-8")
        print(f"manifest.json → version {version} ({len(grades)} file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
