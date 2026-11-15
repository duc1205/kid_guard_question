"""Test cho check_questions.py:  python3 -m unittest discover -s scripts -p "test_*.py" """
import json
import tempfile
import unittest
from pathlib import Path

import check_questions as c


def q(i, **kw):
    base = {
        "id": f"g3_toan_{i:02d}", "subject": "Toán", "topic": f"Chủ đề {i}",
        "type": "academic", "question": f"Câu hỏi số {i}?",
        "options": ["1", "2", "3", "4"], "answerIndex": 0,
        "suggestion": "Ôn lại.", "source": "CT GDPT 2018",
    }
    base.update(kw)
    return base


def run(questions, allow_draft=False):
    with tempfile.TemporaryDirectory() as d:
        Path(d, "grade_3.json").write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
        rep, counts = c.check_directory(Path(d), allow_draft=allow_draft)
    return rep, counts.get(3, 0)


def five(*extra):
    return [q(i) for i in range(1, 6)] + list(extra)


class CheckQuestionsTest(unittest.TestCase):
    def test_bo_hop_le_khong_loi(self):
        rep, n = run(five())
        self.assertEqual(rep.errors, [])
        self.assertEqual(n, 5)

    def test_dap_an_nhac_vi_tri_la_loi(self):
        for opt in ["Cả A và B", "A, C", "Tất cả các đáp án trên", "Không có đáp án nào đúng"]:
            rep, _ = run(five(q(6, options=["x", "y", "z", opt])))
            self.assertTrue(any("vị trí" in e for e in rep.errors), opt)

    def test_noi_dung_binh_thuong_khong_bat_nham(self):
        for opt in ["Vitamin A, C và D", "Loại bớt quan sát không có ý nghĩa", "Cả hai bạn cùng xin lỗi"]:
            rep, _ = run(five(q(6, options=["x", "y", "z", opt])))
            self.assertEqual(rep.errors, [], opt)

    def test_phan_biet_hoa_thuong_khi_so_trung(self):
        rep, _ = run(five(q(6, options=["1 AA : 1 aa", "1 Aa : 1 aa", "3 AA : 1 aa", "1 aa"])))
        self.assertEqual(rep.errors, [])
        rep, _ = run(five(q(6, options=["Hà Nội", "Hà  Nội ", "Huế", "Vinh"])))
        self.assertTrue(any("trùng" in e for e in rep.errors))

    def test_truong_moi_va_cau_nhap(self):
        rep, n = run(five(q(6, difficulty=2, term=1, status="teacher-reviewed", reviewedBy="Cô Lan")))
        self.assertEqual(rep.errors, [])
        self.assertEqual(n, 6)
        for bad in [{"difficulty": 4}, {"term": 3}, {"status": "ok"}, {"status": "teacher-reviewed"}]:
            rep, _ = run(five(q(6, **bad)))
            self.assertTrue(rep.errors, bad)
        rep, _ = run(five(q(6, status="draft")))
        self.assertTrue(any("nháp" in e for e in rep.errors))
        rep, n = run(five(q(6, status="draft")), allow_draft=True)
        self.assertEqual((rep.errors, n), ([], 5))

    def test_id_trung_sai_tien_to_va_cau_trung(self):
        rep, _ = run(five(q(1)))
        self.assertTrue(any("trùng id" in e for e in rep.errors))
        rep, _ = run(five(q(6, id="g4_toan_06")))
        self.assertTrue(any("bắt đầu bằng 'g3_'" in e for e in rep.errors))
        rep, _ = run(five(q(6, question="câu hỏi SỐ 1")))
        self.assertTrue(any("trùng nội dung" in e for e in rep.errors))

    def test_canh_bao_so_thap_phan_va_lo_dap_an(self):
        rep, _ = run(five(q(6, options=["3.45", "2,7", "6,15", "5,52"])))
        self.assertTrue(any("dấu phẩy" in w for w in rep.warnings))
        rep, _ = run(five(q(6, options=["1.000 đồng", "2", "3", "4"])))
        self.assertFalse(any("dấu phẩy" in w for w in rep.warnings))
        give = [q(i, options=["Một đáp án rất dài và chi tiết", "Ngắn", "Ngắn hơn", "Cụt"]) for i in range(1, 6)]
        rep, _ = run(give)
        self.assertTrue(any("dễ đoán" in w for w in rep.warnings))


if __name__ == "__main__":
    unittest.main()
