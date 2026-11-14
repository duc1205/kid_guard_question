#!/usr/bin/env python3
"""Kiểm tra các file grade_N.json và tạo lại manifest.json.

    python3 scripts/build_manifest.py [--previous <manifest đã phát hành>] [--check]

- Luật kiểm tra giống app (QuestionFileParser): file sai thì dừng, không ghi gì.
- Có file đổi so với bản đã phát hành → tăng `version`. Không bao giờ giảm
  `version` (máy đang ở bản cao hơn sẽ bỏ qua bản thấp hơn).
- --check: chỉ kiểm tra, báo lỗi nếu manifest.json chưa khớp với các file.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.json"
GRADE_FILE = re.compile(r"^grade_(\d+)\.json$")
MIN_GRADE, MAX_GRADE = 1, 14
MIN_QUESTIONS = 5
TYPES = {"academic", "open", "social"}
TEXT_FIELDS = ("id", "subject", "topic", "question", "suggestion")


def validate(path: Path, raw: bytes) -> int:
    """Trả về số câu hỏi; ném ValueError nếu file không hợp lệ."""
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"{path.name}: không phải JSON hợp lệ ({e})")
    if not isinstance(data, list):
        raise ValueError(f"{path.name}: gốc phải là một danh sách câu hỏi")
    ids = set()
    for i, q in enumerate(data, 1):
        where = f"{path.name} câu #{i} (id={q.get('id') if isinstance(q, dict) else '?'})"
        if not isinstance(q, dict):
            raise ValueError(f"{where}: phải là object")
        for f in TEXT_FIELDS:
            if not isinstance(q.get(f), str) or not q[f].strip():
                raise ValueError(f"{where}: thiếu hoặc rỗng trường '{f}'")
        if q["id"] in ids:
            raise ValueError(f"{where}: trùng id")
        ids.add(q["id"])
        if q.get("type") not in TYPES:
            raise ValueError(f"{where}: 'type' phải là một trong {sorted(TYPES)}")
        opts = q.get("options")
        if (
            not isinstance(opts, list)
            or len(opts) != 4
            or not all(isinstance(o, str) and o.strip() for o in opts)
            or len(set(opts)) != 4
        ):
            raise ValueError(f"{where}: 'options' phải có đúng 4 đáp án khác nhau, không rỗng")
        ans = q.get("answerIndex")
        if not isinstance(ans, int) or isinstance(ans, bool) or not 0 <= ans <= 3:
            raise ValueError(f"{where}: 'answerIndex' phải là số 0–3")
    if len(data) < MIN_QUESTIONS:
        raise ValueError(f"{path.name}: cần ít nhất {MIN_QUESTIONS} câu (có {len(data)})")
    return len(data)


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

    files = []
    for p in ROOT.iterdir():
        m = GRADE_FILE.match(p.name)
        if m and MIN_GRADE <= int(m.group(1)) <= MAX_GRADE:
            files.append((int(m.group(1)), p))
    files.sort()
    if not files:
        print("Không tìm thấy file grade_N.json nào", file=sys.stderr)
        return 1

    grades, errors = {}, []
    for grade, path in files:
        raw = path.read_bytes()
        try:
            count = validate(path, raw)
        except ValueError as e:
            errors.append(str(e))
            continue
        grades[str(grade)] = {
            "file": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "count": count,
        }
    if errors:
        print("Câu hỏi không hợp lệ, KHÔNG phát hành:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

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
