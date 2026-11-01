#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2feishu: 把 Markdown 一键转成飞书云文档（标题/列表/待办/引用/代码/分割线/表格）。

零依赖，只用 Python 标准库。
飞书应用凭证从环境变量读取：FEISHU_APP_ID、FEISHU_APP_SECRET。
国际版 Lark 用户额外设置 FEISHU_BASE_URL=https://open.larksuite.com/open-apis
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

__version__ = "0.1.0"

BASE = os.environ.get("FEISHU_BASE_URL", "https://open.feishu.cn/open-apis").rstrip("/")


def req(method, path, body=None, token=None):
    h = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        h["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def get_token():
    app_id = os.environ.get("FEISHU_APP_ID")
    secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not secret:
        sys.exit("缺少飞书应用凭证：请先设置环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET（见 README）")
    r = req("POST", "/auth/v3/tenant_access_token/internal",
            {"app_id": app_id, "app_secret": secret})
    if r.get("code") != 0:
        sys.exit("获取 token 失败：%s" % r)
    return r["tenant_access_token"]


# ---------- inline ----------
def inline(text):
    """把 **bold** / `code` / [t](u) 转成 text_run 列表"""
    out, pos = [], 0
    pat = re.compile(r'\*\*(.+?)\*\*|`([^`]+?)`|\[([^\]]+)\]\(([^)]+)\)')
    for m in pat.finditer(text):
        if m.start() > pos:
            out.append({"text_run": {"content": text[pos:m.start()]}})
        if m.group(1) is not None:
            out.append({"text_run": {"content": m.group(1),
                                     "text_element_style": {"bold": True}}})
        elif m.group(2) is not None:
            out.append({"text_run": {"content": m.group(2),
                                     "text_element_style": {"inline_code": True}}})
        else:
            out.append({"text_run": {"content": m.group(3),
                                     "text_element_style": {"link": {"url": urllib.parse.quote(m.group(4), safe='')}}}})
        pos = m.end()
    if pos < len(text):
        out.append({"text_run": {"content": text[pos:]}})
    if not out:
        out = [{"text_run": {"content": ""}}]
    return out


HEAD = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8}
_ctr = [0]


def nid():
    _ctr[0] += 1
    return "b%d" % _ctr[0]


def txtblk(btype, content, extra_key=None):
    key = extra_key or {2: "text", 12: "bullet", 13: "ordered", 15: "quote"}.get(btype, "text")
    if btype in HEAD.values():
        key = "heading%d" % [k for k, v in HEAD.items() if v == btype][0]
    return {"block_id": nid(), "block_type": btype,
            key: {"elements": inline(content), "style": {}}}


def parse(md):
    """返回 (top_level_ids, descendants)"""
    lines = md.split("\n")
    tops, desc = [], []
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()

        if not s or s == ">":
            i += 1; continue

        # code fence
        if s.startswith("```"):
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                buf.append(lines[j]); j += 1
            b = {"block_id": nid(), "block_type": 14,
                 "code": {"elements": [{"text_run": {"content": "\n".join(buf)}}],
                          "style": {"language": 1, "wrap": True}}}
            desc.append(b); tops.append(b["block_id"]); i = j + 1; continue

        # divider
        if re.fullmatch(r'-{3,}|\*{3,}', s):
            b = {"block_id": nid(), "block_type": 22, "divider": {}}
            desc.append(b); tops.append(b["block_id"]); i += 1; continue

        # table
        if s.startswith("|") and i + 1 < len(lines) and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
            rows = []
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                raw = lines[j].strip().strip("|")
                if re.match(r'^[\s:|-]+$', raw):
                    j += 1; continue
                rows.append([c.strip() for c in raw.split("|")])
                j += 1
            cols = max(len(r) for r in rows)
            rows = [r + [""] * (cols - len(r)) for r in rows]
            cell_ids, cellblocks = [], []
            for r in rows:
                for c in r:
                    tb = txtblk(2, c)
                    cell = {"block_id": nid(), "block_type": 32,
                            "table_cell": {}, "children": [tb["block_id"]]}
                    cellblocks.append(tb); cellblocks.append(cell)
                    cell_ids.append(cell["block_id"])
            tbl = {"block_id": nid(), "block_type": 31,
                   "table": {"property": {"row_size": len(rows), "column_size": cols,
                                          "header_row": True}},
                   "children": cell_ids}
            desc.append(tbl); desc.extend(cellblocks); tops.append(tbl["block_id"])
            i = j; continue

        # heading
        m = re.match(r'^(#{1,6})\s+(.*)$', s)
        if m:
            b = txtblk(HEAD[len(m.group(1))], m.group(2))
            desc.append(b); tops.append(b["block_id"]); i += 1; continue

        # quote
        if s.startswith("> "):
            b = txtblk(15, s[2:])
            desc.append(b); tops.append(b["block_id"]); i += 1; continue

        # todo（勾选框）
        m = re.match(r'^[-*]\s+\[([ xX])\]\s*(.*)$', s)
        if m:
            b = txtblk(17, m.group(2), extra_key="todo")
            b["todo"]["style"] = {"done": m.group(1).lower() == "x"}
            desc.append(b); tops.append(b["block_id"]); i += 1; continue

        # bullet
        m = re.match(r'^[-*]\s+(.*)$', s)
        if m:
            b = txtblk(12, m.group(1))
            desc.append(b); tops.append(b["block_id"]); i += 1; continue

        # ordered
        m = re.match(r'^\d+[.)]\s+(.*)$', s)
        if m:
            b = txtblk(13, m.group(1))
            desc.append(b); tops.append(b["block_id"]); i += 1; continue

        b = txtblk(2, s)
        desc.append(b); tops.append(b["block_id"]); i += 1

    return tops, desc


