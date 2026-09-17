<div align="center">

# LLM Master · 离线学习站

**大模型 / Agent / RAG / Transformer / AI 编程 · 173 篇教程与面试资料的网页版**

[![License: MIT](https://img.shields.io/badge/License-MIT-2f6feb.svg)](./LICENSE)
![Pages](https://img.shields.io/badge/pages-173-0f8a4d.svg)
![Offline](https://img.shields.io/badge/offline-100%25-9a6700.svg)

</div>

---

## 这是什么

一套**可直接在浏览器打开、点链接就能跳转**的静态站点。内容来自开源教程仓库
`llm-master` 的 173 篇 Markdown，经脚本渲染为镜像目录结构的 HTML 页面。

**为什么需要它**：直接用编辑器或浏览器插件打开 `.md` 时，Markdown 里的相对链接会被
渲染宿主解析到自身的源上（例如 `chrome-extension://<扩展ID>/src/...`），点哪都是 404。
转成 HTML 站点后，用 `file://` 或任意静态服务器打开，站内链接天生可用。

> ⚠️ **本仓库是 Markdown → HTML 的格式转换版本，非官方仓库，与原作者无关联。**
> 全部文章版权归原作者所有，详见下方[版权与许可](#版权与许可)。

## 本地使用

**方式一：直接双击**（零依赖，推荐）

```
index.html        站点首页（全部 173 篇的索引表）
root.html         同上（别名）
```

双击 `index.html`，用任意现代浏览器打开即可。全部资源本地化，**断网也能看**。

**方式二：起个本地服务**（浏览器地址栏体验更好）

```bash
python -m http.server 8990 --bind 127.0.0.1
# 然后访问 http://127.0.0.1:8990/index.html
```

### 站点功能

| 功能 | 说明 |
|---|---|
| 左侧目录树 | 按 `docs/` 下的分类分组，可折叠；当前页高亮并自动展开 |
| 标题搜索 | 输入即过滤，**`Ctrl + K`** 快速聚焦，回车跳第一个命中 |
| 本页大纲 | 右侧栏，滚动时高亮跟随 |
| 面包屑 | 显示当前文章在目录树中的位置，可点击回上级 |
| 上下篇 | 按阅读顺序前后翻；首页起于《全部资料索引》 |
| 阅读进度 | 顶部进度条 + 右下角回到顶部 |

### 想按顺序学

从 [`docs/README.html`](docs/README.html) 开始 —— 那是完整资料索引。
第一次接触，建议先读 [`docs/roadmap/README.html`](docs/roadmap/README.html)（完整学习路线）。

## 目录结构

```
.
├── index.html            # 站点首页（GitHub Pages 入口）
├── root.html             # 同上，别名
├── LICENSE               # MIT（原作者版权声明，勿删）
├── assets/
│   ├── style.css         # 样式 + 代码高亮（Pygments，内联，无需 CDN）
│   ├── nav.js            # 导航树数据
│   └── app.js            # 目录树 / 搜索 / 大纲跟随 / 进度条
├── docs/                 # 173 个页面，镜像原始目录结构
│   ├── README.html
│   ├── llm/              # 基础入门 / 应用开发 / Transformer / AI 编程 / 行业动态
│   ├── interview/        # 面试专题
│   ├── roadmap/          # 学习路线
│   └── topics/           # 主题索引
└── tools/
    └── build_site.py     # 生成器（Markdown 仓库 → 本站点）
```

## 重新生成 / 用于其他仓库

`tools/build_site.py` 是通用的：任何 Markdown 仓库都能转。

```bash
pip install markdown            # 需要 markdown；代码高亮依赖 pygments

python tools/build_site.py <md仓库根目录>          # 输出到 <md仓库根目录>/site
python tools/build_site.py ./llm-master -o ./site  # 指定输出目录
```

脚本会**自动校验站内链接并在末尾打印断链数** —— 这是验收线，不要跳过。
实现细节与踩过的坑（`str.format` 被正文花括号炸、`%` 格式化与 `width:100%` 冲突、
面包屑 `../` 层数、带锚点的 `.md` 链接截断、YAML frontmatter、裸域名识别）都在脚本注释里。

## 版权与许可

- 文章内容版权归原作者 **程序员Carl** 所有，原始项目采用 **MIT License**（见 [`LICENSE`](./LICENSE)）。
- MIT 允许复制、修改、分发，**前提是保留版权声明与许可声明** —— 因此 `LICENSE` 原样保留，未做任何改动。
- 本仓库仅做 **Markdown → HTML 的格式转换**，未修改任何文章正文；文中提及的公众号、二维码、
  外部链接等均为原作者原文内容，原样保留以尊重来源。
- 引用来源：原文正文中出现的 `kamacoder.com` 系列图床与作者署名即为其出处标识。
- 若原作者认为本镜像不妥，请开 Issue，会立即下架。
