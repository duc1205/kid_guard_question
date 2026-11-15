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

Trường tuỳ chọn (app bản cũ bỏ qua, nên thêm vào không làm hỏng máy chưa cập nhật):

| Trường | Giá trị | Ý nghĩa |
|---|---|---|
| `difficulty` | `1` dễ · `2` vừa · `3` khó | Để app tăng dần độ khó |
| `term` | `1` · `2` | Học kỳ; chỉ hỏi phần đã học tới thời điểm đó |
| `status` | `draft` · `ai-checked` (mặc định) · `teacher-reviewed` | `draft` không được phát hành |
| `reviewedBy` | tên người duyệt | Bắt buộc khi `status` = `teacher-reviewed` |

`id` bắt đầu bằng `g<lớp>_` (lớp 1–12), `dh_` (Đại học), `sdh_` (Sau đại học).

## Kiểm tra chất lượng

```bash
python3 scripts/check_questions.py              # kiểm tra + báo cáo độ phủ
python3 scripts/check_questions.py --target 60  # báo lớp nào còn thiếu so với 60 câu
python3 scripts/check_questions.py --allow-draft  # khi đang soạn (cho phép câu nháp)
```

- **Lỗi** (chặn phát hành): sai định dạng, trùng `id`, sai tiền tố `id`, trùng nội dung câu hỏi trong
  cùng lớp, đáp án trùng, câu nháp, giá trị trường tuỳ chọn sai, và **đáp án nhắc tới vị trí**
  ("Cả A và B", "Tất cả các đáp án trên"…) vì app đảo thứ tự A/B/C/D.
- **Cảnh báo**: đáp án đúng dài hẳn các đáp án khác ở > 35% số câu của lớp (bé dễ đoán), số thập phân
  viết bằng dấu chấm trong môn tính toán, câu/đáp án quá dài, trường lạ, trùng câu với lớp khác.
- Action chạy cùng bộ luật này (`build_manifest.py` gọi `check_questions.py`) và in báo cáo độ phủ.
  Test của công cụ: `python3 -m unittest discover -s scripts -p "test_*.py"`.

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
Từ repo app: `python3 ../../kid_guard_question/scripts/check_questions.py assets/questions`
(`fvm flutter test` cũng tự chạy lệnh này nếu hai repo nằm cạnh nhau).

Câu sửa nội dung phải có **id mới**. Câu hỏi do AI soạn và đối chiếu với chương trình; nên để giáo viên rà lại.