# 飞书 descendant 接口硬上限：单次 descendants ≤1000。表格一行 8 列就是 16 个块，
# 只按顶层块数分批会超，所以按「顶层块数 ≤15 且 descendant 数 ≤800」双条件切。
MAX_TOPS, MAX_DESC = 15, 800


def make_batches(tops, desc):
    """把顶层块切成若干批，返回 [(顶层id列表, 该批全部块)]"""
    byid = {d["block_id"]: d for d in desc}

    def collect(ids):
        out = []
        for i in ids:
            b = byid[i]
            out.append(b)
            if b.get("children"):
                out.extend(collect(b["children"]))
        return out

    batches, cur, cur_n = [], [], 0
    for t in tops:
        n = len(collect([t]))
        if cur and (len(cur) >= MAX_TOPS or cur_n + n > MAX_DESC):
            batches.append(cur); cur, cur_n = [], 0
        cur.append(t); cur_n += n
        if n > MAX_DESC:
            print("WARN: 单个块 %s 有 %d 个子块，超过 %d，可能失败（建议拆表）" % (t, n, MAX_DESC))
    if cur:
        batches.append(cur)
    return [(chunk, collect(chunk)) for chunk in batches]


def clear_doc(doc, tok):
    """清空文档根块下的所有子块（用于就地重刷，保留原 URL 与权限）"""
    while True:
        r = req("GET", "/docx/v1/documents/%s/blocks/%s/children?page_size=500" % (doc, doc),
                token=tok)
        if r.get("code") != 0:
            sys.exit("读取文档失败：%s" % json.dumps(r, ensure_ascii=False)[:400])
        n = len(r["data"].get("items", []))
        if not n:
            return
        end = min(n, 50)
        d = req("DELETE", "/docx/v1/documents/%s/blocks/%s/children/batch_delete" % (doc, doc),
                {"start_index": 0, "end_index": end}, token=tok)
        if d.get("code") != 0:
            sys.exit("清空文档失败：%s" % json.dumps(d, ensure_ascii=False)[:400])
        print("  已清除 %d 块" % end)
        time.sleep(0.35)


def doc_url(doc, tok):
    """查询文档的真实访问地址（不同企业的飞书域名不一样）"""
    r = req("POST", "/drive/v1/metas/batch_query",
            {"request_docs": [{"doc_token": doc, "doc_type": "docx"}], "with_url": True}, token=tok)
    metas = (r.get("data") or {}).get("metas") or []
    return metas[0].get("url") if metas else None


def run(md_path, title, replace=None, folder=None, owner=None, link=None):
    tok = get_token()
    if replace:
        doc = replace
        print("就地重刷文档：", doc)
        clear_doc(doc, tok)
    else:
        body = {"title": title}
        if folder:
            body["folder_token"] = folder
        r = req("POST", "/docx/v1/documents", body, token=tok)
        if r.get("code") != 0:
            sys.exit("新建文档失败：%s" % json.dumps(r, ensure_ascii=False))
        doc = r["data"]["document"]["document_id"]
        print("已新建文档：", doc)

    with open(md_path, encoding="utf-8") as f:
        tops, desc = parse(f.read())

    batches = make_batches(tops, desc)
    for k, (chunk, blocks) in enumerate(batches):
        payload = {"children_id": chunk, "index": -1, "descendants": blocks}
        res = req("POST", f"/docx/v1/documents/{doc}/blocks/{doc}/descendant",
                  payload, token=tok)
        if res.get("code") != 0:
            sys.exit("写入失败 批次%d/%d：%s" % (k + 1, len(batches),
                                              json.dumps(res, ensure_ascii=False)[:600]))
        time.sleep(0.35)
    print("已写入 %d 批内容" % len(batches))

    if link:
        perm = req("PATCH", f"/drive/v2/permissions/{doc}/public?type=docx",
                   {"link_share_entity": link}, token=tok)
        print("链接分享：", "已设置为 " + link if perm.get("code") == 0
              else json.dumps(perm, ensure_ascii=False)[:200])

    if owner:
        t = req("POST", f"/drive/v1/permissions/{doc}/members/transfer_owner"
                        "?type=docx&need_notification=true&remove_old_owner=false",
                {"member_type": "email", "member_id": owner}, token=tok)
        print("转移所有者：", "已转给 " + owner if t.get("code") == 0
              else json.dumps(t, ensure_ascii=False)[:300])

    print("文档地址：", doc_url(doc, tok) or "（未查到，可在飞书里搜索标题；文档 ID：%s）" % doc)
    return doc


def main(argv=None):
    p = argparse.ArgumentParser(prog="md2feishu", description="把 Markdown 转成飞书云文档")
    p.add_argument("markdown", help="要转换的 .md 文件")
    p.add_argument("title", nargs="?", default="", help="文档标题（默认用文件名）")
    p.add_argument("--replace", metavar="DOC_ID",
                   help="清空并重写已有文档（保留网址；注意：会冲掉别人在飞书里的手动修改）")
    p.add_argument("--folder", metavar="FOLDER_TOKEN", help="新建到指定云空间文件夹（应用需有该文件夹权限）")
    p.add_argument("--owner", metavar="EMAIL", help="写完后把文档所有者转给这个邮箱对应的飞书用户")
    p.add_argument("--link", choices=["tenant_readable", "tenant_editable"],
                   help="开启链接分享：组织内可读 / 组织内可编辑（默认不改）")
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    a = p.parse_args(argv)
    title = a.title or os.path.splitext(os.path.basename(a.markdown))[0]
    run(a.markdown, title, replace=a.replace, folder=a.folder, owner=a.owner, link=a.link)


if __name__ == "__main__":
    main()
