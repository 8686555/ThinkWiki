# llm-wiki

`llm-wiki` 是一个符合 Agent Skills 规范的本地 Markdown 知识库 skill。

它的目标不是做一个复杂的知识平台，而是提供一套真正可运行的脚本闭环，让 Agent 可以在本地完成这些动作：

- 初始化 wiki 工作区
- 导入 Markdown、DOCX、PDF、网页到知识库
- 基于已有知识页回答问题
- 将高价值内容沉淀为 `query / synthesis / decision / concept`
- 生成图谱和本地浏览页
- 检查依赖、结构和摘要质量

推荐用法：

- 安装为 skill 后，优先直接通过 Agent 对话来使用 `llm-wiki`
- README 里的命令主要用于调试、排错和宿主集成参考
- 对最终用户来说，通常不需要手动记住这些底层命令

## 适用场景

适合：

- 个人知识库
- 项目文档知识管理
- 研究资料整理
- 本地 wiki 问答与沉淀
- 为 OpenClaw、Hermes Agent、Claude Code、Trae 等支持 Agent Skills 的宿主提供知识管理能力

不适合：

- 多租户企业知识平台
- 复杂在线协作与权限系统
- 任务流转或项目管理系统本身

## 当前能力

- 导入 Markdown、PDF、DOCX、网页与公众号文章
- 生成本地知识页、综合页、概念页、决策页
- 基于已有知识页做证据优先问答
- 生成图谱、本地浏览页，并做运行时与结构体检

## 目录结构

仓库结构：

```text
llm-wiki/
├── README.md
├── SKILL.md
├── requirements.txt
├── scripts/
└── templates/
```

知识库工作区结构：

```text
<wiki-root>/
├── raw/
├── normalized/
├── wiki/
├── output/
├── .wiki-schema.md
├── index.md
├── overview.md
├── purpose.md
└── log.md
```

## 安装方式

### 作为 Agent Skills 使用

`llm-wiki` 的真实使用方式是把它作为一个 Skill 安装到支持 Agent Skills 的宿主里。

适用宿主包括但不限于：

- Trae
- Claude Code
- OpenClaw
- Hermes Agent
- 其他支持本地 Agent Skills 目录的宿主

通用安装原则：

- 保留整个 `llm-wiki` 仓库目录，不要只复制单个脚本
- 把仓库放到宿主约定的 skills 目录中
- 实际执行入口统一是 `<python-command> scripts/llm-wiki <command> ...`
- 首次运行时让 `llm-wiki` 自己完成 `.venv` 自举和依赖安装

其中：

- 文中的 `<python-command>` 在 macOS / Linux 上通常是 `python3`
- 文中的 `<python-command>` 在 Windows 上通常是 `python`
- macOS / Linux 通常使用 `python3`
- Windows 通常使用 `python`

以 Trae 为例，典型结构如下：

```text
<workspace>/.trae/skills/
└── llm-wiki
```

如果你通过 Git 拉取源码，推荐直接克隆到宿主的 skills 目录，例如：

```bash
git clone https://github.com/wzdavid/llm-wiki llm-wiki
cd llm-wiki
<python-command> scripts/llm-wiki bootstrap
<python-command> scripts/llm-wiki doctor --repo-root .
```

说明：

- 首次执行 `bootstrap` 时会在仓库内自动创建 `./.venv`
- 这个本地运行环境仅供 `llm-wiki` 自己使用，不需要手动激活
- `.venv/` 已加入仓库忽略规则，不应提交到 Git
- 对用户来说，只需要安装 `llm-wiki` 这一个 skill

## 运行依赖

基础依赖：

- `python`
- `venv`

平台说明：

- 当前支持 macOS、Linux 和 Windows
- Windows 可以直接用 `PowerShell` 或 `cmd` 运行，但前提是系统里有可用的 `python`
- macOS / Linux 通常使用 `python3 scripts/llm-wiki ...`
- Windows 通常使用 `python scripts/llm-wiki ...`

运行方式：

- `llm-wiki` 首次运行会自动创建仓库内的 `.venv`
- 运行库会安装到 `llm-wiki/.venv`
- 后续命令默认都通过这个本地运行环境执行

核心运行库：

- `markitdown`
- `beautifulsoup4`
- `markdownify`

