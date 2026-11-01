"""离线测试：只测 Markdown 解析和分批逻辑，不连飞书。运行：python3 -m unittest discover tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import md2feishu as m  # noqa: E402


def types(md):
    tops, desc = m.parse(md)
    byid = {d["block_id"]: d for d in desc}
    return [byid[t]["block_type"] for t in tops], desc


class TestParse(unittest.TestCase):
    def test_headings(self):
        t, _ = types("# 一\n## 二\n###### 六")
        self.assertEqual(t, [3, 4, 8])

    def test_lists_todo_quote(self):
        t, desc = types("- 甲\n* 乙\n1. 丙\n2) 丁\n- [x] 完成\n- [ ] 未完成\n> 引用")
        self.assertEqual(t, [12, 12, 13, 13, 17, 17, 15])
        todos = [d for d in desc if d["block_type"] == 17]
        self.assertEqual([d["todo"]["style"]["done"] for d in todos], [True, False])

    def test_code_and_divider(self):
        t, desc = types("```python\nprint(1)\n# 不是标题\n```\n---")
        self.assertEqual(t, [14, 22])
        self.assertEqual(desc[0]["code"]["elements"][0]["text_run"]["content"], "print(1)\n# 不是标题")

    def test_table(self):
        t, desc = types("| 名称 | 数值 |\n|---|:-:|\n| a | 1 |\n| b |")
        self.assertEqual(t, [31])
        tbl = desc[0]["table"]["property"]
        self.assertEqual((tbl["row_size"], tbl["column_size"]), (3, 2))
        self.assertEqual(len([d for d in desc if d["block_type"] == 32]), 6)

    def test_inline(self):
        els = m.inline("普通**加粗**和`代码`及[链接](https://a.com/x?y=1)")
        styles = [e["text_run"].get("text_element_style", {}) for e in els]
        self.assertTrue(styles[1]["bold"])
        self.assertTrue(styles[3]["inline_code"])
        self.assertEqual(styles[5]["link"]["url"], "https%3A%2F%2Fa.com%2Fx%3Fy%3D1")

    def test_blank_and_empty_quote_skipped(self):
        t, _ = types("\n\n>\n正文\n")
        self.assertEqual(t, [2])


class TestBatches(unittest.TestCase):
    def test_split_by_top_count(self):
        tops, desc = m.parse("\n".join("段落%d" % i for i in range(40)))
        batches = m.make_batches(tops, desc)
        self.assertEqual([len(c) for c, _ in batches], [15, 15, 10])

    def test_split_by_descendant_count(self):
        row = "|" + "|".join(["x"] * 8) + "|"
        table = "\n".join([row, "|" + "---|" * 8] + [row] * 29)  # 30 行 × 8 列 = 481 块
        tops, desc = m.parse(table + "\n\n" + table)
        batches = m.make_batches(tops, desc)
        self.assertEqual(len(batches), 2)
        self.assertTrue(all(len(b) <= m.MAX_DESC for _, b in batches))


class TestConfig(unittest.TestCase):
    def test_missing_credentials_exits_with_hint(self):
        env = {k: os.environ.pop(k) for k in ("FEISHU_APP_ID", "FEISHU_APP_SECRET") if k in os.environ}
        try:
            with self.assertRaises(SystemExit) as cm:
                m.get_token()
            self.assertIn("FEISHU_APP_ID", str(cm.exception))
        finally:
            os.environ.update(env)


if __name__ == "__main__":
    unittest.main()
