#!/usr/bin/env python3
"""Kiểm tra chất lượng ngân hàng câu hỏi KidGuard.

    python3 scripts/check_questions.py [THƯ_MỤC] [--allow-draft] [--strict] [--target N] [-v]

THƯ_MỤC mặc định là thư mục gốc repo này (chứa grade_N.json). Trong repo app:
    python3 ../../kid_guard_question/scripts/check_questions.py assets/questions

- LỖI (exit 1): câu hỏi app sẽ từ chối, hoặc chắc chắn sai khi hiển thị
  (vd. đáp án "Cả A và B" — app đảo thứ tự đáp án nên chữ cái không còn đúng).
- CẢNH BÁO: nên sửa (lộ đáp án vì đáp án đúng dài hẳn, số thập phân dùng dấu chấm…).
  --strict coi cảnh báo là lỗi.
- Báo cáo độ phủ: số câu theo lớp / loại / môn / chủ đề / độ khó / học kỳ / trạng thái.

Định dạng một câu (trường có dấu * là tuỳ chọn, app cũ bỏ qua):
    id, subject, topic, type (academic|open|social), question, options (4),
    answerIndex (0–3), suggestion, source,
    *difficulty (1 dễ | 2 vừa | 3 khó), *term (1 | 2: học kỳ),
    *status (draft | ai-checked | teacher-reviewed; thiếu = ai-checked),
    *reviewedBy (bắt buộc khi status = teacher-reviewed)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRADE_FILE = re.compile(r"^grade_(\d+)\.json$")
MIN_GRADE, MAX_GRADE = 1, 14
MIN_QUESTIONS = 5
TYPES = ("academic", "open", "social")
STATUSES = ("draft", "ai-checked", "teacher-reviewed")
REQUIRED_TEXT = ("id", "subject", "topic", "question", "suggestion", "source")
KNOWN_FIELDS = set(REQUIRED_TEXT) | {
    "type", "options", "answerIndex", "difficulty", "term", "status", "reviewedBy",
}

# Đáp án nhắc tới vị trí / đáp án khác: sai khi app đảo thứ tự A/B/C/D.
POSITIONAL = [
    re.compile(
        r"^\s*(?:cả\s+)?(?:đáp án\s+)?[A-D](?:\s*(?:,|và|hoặc|&|and|or)\s*[A-D])+"
        r"(?:\s+đều\s+(?:đúng|sai))?\s*\.?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:đáp án|phương án|ý|câu)\s+(?:nào|trên|kể trên|đã nêu|đều đúng|đều sai)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:tất cả|cả hai|cả ba)\s+(?:đều\s+)?(?:đúng|sai)\b", re.IGNORECASE),
    re.compile(r"\b(?:all|none|both)\s+of\s+(?:the\s+)?(?:above|these)\b", re.IGNORECASE),
]
# Số thập phân viết kiểu Anh (3.5, 0.25). Dấu chấm + đúng 3 chữ số là phân tách hàng nghìn → bỏ qua.
DOT_DECIMAL = re.compile(r"(?<![\d.,])\d+\.(?:\d{1,2}|\d{4,})(?![\d.,])")
NUMERIC_SUBJECTS = ("toán", "vật lí", "vật lý", "hóa", "hoá", "khoa học", "thống kê", "xác suất")

MAX_QUESTION_CHARS = 260
MAX_OPTION_CHARS = 100
LONGEST_RATIO = 1.25  # đáp án đúng dài hơn đáp án dài thứ hai ≥ 25% → "lộ"
LONGEST_SHARE_WARN = 0.35  # ngẫu nhiên ~25%


def id_prefix(grade: int) -> str:
    return {13: "dh_", 14: "sdh_"}.get(grade, f"g{grade}_")


def norm(s: str, fold_case: bool = True) -> str:
    s = unicodedata.normalize("NFC", s)
    if fold_case:
        s = s.casefold()
    s = re.sub(r"\s+", " ", s).strip()
    return s.rstrip(" .?!:;")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[int, dict] = field(default_factory=dict)

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


def check_question(q: object, grade: int, where: str, rep: Report, allow_draft: bool) -> bool:
    """Kiểm tra một câu. Trả về False nếu có lỗi chặn (để bỏ qua các kiểm tra sau)."""
    if not isinstance(q, dict):
        rep.err(where, "phải là object")
        return False
    ok = True
    for f in REQUIRED_TEXT:
        v = q.get(f)
        if not isinstance(v, str) or not v.strip():
            rep.err(where, f"thiếu hoặc rỗng trường '{f}'")
            ok = False
        elif v != v.strip():
            rep.warn(where, f"'{f}' có khoảng trắng thừa ở đầu/cuối")
    if q.get("type") not in TYPES:
        rep.err(where, f"'type' phải là một trong {list(TYPES)}")
        ok = False
    opts = q.get("options")
    if not (isinstance(opts, list) and len(opts) == 4
            and all(isinstance(o, str) and o.strip() for o in opts)):
        rep.err(where, "'options' phải có đúng 4 đáp án dạng chữ, không rỗng")
        return False
    # Giữ phân biệt hoa/thường: "1 AA : 1 aa" ≠ "1 Aa : 1 aa" (di truyền), "m" ≠ "M"…
    if len({norm(o, fold_case=False) for o in opts}) != 4:
        rep.err(where, "có đáp án trùng nhau (chỉ khác khoảng trắng / dấu câu cuối)")
        ok = False
    ans = q.get("answerIndex")
    if not isinstance(ans, int) or isinstance(ans, bool) or not 0 <= ans <= 3:
        rep.err(where, "'answerIndex' phải là số 0–3")
        return False

    qid = q.get("id")
    if isinstance(qid, str) and not qid.startswith(id_prefix(grade)):
        rep.err(where, f"id phải bắt đầu bằng '{id_prefix(grade)}'")
        ok = False

    for key, lo, hi in (("difficulty", 1, 3), ("term", 1, 2)):
        if key in q:
            v = q[key]
            if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
                rep.err(where, f"'{key}' phải là số {lo}–{hi}")
                ok = False
    status = q.get("status", "ai-checked")
    if status not in STATUSES:
        rep.err(where, f"'status' phải là một trong {list(STATUSES)}")
        ok = False
    elif status == "draft" and not allow_draft:
        rep.err(where, "câu nháp (status=draft) chưa được phát hành — app bản cũ vẫn hiện câu này")
        ok = False
    elif status == "teacher-reviewed" and not str(q.get("reviewedBy", "")).strip():
        rep.err(where, "status=teacher-reviewed cần 'reviewedBy'")
        ok = False
    for k in q:
        if k not in KNOWN_FIELDS:
            rep.warn(where, f"trường lạ '{k}' (gõ nhầm?)")

    for i, o in enumerate(opts):
        for pat in POSITIONAL:
            if pat.search(o):
                rep.err(where, f"đáp án {'ABCD'[i]} \"{o}\" nhắc tới vị trí/đáp án khác — "
                               "app đảo thứ tự đáp án nên sẽ sai")
                ok = False
                break
        if len(o) > MAX_OPTION_CHARS:
            rep.warn(where, f"đáp án {'ABCD'[i]} dài {len(o)} ký tự (> {MAX_OPTION_CHARS})")
    text = q.get("question") or ""
    if len(text) > MAX_QUESTION_CHARS:
        rep.warn(where, f"câu hỏi dài {len(text)} ký tự (> {MAX_QUESTION_CHARS})")
    subject = norm(str(q.get("subject", "")))
    if any(s in subject for s in NUMERIC_SUBJECTS):
        for s in [text, *opts]:
            m = DOT_DECIMAL.search(s)
            if m:
                rep.warn(where, f"\"{m.group()}\": số thập phân tiếng Việt dùng dấu phẩy")
                break
    return ok


def answer_is_giveaway(opts: list[str], ans: int) -> bool:
    lengths = sorted((len(o.strip()) for o in opts), reverse=True)
    correct = len(opts[ans].strip())
    return correct == lengths[0] and correct >= LONGEST_RATIO * max(lengths[1], 1)


def check_grade(path: Path, grade: int, rep: Report, allow_draft: bool,
                seen_ids: dict[str, str], seen_text: dict[str, str]) -> int:
    """Kiểm tra một file. Trả về số câu sẽ được app dùng (không tính câu nháp)."""
    try:
        data = json.loads(path.read_bytes().decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        rep.err(path.name, f"không phải JSON hợp lệ ({e})")
        return 0
    if not isinstance(data, list):
        rep.err(path.name, "gốc phải là một danh sách câu hỏi")
        return 0

    st = {
        "total": 0, "type": Counter(), "subject": Counter(), "topic": Counter(),
        "difficulty": Counter(), "term": Counter(), "status": Counter(), "giveaway": [],
    }
    texts_here: dict[str, str] = {}
    usable = 0
    for i, q in enumerate(data, 1):
        qid = q.get("id") if isinstance(q, dict) else None
        where = f"{path.name} #{i} ({qid or '?'})"
        if not check_question(q, grade, where, rep, allow_draft):
            continue
        if qid in seen_ids:
            rep.err(where, f"trùng id với {seen_ids[qid]}")
        seen_ids[qid] = where
        key = norm(q["question"])
        if key in texts_here:
            rep.err(where, f"trùng nội dung câu hỏi với {texts_here[key]}")
        elif key in seen_text:
            rep.warn(where, f"trùng nội dung với {seen_text[key]} (lớp khác)")
        texts_here[key] = where

        status = q.get("status", "ai-checked")
        st["status"][status] += 1
        if status == "draft":
            continue
        usable += 1
        st["total"] += 1
        st["type"][q["type"]] += 1
        st["subject"][q["subject"]] += 1
        st["topic"][(q["subject"], q["topic"])] += 1
        st["difficulty"][q.get("difficulty", "?")] += 1
        st["term"][q.get("term", "?")] += 1
        if answer_is_giveaway(q["options"], q["answerIndex"]):
            st["giveaway"].append(qid)
    seen_text.update(texts_here)

    if usable < MIN_QUESTIONS:
        rep.err(path.name, f"cần ít nhất {MIN_QUESTIONS} câu dùng được (có {usable})")
    for t in TYPES:
        if st["type"][t] == 0 and usable:
            rep.warn(path.name, f"chưa có câu loại '{t}'")
    if usable and len(st["giveaway"]) / usable > LONGEST_SHARE_WARN:
        rep.warn(path.name, f"{len(st['giveaway'])}/{usable} câu có đáp án đúng dài hẳn các đáp án "
                            f"khác (bé dễ đoán): {', '.join(st['giveaway'][:8])}"
                            f"{'…' if len(st['giveaway']) > 8 else ''}")
    rep.stats[grade] = st
    return usable


def grade_files(directory: Path) -> list[tuple[int, Path]]:
    files = []
    for p in directory.iterdir():
        m = GRADE_FILE.match(p.name)
        if m and MIN_GRADE <= int(m.group(1)) <= MAX_GRADE:
            files.append((int(m.group(1)), p))
    return sorted(files)


def check_directory(directory: Path, allow_draft: bool = False) -> tuple[Report, dict[int, int]]:
    rep = Report()
    counts: dict[int, int] = {}
    seen_ids: dict[str, str] = {}
    seen_text: dict[str, str] = {}
    files = grade_files(directory)
    if not files:
        rep.err(str(directory), "không tìm thấy file grade_N.json nào")
    for grade, path in files:
        counts[grade] = check_grade(path, grade, rep, allow_draft, seen_ids, seen_text)
    return rep, counts


def label(grade: int) -> str:
    return {13: "Đại học", 14: "Sau ĐH"}.get(grade, f"Lớp {grade}")


def print_coverage(rep: Report, target: int, verbose: bool) -> None:
    print("\nĐộ phủ (không tính câu nháp):")
    print(f"{'':9}{'câu':>5} {'môn':>4} {'chủ đề':>7} {'1 câu/c.đề':>11}  độ khó 1/2/3/?   học kỳ 1/2/?   đã duyệt")
    total = 0
    for grade, st in sorted(rep.stats.items()):
        total += st["total"]
        thin = sum(1 for n in st["topic"].values() if n == 1)
        d, t = st["difficulty"], st["term"]
        reviewed = st["status"]["teacher-reviewed"]
        need = f"  (thiếu {target - st['total']} so với {target})" if target and st["total"] < target else ""
        print(f"{label(grade):9}{st['total']:>5} {len(st['subject']):>4} {len(st['topic']):>7} {thin:>11}"
              f"  {d[1]:>3}/{d[2]}/{d[3]}/{d['?']:<4}  {t[1]:>3}/{t[2]}/{t['?']:<5}  {reviewed:>4}{need}")
        if verbose:
            for subj, n in st["subject"].most_common():
                print(f"{'':11}{subj}: {n}")
    print(f"{'Tổng':9}{total:>5}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("directory", nargs="?", default=str(ROOT))
    ap.add_argument("--allow-draft", action="store_true", help="cho phép câu nháp (khi đang soạn)")
    ap.add_argument("--strict", action="store_true", help="coi cảnh báo là lỗi")
    ap.add_argument("--target", type=int, default=0, help="số câu mục tiêu mỗi lớp (báo thiếu)")
    ap.add_argument("-v", "--verbose", action="store_true", help="in số câu theo môn")
    ap.add_argument("-q", "--quiet", action="store_true", help="không in báo cáo độ phủ")
    args = ap.parse_args()

    rep, _ = check_directory(Path(args.directory), allow_draft=args.allow_draft)
    for w in rep.warnings:
        print(f"CẢNH BÁO  {w}")
    for e in rep.errors:
        print(f"LỖI       {e}", file=sys.stderr)
    if not args.quiet:
        print_coverage(rep, args.target, args.verbose)
    print(f"\n{len(rep.errors)} lỗi, {len(rep.warnings)} cảnh báo")
    if rep.errors or (args.strict and rep.warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
