# ThinkWiki

[![Release](https://img.shields.io/github/v/release/wzdavid/ThinkWiki?sort=semver)](https://github.com/wzdavid/ThinkWiki/releases)
[![License](https://img.shields.io/github/license/wzdavid/ThinkWiki)](LICENSE)
[![Python](https://img.shields.io/badge/python-3-blue.svg)](https://www.python.org/)

`ThinkWiki` 是一个符合 Agent Skills 规范的本地 Markdown 知识库 skill。它帮助 Agent 持续整理、沉淀、查询和可视化你的知识库，而不是每次都从原始资料重新推导。

它现在不只会生成浏览页和图谱页，还会生成确定性的 `graph-report`，把 `Key Pages`、`Bridge Pages`、`Pages That Need Links`、`Suggested Links`、`hub stubs` 和 `isolated clusters` 收敛成普通用户也能直接打开的治理结果。

它适合这样的场景：

- 你想把 PDF、网页、笔记和对话持续沉淀成可复用的本地知识库
- 你希望 Agent 不只是“一次问答”，而是持续产出 `query / synthesis / decision / concept`
- 你需要可以直接打开的浏览页和知识图谱，而不是只得到 JSON 或终端输出
- 你希望整个能力仍然以一个简单的 skill 交付，而不是额外拼很多安装步骤

一句话理解：

- `ThinkWiki = 本地 Markdown 知识库 + Agent Skill 原生入口 + 可直接打开的 Inbox / Viewer / Graph 成果页`

## 效果预览

下面这五张样例图展示了 `ThinkWiki` 生成后的五个核心成果页：

- 知识工作台首页：用户最容易直接打开的统一入口，也会展示当前 wiki 的页面规模、最近变化、图谱状态和下一步建议
- Inbox Review 页：按 `ready / review / weak` 分组复核采集内容，并直接复制下一步 ingest 命令
- 浏览页：适合按页面类型、状态、置信度浏览整个 wiki
- 图谱页：适合查看页面之间的引用、包含和链接关系，也会直接给出图谱洞察和补链建议
- 图谱治理报告页：适合直接查看孤立页面、脆弱桥接、孤立子图和 top graph fixes
- 这五张图都来自仓库内 `docs/demo-wiki` 的真实输出，而不是手工绘制的示意图
- 如需重新生成 README 截图，可执行：`python3 scripts/capture_readme_screenshots.py`

### 成果入口页样例

![ThinkWiki Output Hub Preview](docs/assets/output-hub-preview.png)

### Inbox Review 页样例

![ThinkWiki Inbox Preview](docs/assets/inbox-preview.png)

### 浏览页样例

![ThinkWiki Viewer Preview](docs/assets/viewer-preview.png)

### 图谱页样例

![ThinkWiki Graph Preview](docs/assets/graph-preview.png)

### 图谱治理报告页样例

![ThinkWiki Graph Report Preview](docs/assets/graph-report-preview.png)

## 30 秒上手

安装好 `ThinkWiki` 之后，最自然的使用方式通常是直接通过 Agent 对话来使用它。

你可以直接对 Agent 这样说：

- “帮我初始化一个知识库，名字叫 `My Wiki`”
- “先把这个网页收进 inbox，稍后我再决定要不要正式入库：`https://example.com/article`”
- “把这个 PDF 导入到知识库里：`/path/to/file.pdf`”
- “把这个网页整理进知识库：`https://example.com/article`”
- “基于当前知识库回答：AI 原生团队的核心定义是什么？”
- “帮我生成一个本地知识图谱，我想可视化看看”

如果宿主支持工具自动调用，Agent 会直接使用 `ThinkWiki` 完成这些动作；对最终用户来说，通常不需要手动记住底层命令。

## 它能做什么

- 初始化本地 wiki 工作区
- 先把网页、文件和临时文本采集到 `inbox`
- 导入 Markdown、PDF、DOCX、XLSX、XLS、PPTX、网页和文本
- 基于已有知识页做证据优先问答
- 将高价值结果沉淀为 `query / synthesis / decision / concept`
- 生成本地浏览页和离线知识图谱
- 在图谱页识别关键页面、桥接页面、弱连接页面和建议补链
- 检查运行时依赖、结构和链接健康度

## Graph Insights

`ThinkWiki` 的图谱页不只是把页面节点画出来，它还会在右侧直接给出结构洞察：

- `Key Pages`：当前知识库里最关键、最值得先读的页面
- `Bridge Pages`：连接多个主题区域的桥接页面
- `Pages That Need Links`：还比较孤立或关系太弱的页面
- `Suggested Links`：基于关键词、来源和邻接关系给出的补链建议

这让 `output/graph/index.html` 更像一个知识图谱探索器，而不只是静态关系图。

## 为什么适合作为 Agent Skill

`ThinkWiki` 的目标就是作为一个完整 skill 被安装和使用，而不是依赖额外 companion skills 或复杂安装器。

- 整个仓库就是一个 skill
- 统一入口是 `scripts/thinkwiki`
- 首次运行时会自举仓库内 `.venv`
- 运行依赖来自仓库内 `requirements.txt`
- 支持 macOS、Linux 和 Windows
- 不要求用户理解内部脚本结构
- 不要求前端工程或服务端环境

对宿主来说，只需要安装 `ThinkWiki` 这一个 skill；对用户来说，只需要围绕知识库说自然语言需求。

## 你会得到什么

一个典型知识库会长成这样：

```text
<wiki-root>/
├── raw/
├── normalized/
├── wiki/
│   ├── sources/
│   ├── topics/
│   ├── concepts/
│   ├── decisions/
│   ├── syntheses/
│   └── queries/
├── output/
│   ├── inbox/
│   │   └── index.html
│   ├── graph/
│   │   ├── graph.json
│   │   ├── graph.md
│   │   ├── report.json
│   │   ├── report.md
│   │   └── index.html
│   ├── viewer/
│       ├── viewer.json
│       └── index.html
│   └── index.html
├── .wiki-schema.md
├── index.md
├── overview.md
├── purpose.md
└── log.md
```

其中：

- `wiki/` 保存沉淀后的知识页面
- `output/viewer/index.html` 是本地浏览页
- `output/graph/index.html` 是本地知识图谱
- `output/graph/report.html` 是图谱治理报告页
- `output/graph/report.md` 是同一份报告的 Markdown 归档版本
- `output/inbox/index.html` 是待处理采集内容的复核页
- `output/index.html` 是统一知识工作台首页
- 这些成果都可以直接在浏览器打开查看

## 和普通 RAG 的区别

`ThinkWiki` 更强调“持续沉淀”而不是“一次问答”：

- Markdown 和文件系统是本地真相源
- 来源、摘要、证据和派生页面都可追溯
- 索引和派生内容都可重建
- 可以直接离线浏览页面和图谱

## 安装方式

### 作为 Agent Skills 使用

`ThinkWiki` 的真实使用方式是把它作为一个 skill 安装到支持 Agent Skills 的宿主里。

适用宿主包括但不限于：

- Trae
- Claude Code
- OpenClaw
- Hermes Agent
- 其他支持本地 Agent Skills 目录的宿主

通用安装原则：

- 保留整个 `ThinkWiki` 仓库目录，不要只复制单个脚本
- 把仓库放到宿主约定的 skills 目录中
- 实际执行入口统一是 `<python-command> scripts/thinkwiki <command> ...`
- 首次运行时让 `ThinkWiki` 自己完成 `.venv` 自举和依赖安装

以 Trae 为例，典型结构如下：

```text
<workspace>/.trae/skills/
└── ThinkWiki
```

如果你通过 Git 拉取源码，推荐直接克隆到宿主的 skills 目录，例如：

```bash
git clone https://github.com/wzdavid/ThinkWiki ThinkWiki
cd ThinkWiki
<python-command> scripts/thinkwiki bootstrap
<python-command> scripts/thinkwiki doctor --repo-root .
```

说明：

- 首次执行 `bootstrap` 时会在仓库内自动创建 `./.venv`
- 这个本地运行环境仅供 `ThinkWiki` 自己使用，不需要手动激活
- `.venv/` 已加入仓库忽略规则，不应提交到 Git
- 对用户来说，只需要安装 `ThinkWiki` 这一个 skill

其中：

- 文中的 `<python-command>` 在 macOS / Linux 上通常是 `python3`
- 文中的 `<python-command>` 在 Windows 上通常是 `python`

## 快速开始

```bash
<python-command> scripts/thinkwiki bootstrap
<python-command> scripts/thinkwiki init --root <wiki-root> --title "My Wiki"
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://example.com/article"
<python-command> scripts/thinkwiki inbox --root <wiki-root>
<python-command> scripts/thinkwiki batch-clip --root <wiki-root> --source-dir <import-dir> --dry-run
<python-command> scripts/thinkwiki batch-ingest --root <wiki-root> --quality ready --dry-run
<python-command> scripts/thinkwiki health --root <wiki-root>
<python-command> scripts/thinkwiki status --root <wiki-root>
<python-command> scripts/thinkwiki ingest --root <wiki-root> --source <file.pdf>
<python-command> scripts/thinkwiki ask --root <wiki-root> --question "AI原生团队的核心定义是什么？"
<python-command> scripts/thinkwiki viewer --root <wiki-root>
<python-command> scripts/thinkwiki graph --root <wiki-root>
<python-command> scripts/thinkwiki graph-report --root <wiki-root>
```

生成后可直接打开：

- `output/index.html`
- `output/inbox/index.html`
- `output/viewer/index.html`
- `output/graph/index.html`
- `output/graph/report.html`

如果你只记一个入口，优先记住：

- `output/index.html`

## 常见任务

### 导入文件或网页

```bash
<python-command> scripts/thinkwiki ingest --root <wiki-root> --source <source-file>
<python-command> scripts/thinkwiki ingest --root <wiki-root> --url "https://example.com/article"
```

### 先采集到 Inbox，再决定是否入库

```bash
<python-command> scripts/thinkwiki clip --root <wiki-root> --source <source-file>
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://example.com/article"
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://mp.weixin.qq.com/s/xxxxx" --adapter wechat
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://example.com/article" --mode wait --wait-seconds 8
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://example.com/article" --media always
<python-command> scripts/thinkwiki clip --root <wiki-root> --title "Quick Note" --text "# Quick Note\n\nSomething worth saving."
```

`clip` 会把内容先放进：

- `raw/inbox/`：保留原始文件、网页 HTML 或原始文本
- `normalized/inbox/`：保存清洗后的 Markdown，方便后续复核和正式 ingest

对于网页采集，`ThinkWiki` 还会额外写入：

- `normalized/inbox/*.json`：保存结构化网页元数据，例如 `adapter`、`siteName`、`author`、`publishDate` 和 `url`
- `output/inbox/index.html` 中的质量状态：`ready / review / weak`，帮助你快速判断哪些条目可以直接继续 ingest
- `output/inbox/index.html` 中的采集状态：例如 `ok / needs_review / wait_completed / wait_timeout`
- `output/inbox/index.html` 中的媒体状态：例如 `review_needed / localized / kept_remote`
- `output/inbox/index.html` 中的采集原因：例如 `loading_placeholder / body_too_short / metadata_sparse`

如果你已经知道来源站点类型，也可以显式指定：

```bash
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://mp.weixin.qq.com/s/xxxxx" --adapter wechat
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://example.com/article" --adapter generic
```

如果网页正文出现得比较慢，或者第一次抓到的内容还像加载占位页，也可以切到等待模式：

```bash
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://example.com/article" --mode wait --wait-seconds 8
```

`wait` 模式会在一个短时间窗口里轮询抓取页面，并把最终状态记录到 inbox metadata 里：

- `wait_completed`：等待后抓到了更完整的正文
- `wait_timeout`：等待已结束，但正文仍不够稳定，建议人工复核

除了状态，`ThinkWiki` 还会给网页采集写入更细的原因提示，例如：

- `loading_placeholder`：页面内容看起来还像加载占位
- `body_too_short`：正文过短，可能没抓到完整文章
- `sparse_structure`：抓到的结构过于稀疏，可能只是页头或摘要
- `metadata_sparse`：标题、作者、来源、发布时间等元数据过少

网页图片的处理策略也可以直接指定：

```bash
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://example.com/article" --media ask
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://example.com/article" --media always
<python-command> scripts/thinkwiki clip --root <wiki-root> --url "https://example.com/article" --media never
```

- `ask`：先保留远程图片链接，并在 inbox review 中标记为后续复核
- `always`：直接下载图片到 `normalized/assets/inbox/...`，并把 Markdown 引用改写成本地相对路径
- `never`：保留远程图片链接，不做本地化

### 检查当前工作区状态

```bash
<python-command> scripts/thinkwiki health --root <wiki-root>
<python-command> scripts/thinkwiki status --root <wiki-root>
<python-command> scripts/thinkwiki graph-report --root <wiki-root>
```

- `health`：做确定性检查，提示缺失目录、失效 inbox metadata、以及过期的 viewer / graph / inbox 输出
- `status`：快速汇总页面数、inbox ready/review/weak 数量，以及当前成果页是否已生成
- `graph-report`：基于现有 `output/graph/graph.json` 生成 `output/graph/report.{json,md,html}`，汇总孤立页面、脆弱桥接、孤立子图和建议补链

生成 `graph-report` 之后：

- `status` 会额外显示 `Graph Report` 的生成状态和核心计数
- `health` 会提示 `graph-report` 是否缺失或过期
- `output/index.html` 会直接显示图谱治理摘要和 top actions

执行后，命令会直接打印下一步建议，例如：

```bash
python scripts/thinkwiki ingest --root <wiki-root> --source normalized/inbox/2026-06-20-quick-note.md
```

执行 `clip` 后，`ThinkWiki` 会自动更新 `output/inbox/index.html` 和 `output/index.html`，让工作台首页直接显示最新的 `Inbox Queue`。

### 批量采集到 Inbox

```bash
<python-command> scripts/thinkwiki batch-clip --root <wiki-root> --source-dir <import-dir> --dry-run
<python-command> scripts/thinkwiki batch-clip --root <wiki-root> --source-dir <import-dir>
<python-command> scripts/thinkwiki batch-clip --root <wiki-root> --manifest <clip-manifest.jsonl>
```

- `batch-clip` 适合把一个资料目录，或一组事先列好的 source / url / text 条目，一次性收进 inbox
- `--source-dir` 会递归扫描目录中的受支持文件格式，并批量生成 `raw/inbox` 与 `normalized/inbox` 条目
- `--manifest` 支持 JSON 数组或 JSONL，每条记录可提供一个 `source`、`url` 或 `text`，并可附带 `title`
- manifest 中的网页条目还支持 `adapter`、`mode`、`waitSeconds` 和 `media`，直接复用单条 `clip` 的网页采集能力
- `--dry-run` 会先列出本次准备采集的批次，确认后再正式执行
- 执行完成后会自动刷新 `output/inbox/index.html` 和 `output/index.html`，并直接提示下一步 `batch-ingest --dry-run`

一个最小 JSONL manifest 例子：

```json
{"source":"./docs/a.md","title":"Alpha Note"}
{"url":"https://example.com/article","title":"Example Article","mode":"wait","waitSeconds":8}
{"text":"# Quick Note\n\nSomething worth saving.","title":"Quick Note"}
```

### 批量处理 Ready Inbox

```bash
<python-command> scripts/thinkwiki batch-ingest --root <wiki-root> --quality ready --dry-run
<python-command> scripts/thinkwiki batch-ingest --root <wiki-root> --quality ready
<python-command> scripts/thinkwiki batch-ingest --root <wiki-root> --quality review --limit 3
```

- `batch-ingest` 默认优先处理 `ready` 条目，把 inbox 里的已复核内容批量正式入库
- `--dry-run` 先列出将要处理的条目，不改动任何文件
- `--limit` 适合先吃掉最上面的几条 ready 队列，而不是一次性清空
- 正式执行后，会清理已处理条目的 `normalized/inbox`、对应 metadata、`raw/inbox` 原始文件，以及相关本地化媒体目录
- 执行完成后会自动刷新 `output/inbox/index.html` 和 `output/index.html`，然后提示你重新生成 `viewer` / `graph`

### 查看 Inbox Review 页面

```bash
<python-command> scripts/thinkwiki inbox --root <wiki-root>
```

这个命令会生成：

- `output/inbox/index.html`：集中查看最近 clip 进来的条目
- 每条条目都带有清洗后的 Markdown 打开入口
- 网页条目会显示 `adapter / source / author / publish date` 等结构化元数据
- 网页条目会显示当前提取质量状态，并给出一条简短的复核建议
- 网页条目支持直接打开 sidecar metadata JSON，方便复核提取质量
- `ready` 分组会直接给出 `batch-ingest` 的 dry-run 和正式执行命令
- 每条条目都会直接显示下一步 `ingest` 命令，方便复制执行
- 工作台首页 `output/index.html` 也会同步刷新

对于微信公众号等技术文章，`ThinkWiki` 还会在网页转 Markdown 前先规范化常见的代码块容器，尽量保留更自然的代码内容，避免在 inbox review 阶段就丢失可读性。

### 只做转换，不入库

```bash
<python-command> scripts/thinkwiki convert --source <source-file> --output-file <output-file>
<python-command> scripts/thinkwiki convert --url "https://example.com/article" --output-file <output-file>
```

### 基于已有知识提问

```bash
<python-command> scripts/thinkwiki ask --root <wiki-root> --question "AI原生团队的核心定义是什么？"
```

### 生成综合页

```bash
<python-command> scripts/thinkwiki digest \
  --root <wiki-root> \
  --title "AI原生团队与组织演化" \
  --source-path wiki/sources/a.md \
  --source-path wiki/sources/b.md
```

### 生成概念页或决策页

```bash
<python-command> scripts/thinkwiki crystallize \
  --root <wiki-root> \
  --kind concept \
  --title "AI原生团队" \
  --source-path wiki/sources/a.md
```

### 生成浏览页和知识图谱

```bash
<python-command> scripts/thinkwiki viewer --root <wiki-root>
<python-command> scripts/thinkwiki graph --root <wiki-root>
```

## 运行依赖

基础依赖：

- `python`
- `venv`

平台说明：

- 当前支持 macOS、Linux 和 Windows
- Windows 可以直接用 `PowerShell` 或 `cmd` 运行，但前提是系统里有可用的 `python`
- macOS / Linux 通常使用 `python3 scripts/thinkwiki ...`
- Windows 通常使用 `python scripts/thinkwiki ...`

运行方式：

- `ThinkWiki` 首次运行会自动创建仓库内的 `.venv`
- 运行库会安装到 `ThinkWiki/.venv`
- 后续命令默认都通过这个本地运行环境执行

核心运行库：

- `markitdown`
- `beautifulsoup4`
- `markdownify`
- `mammoth`
- `pdfminer-six`
- `pdfplumber`
- `openpyxl`
- `pandas`
- `python-pptx`
- `xlrd`

根目录 `requirements.txt` 是运行时自举的正式依赖声明，`bootstrap_runtime.py` 会直接读取它来安装本 skill 所需的 Python 运行库。

`bootstrap` 会尝试安装完整的 Markdown、网页和办公文档转换依赖，并在默认包索引失败后自动回退到可配置镜像或官方 PyPI。

如果你所在环境需要指定镜像，可以设置：

```bash
export THINKWIKI_PIP_INDEX_URL="https://pypi.org/simple"
```

## 推荐使用方式

对 Agent 来说，推荐默认流程是：

1. 确定 wiki 根目录
2. 先用 `clip` 或 `ingest` 导入资料
3. 用 `inbox` 或 `output/index.html` 复核待处理采集内容
4. 用 `ask` 做基于证据的回答
5. 对高价值结果再调用 `query / digest / crystallize`
6. 用 `viewer` 和 `graph` 生成可直接查看的成果页
7. 定期运行 `lint` 和 `doctor`

其中：

- 如果资料还没确认是否值得正式沉淀，优先用 `clip` 先放进 `inbox`
- 如果资料已经明确要入库，直接用 `ingest`

## 运行体检

建议在首次安装或更换运行环境后执行：

```bash
<python-command> scripts/thinkwiki doctor --repo-root .
```

`doctor` 会输出以下能力状态：

- `Core runtime`
- `Web import`
- `PDF import`
- `DOCX import`
- `XLSX import`
- `XLS import`
- `PPTX import`

如果某一项显示 `missing ...`，说明对应格式尚不可用，需要重新执行 `bootstrap` 或检查包索引或网络环境。

## 版本与发布

版本更新记录见 `CHANGELOG.md`。

升级后建议关注：

- 是否新增输出文件
- 是否有命令行为调整
- 是否需要重新执行 `bootstrap`

## License

MIT
