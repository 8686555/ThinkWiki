# ThinkWiki

[![Release](https://img.shields.io/github/v/release/wzdavid/ThinkWiki?sort=semver)](https://github.com/wzdavid/ThinkWiki/releases)
[![License](https://img.shields.io/github/license/wzdavid/ThinkWiki)](LICENSE)
[![Python](https://img.shields.io/badge/python-3-blue.svg)](https://www.python.org/)

ThinkWiki 是一个 **面向 Agent 的本地知识库 Skill**。你只需要和 Agent 对话，就能把网页、文档、笔记和对话持续沉淀成可追溯的 Markdown 知识空间，并生成可在浏览器中打开的 Inbox、浏览页和内容知识图谱。

English version: [README.md](README.md)

代码库：**https://github.com/wzdavid/ThinkWiki**

## 适用于支持 Agent Skills 的智能体

ThinkWiki 遵循开放的 [Agent Skills](https://agentskills.io) 规范（`SKILL.md` + 脚本目录）。只要你的 Agent 能安装 Skill 并在本机执行命令，就可以使用 ThinkWiki。

你 **不需要记住 CLI 命令**。安装一次 Skill 之后，创建和管理知识库都可以通过对话完成。

| Agent / 宿主 | 典型用法 |
| --- | --- |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | 将仓库安装为 Skill，在对话中构建和查询知识库 |
| [OpenClaw](https://openclaw.ai) | 完整 Skill 工作流；可用 `serve` + 内置 browser 打开 HTML 成果页 |
| [Trae](https://www.trae.ai) | 安装到 `.trae/skills`，在对话中管理 wiki |
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | 本地 Skill 目录 + shell 执行 |
| [OpenAI Codex](https://developers.openai.com/codex) / Codex CLI | 支持 Skills 的本地编码 Agent |
| [Cursor](https://cursor.com) | Agent 模式 + 项目 Skill |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | 支持 Skills 的 CLI Agent |
| [GitHub Copilot](https://github.com/features/copilot) | VS Code 中支持 Skills 的 Agent / 编码工作流 |
| 其他 Skills 宿主 | 只要能加载 `SKILL.md` 并在本机运行 `python3 scripts/thinkwiki ...` |

**前提：** 本机有 Python 3 环境。ThinkWiki 会在首次使用时自动 bootstrap 运行时。纯云端对话、无法访问本机文件或 shell 的环境无法运行本地知识库。

## 快速开始：用对话安装

把下面这个代码库地址发给你的 Agent，请它帮你安装并验证环境。

**示例说法：**

> 请帮我安装 ThinkWiki 这个 Skill，代码库地址是 https://github.com/wzdavid/ThinkWiki ，完成 bootstrap 并检查一下本机环境是否可用。

Agent 通常会把 Skill 安装到宿主对应的 skills 目录，执行 `bootstrap` 和 `doctor` 做自检。一般情况下你不必自己敲这些命令，除非你希望手动安装。

**安装完成后，直接开始用：**

> 帮我在工作区创建一个名为 `My Wiki` 的本地知识库。

> 先把这篇文章收进 inbox：`https://example.com/article`

> 把这个 PDF 导入知识库：`/path/to/file.pdf`

> 根据我的 wiki 回答：我们之前对 context budget 做过什么决定？

> 生成知识图谱，并在浏览器里打开工作台首页。

Agent 会读取 `SKILL.md`，把你的意图映射成稳定的 ThinkWiki 动作，并告诉你 Markdown 页面和 HTML 成果页的位置。

## 为什么用 ThinkWiki

- **Agent-first：** 用户主要通过和 Agent 对话来使用，不需要记很多命令。
- **Local-first：** Markdown 文件仍然是真相源，数据留在本机。
- **HTML-first：** Inbox、Viewer、Graph、Governance 都是可浏览的真实工作界面。
- **Knowledge-first：** 图谱是内容知识图谱，而不只是文件链接图。

## 会生成什么

ThinkWiki 会生成这些核心成果页：

- `output/index.html`：统一工作台首页
- `output/inbox/index.html`：Inbox 复核页
- `output/viewer/index.html`：本地浏览页
- `output/graph/index.html`：交互式知识图谱页
- `output/graph/report.html`：图谱治理报告页
- `output/graph/entity-merge-review.html`：实体归并复核页
- `output/graph/entity-merge-plan.html`：实体归并 dry-run 预演页

### 界面预览

#### 工作台首页（`output/index.html`）

统一工作台首页，汇总最近变更、推荐下一步操作、Inbox 待办和图谱快照，方便你决定先阅读、入库还是进入图谱。

![ThinkWiki 工作台首页预览](docs/assets/output-hub-preview.png)

#### Inbox 复核页（`output/inbox/index.html`）

在正式 ingest 前复核已采集的网页、文件和笔记。条目按 `ready / review / weak` 分组，优先处理价值最高的内容。

![ThinkWiki Inbox 复核页预览](docs/assets/inbox-preview.png)

#### 本地浏览页（`output/viewer/index.html`）

按页面类型、置信度和状态浏览整个 wiki，可直接在本地 HTML 工作区中打开任意页面阅读。

![ThinkWiki 本地浏览页预览](docs/assets/viewer-preview.png)

#### 知识图谱页（`output/graph/index.html`）

交互式内容知识图谱。可在 `knowledge / document / suggested` 三种视图间切换，查看语义关系和候选边。

![ThinkWiki 知识图谱页预览](docs/assets/graph-preview.png)

#### 图谱治理报告（`output/graph/report.html`）

查看孤立页面、高连接薄页、脆弱桥接、建议补链和实体归并候选等图谱健康信号，再决定是否调整知识结构。

![ThinkWiki 图谱治理报告预览](docs/assets/graph-report-preview.png)

## 日常怎么说（自然语言对照）

安装 ThinkWiki 之后，最常见的用法就是直接说人话：

| 你可以说 | ThinkWiki 会做什么 |
| --- | --- |
| 创建一个叫 `Research Notes` 的知识库 | 初始化本地 wiki 工作区 |
| 把这篇 URL / 文件先收进 inbox | 采集内容，等待复核 |
| 把 ready 的 inbox 条目正式入库 | 生成 wiki 页面 |
| 我的 wiki 里关于 X 是怎么说的？ | 基于已有页面做证据优先问答 |
| 把这个回答保存成 query 页 | 沉淀高价值输出 |
| 帮我看看知识图谱 | 构建/刷新图谱 HTML |
| 复核 entity merge 候选 | 展示 alias 冲突，等待确认 |
| 在浏览器里打开 wiki 工作台 | 启动 `serve`，返回 `http://127.0.0.1:8765/index.html` |

## 核心能力

- 初始化本地 wiki 工作区
- 先采集到 inbox，再决定是否正式入库
- 导入 Markdown、PDF、DOCX、XLSX、XLS、PPTX、网页和文本
- 基于已有知识页做证据优先问答
- 沉淀 `query / synthesis / decision / concept` 页面
- 生成 `knowledge / document / suggested` 三种图谱视图
- 做 entity alias 冲突复核和确定性归并
- 检查运行环境、工作区状态和图谱治理状态

## 内容知识图谱

在 `v1.6.0` 中，ThinkWiki 默认生成 `schema v2` 的内容知识图谱，默认视图是 `knowledge`。

知识图谱里可以包含：

- `source`、`topic`、`concept`、`decision`、`synthesis`、`query`、`entity` 等页面节点
- 从结构化内容里抽取出的 `claim` 节点
- `about`、`belongs_to`、`depends_on`、`asserts`、`supports`、`contradicts`、`suggests_related_to` 等语义关系

因此它已经不是单纯的文件关系图，而是可以表达知识结构、证据结构和实体治理的内容图谱。

## 浏览 HTML 成果页

Agent 对话界面通常无法直接渲染 ThinkWiki 的 HTML 页面。需要查看 Inbox、Viewer、Graph 或治理报告时，可以直接对 Agent 说：

> 启动 ThinkWiki 的输出服务，并把工作台 URL 给我。

或自行运行：

```bash
python3 scripts/thinkwiki serve --root /path/to/my-wiki
```

默认会在 `http://127.0.0.1:8765/` 提供 `<wiki-root>/output/` 目录。建议从 `http://127.0.0.1:8765/index.html` 进入工作台首页。

在 **OpenClaw** 中，`serve` 启动后 Agent 也可以用内置 browser 打开：

```bash
openclaw browser --browser-profile openclaw open http://127.0.0.1:8765/index.html
```

在其他 Agent 上，用系统浏览器打开同一 URL，或使用宿主提供的 browser 工具即可。

如果只需要 URL 列表、不想启动常驻服务，可使用 `serve --print-urls`。

## 环境变量

ThinkWiki 的部分功能需要 API key：

| 变量 | 必需 | 用途 |
|------|------|------|
| `MINIMAX_API_KEY` | 否（可选） | MiniMax M2.7 内容生成；未设置则回退到启发式算法 |
| `SILICONFLOW_API_KEY` | 否（可选） | SiliconFlow 免费 BGE-M3 embedding，用于实体归并去重；不设置则退化为纯字符串匹配 |

`MINIMAX_API_KEY` 未设置时 `crystallize` 和 `digest` 会优雅回退到启发式算法。`SILICONFLOW_API_KEY` 可在 https://siliconflow.cn 免费注册获取。

## 手动安装（可选）

如果你希望自己安装，而不是让 Agent 代劳：

```bash
git clone https://github.com/wzdavid/ThinkWiki ThinkWiki
cd ThinkWiki
python3 scripts/thinkwiki bootstrap
python3 scripts/thinkwiki doctor --repo-root .
```

然后按你所用 Agent 的文档，把该目录安装到对应的 skills 目录中。

## CLI 参考（给 Agent 和进阶用户）

ThinkWiki 在底层保持一个统一入口，Agent 会在背后调用它：

```bash
python3 scripts/thinkwiki <command> [args]
```

常见命令：`init`、`clip`、`ingest`、`inbox`、`viewer`、`graph`、`graph-report`、`entity-merge-review`、`entity-merge-apply`、`serve`、`health`、`status`、`doctor`。

完整意图映射见 `SKILL.md`。

## 仓库文档

- `README.md`：英文项目总览
- `README.zh.md`：中文说明
- `SKILL.md`：面向 Agent 宿主的 skill 约定
- `CHANGELOG.md`：版本记录

## License

MIT
