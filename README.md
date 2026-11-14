# KidGuard – ngân hàng câu hỏi

Câu hỏi trắc nghiệm A/B/C/D cho app KidGuard. App tải `manifest.json` rồi các file `grade_N.json`
có mã sha256 thay đổi, kiểm tra định dạng trước khi dùng.

| File | Cấp |
|---|---|
| `grade_1.json` … `grade_12.json` | Lớp 1–12 (CT GDPT 2018, sửa đổi theo TT 13/2022, TT 17/2025) |
| `grade_13.json` | Đại học |
| `grade_14.json` | Sau đại học |

Mỗi câu: `id`, `subject`, `topic`, `type` (`academic` / `open` / `social`), `question`,
`options` (4 đáp án khác nhau), `answerIndex` (0–3), `suggestion`, `source` (căn cứ chương trình / điều luật).

## Cập nhật

App kiểm tra `manifest.json` trên nhánh **main** mỗi khi mở hoặc quay lại app (tối đa 15 phút/lần),
nên merge vào `main` là phát hành cho mọi máy.

**Cách 1 – sửa trực tiếp trong repo này** (kể cả trên giao diện GitHub): sửa `grade_N.json`, commit.
GitHub Action [`Build question manifest`](.github/workflows/manifest.yml) sẽ:

1. Kiểm tra định dạng giống app (4 đáp án khác nhau, `answerIndex` 0–3, không trùng `id`, ≥ 5 câu…).
   File sai → workflow báo lỗi, manifest giữ nguyên, app tiếp tục dùng bản cũ.
2. Tạo lại `manifest.json` (sha256, số câu) và tự tăng `version`, rồi commit lại vào nhánh đó.

Làm trên `develop`, xong thì merge `develop` → `main`.

**Cách 2 – từ repo app** (`main_app/assets/questions/`, nơi giữ bộ câu hỏi đóng gói sẵn trong app):

1. `fvm dart run tool/make_question_manifest.dart` (tự tăng `version`)
2. `fvm flutter test`
3. Chép các file `*.json` sang repo này, commit lên `develop` rồi merge vào `main`.
   Nếu chép manifest có `version` thấp hơn bản đang phát hành, Action tự nâng lại (không bao giờ giảm).

Chạy thử trên máy: `python3 scripts/build_manifest.py` (thêm `--check` để chỉ kiểm tra).

Câu sửa nội dung phải có **id mới**. Câu hỏi do AI soạn và đối chiếu với chương trình; nên để giáo viên rà lại.
