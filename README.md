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

Nguồn gốc nằm trong repo app (`main_app/assets/questions/`). Sau khi sửa:

1. `fvm dart run tool/make_question_manifest.dart` (tự tăng `version`)
2. `fvm flutter test`
3. Chép các file `*.json` sang repo này và push lên `main`.

Câu sửa nội dung phải có **id mới**. Câu hỏi do AI soạn và đối chiếu với chương trình; nên để giáo viên rà lại.