根目录 `requirements.txt` 是运行时自举的正式依赖声明，`bootstrap_runtime.py` 会直接读取它来安装本 skill 所需的 Python 运行库。

这些运行库现在作为 `llm-wiki` 自身实现的一部分使用，不再要求用户安装额外 skill，也不要求用户手动 `pip install`。

如果你想显式预热运行环境，可执行：

```bash
<python-command> scripts/llm-wiki bootstrap
```

如果你直接运行 `init / ingest / ask / digest / crystallize` 等命令，`llm-wiki` 也会先自动尝试完成这一步。

## 实现要点

- `llm-wiki` 是单一 skill，不依赖其他 companion skills
- 统一入口是 `scripts/llm-wiki`，由当前 Python 解释器直接调用
- 首次运行会自动创建仓库内 `.venv`，并从根目录 `requirements.txt` 安装运行库
- 文件系统和 Markdown 是真相源，索引和派生内容都可重建
- 本地办公文档转换直接调用 `markitdown` Python 包
- 网页转换由 Python 抓取、`BeautifulSoup` 和 `markdownify` 完成
- `ask`、`digest`、`crystallize` 尽量保留来源与证据片段
- 当前支持 macOS、Linux、Windows，不要求 `bash` 作为唯一入口

## 快速开始

安装好 skill 之后，推荐直接通过 Agent 对话来使用 `llm-wiki`，而不是先手动记命令。

最自然的使用方式通常是：

1. 先告诉 Agent 你的知识库在哪里，或者让它帮你初始化一个新的知识库
2. 再让 Agent 导入 PDF、DOCX、Markdown、网页或公众号文章
3. 然后直接围绕这个知识库提问、沉淀总结、生成概念页或决策页

可以直接对 Agent 这样说：

- “帮我在 `<wiki-root>` 初始化一个项目知识库，名字叫 `My Wiki`”
- “把这个 PDF 导入到知识库里：`<file.pdf>`”
- “把这个网页整理进知识库：`https://example.com/article`”
- “基于当前知识库，回答：AI 原生团队的核心定义是什么？”
- “把这次问答沉淀成一篇 concept 页面”

如果宿主支持工具自动调用，Agent 会直接使用 `llm-wiki` 完成这些动作；对最终用户来说，通常不需要手动输入底层命令。

## 命令参考

下面这些命令主要用于：

- 手动调试
- 宿主集成排查
- 不通过对话而直接运行脚本

### 初始化知识库

```bash
<python-command> scripts/llm-wiki bootstrap
<python-command> scripts/llm-wiki init --root <wiki-root> --title "My Wiki"
```

### 导入本地 Markdown

```bash
<python-command> scripts/llm-wiki ingest --root <wiki-root> --source <source-file>
```

### 只做转换，不入库

```bash
<python-command> scripts/llm-wiki convert --source <source-file> --output-file <output-file>
<python-command> scripts/llm-wiki convert --url "https://example.com/article" --output-file <output-file>
```

### 导入 PDF / DOCX

```bash
<python-command> scripts/llm-wiki ingest --root <wiki-root> --source <file.pdf>
<python-command> scripts/llm-wiki ingest --root <wiki-root> --source <file.docx>
```

### 导入网页

```bash
<python-command> scripts/llm-wiki ingest --root <wiki-root> --url "https://example.com/article"
```

### 基于已有知识提问

```bash
<python-command> scripts/llm-wiki ask --root <wiki-root> --question "AI原生团队的核心定义是什么？"
```

### 生成综合页

```bash
<python-command> scripts/llm-wiki digest \
  --root <wiki-root> \
  --title "AI原生团队与组织演化" \
  --source-path wiki/sources/a.md \
  --source-path wiki/sources/b.md
```

### 生成概念页或决策页

```bash
<python-command> scripts/llm-wiki crystallize \
  --root <wiki-root> \
  --kind concept \
  --title "AI原生团队" \
  --source-path wiki/sources/a.md
```

## 推荐使用方式

对 Agent 来说，推荐默认流程是：

1. 确定 wiki 根目录
2. 用 `ingest` 导入资料
3. 用 `ask` 做基于证据的回答
4. 对高价值结果再调用 `query / digest / crystallize`
5. 定期运行 `lint` 和 `doctor`

## License

MIT
