# md2feishu

**把 Markdown 一键变成飞书云文档。** 让 AI 写完的东西，直接进飞书。

```bash
python3 md2feishu.py 周报.md "第 44 周周报"
# 已新建文档： Xxxxxx
# 已写入 1 批内容
# 文档地址： https://xxx.feishu.cn/docx/Xxxxxx
```

<!-- 效果图：assets/效果对比.png（阶段 3 实测后补） -->

## 为什么做这个

用 Claude、ChatGPT、Codex 这类 AI 写周报、方案、会议纪要时，它们产出的都是 Markdown。
而团队日常在飞书里协作。手动复制粘贴，表格会散架、格式要重调；飞书自带的导入要点好几步，还不能被脚本调用。

md2feishu 就是中间那根管子：**一条命令，格式完整地变成飞书文档**，也可以交给 AI 在写完后自己调用。

## 特点

- **零依赖**：只用 Python 自带的库，不用 `pip install` 任何东西
- **表格不散架**：Markdown 表格转成飞书原生表格；大表格会自动分批写入，避开飞书单次 1000 块的上限
- **常用格式全覆盖**：1–6 级标题、有序/无序列表、待办勾选框、引用、代码块、分割线、加粗、行内代码、链接
- **能交给人**：机器人建的文档默认归机器人，用 `--owner` 一键转给你自己
- **能就地更新**：用 `--replace` 重写已有文档，网址不变

## 快速开始

### 1. 准备飞书应用（一次性，约 10 分钟）

md2feishu 通过飞书开放平台的「自建应用」来建文档，所以要先有一个应用，拿到它的两把钥匙。

1. 打开 [飞书开放平台](https://open.feishu.cn/app)，点 **创建企业自建应用**，名字随便起，比如「md2feishu」
2. 进入应用 → **凭证与基础信息**，记下 **App ID** 和 **App Secret**
3. 进入 **权限管理**，按中文名搜索并开通下面两项（括号里的代码名仅供参考，以开放平台页面为准）：
   - **创建及编辑新版文档**（`docx:document`）
   - **查看、评论、编辑和管理云空间中所有文件**（`drive:drive`）—— 用于转移所有者、查文档网址、设分享
4. 进入 **版本管理与发布**，创建版本并申请发布（企业版需要管理员审批）

> 没有企业飞书？可以免费注册一个个人团队，自己就是管理员，审批秒过。

### 2. 设置钥匙

```bash
export FEISHU_APP_ID=cli_xxxxxxxx
export FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
```

想每次打开终端都自动生效，就把这两行加进 `~/.zshrc`（Mac）或 `~/.bashrc`（Linux）。
**钥匙不要写进代码、不要传到 GitHub。**

国际版 Lark 用户再加一行：`export FEISHU_BASE_URL=https://open.larksuite.com/open-apis`

### 3. 运行

```bash
git clone https://github.com/linlywu9-sketch/md2feishu.git
cd md2feishu
python3 md2feishu.py examples/示例.md --owner 你的飞书邮箱@example.com
```

要求 Python 3.7 及以上（Mac 自带的就可以）。

## 用法

```text
python3 md2feishu.py <文件.md> [标题] [选项]
```

| 选项 | 作用 |
|---|---|
| `标题` | 文档标题，不填就用文件名 |
| `--owner 邮箱` | 写完后把文档所有者转给这个邮箱的飞书用户，文档会出现在 TA 的云空间里 |
| `--folder 文件夹token` | 建到指定的云空间文件夹（需先把应用加为该文件夹的协作者；此项未经充分测试） |
| `--link tenant_readable` | 开启链接分享：组织内获得链接的人可阅读（`tenant_editable` 为可编辑） |
| `--replace 文档ID` | 清空并重写已有文档，网址不变 |

> ⚠️ **`--replace` 会清空整篇文档再重写**，别人在飞书里手动改过的内容会被冲掉。
> 文档已经发出去、有人在上面改过时，不要用它。

### 让 AI 帮你调用

在 Claude Code、Codex 等 AI 编程工具的项目说明里加一句：

```text
写完 Markdown 文档后，用 `python3 /路径/md2feishu.py <文件> <标题> --owner 我的邮箱` 发到飞书，并把文档地址告诉我。
```

## 局限

目前**不支持**：图片、嵌套列表（会拉平成一级）、斜体和删除线、表格内换行、代码块的语言高亮（统一按纯文本显示）。

## 测试

```bash
python3 -m unittest discover tests
```

测试只验证 Markdown 解析和分批逻辑，不会连接飞书。

## 授权

[MIT](LICENSE)：可以免费使用、修改、商用，保留原作者署名即可。

---

作者：**静水深流AI** —— 一个用 AI 重做 HR 工作的实践者。欢迎在公众号「静水深流AI」交流。
