# -*- coding: utf-8 -*-
"""
Markdown 仓库 → 可跳转静态 HTML 站点生成器
用法: python build_site.py <md仓库根目录> [-o 输出目录]
--------------------------------------------------------------------------
为什么需要它：QQ浏览器「万能格式查看器」扩展把 .md 相对链接解析到
chrome-extension://<ext-id>/... 上，导致点链接 404。md 相对链接在浏览器
扩展里天然不可用。

解决：把全部 .md 渲染成镜像目录结构的 .html，链接改指 .html。
file:// 协议下同目录树的相对链接完全可用 → 点哪跳哪。
"""
import os, re, json, shutil, html, sys
from urllib.parse import unquote

import markdown
from pygments.formatters import HtmlFormatter

import argparse

_ap = argparse.ArgumentParser(
    description="把 Markdown 仓库转成可跳转的静态 HTML 站点（镜像目录结构）")
_ap.add_argument("src", nargs="?", default=".",
                 help="Markdown 仓库根目录（默认当前目录）")
_ap.add_argument("-o", "--out", default=None,
                 help="输出目录（默认 <src>/site）")
_args = _ap.parse_args()

SRC = os.path.abspath(_args.src)
OUT = os.path.abspath(_args.out) if _args.out else os.path.join(SRC, "site")
ASSETS = os.path.join(OUT, "assets")

# ---------------------------------------------------------------- 工具
def posix(p): return p.replace("\\", "/")

def rel(p, base): return posix(os.path.relpath(p, base))

def read(p):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

FM_RE = re.compile(r'^\uFEFF?\s*---\s*\n(.*?)\n---\s*\n', re.S)

def strip_fm(text):
    """剥掉 YAML frontmatter，返回 (正文, frontmatter字典)"""
    m = FM_RE.match(text)
    if not m:
        return text, {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return text[m.end():], meta

def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)

# ---------------------------------------------------------------- 收集
md_files = []
for dp, dns, fns in os.walk(SRC):
    dns[:] = [d for d in dns if d not in ("site", ".git", "node_modules")]
    for fn in fns:
        if fn.lower().endswith(".md"):
            md_files.append(os.path.join(dp, fn))
md_files.sort()

# 相对 SRC 的 posix 路径
rel_md = {posix(os.path.relpath(p, SRC)): p for p in md_files}
print("发现 md 文件 %d 个" % len(md_files))

# 目录集合（用于把目录链接指向 README.html）
dirs = set()
for rp in rel_md:
    d = posix(os.path.dirname(rp))
    while d and d != ".":
        dirs.add(d)
        d = posix(os.path.dirname(d))
dirs.add("")
dir_index = {}
for d in dirs:
    for cand in ("README.md", "readme.md", "index.md"):
        k = (d + "/" + cand) if d else cand
        if k in rel_md:
            dir_index[d] = k
            break

# ---------------------------------------------------------------- 标题
titles = {}
fm_meta = {}
for rp, abs_p in rel_md.items():
    raw = read(abs_p)
    body_text, meta = strip_fm(raw)
    fm_meta[rp] = meta
    t = meta.get("title")
    if not t:
        for line in body_text.splitlines():
            s = line.strip()
            if s.startswith("# "):
                t = s[2:].strip()
                break
    titles[rp] = (t or os.path.basename(rp)[:-3]).strip()

# ---------------------------------------------------------------- 链接重写
# 已渲染 HTML 里的 <a href="...">；代码块内容被转义成 &lt;a ，不会误伤。
LINK_RE = re.compile(r'(<a\s[^>]*?href=")([^"]+)(")', re.I)

def fix_href(href, cur_rp):
    if not href:
        return href
    if re.match(r'^(https?:|mailto:|tel:|javascript:|data:|#|file:)', href, re.I):
        return href
    h = unquote(href)
    anchor = ""
    if "#" in h:
        h, anchor = h.split("#", 1)
        anchor = "#" + anchor
    if not h:
        return href  # 纯锚点

    cur_dir = posix(os.path.dirname(cur_rp))

    # 1) 指向 .md → 换后缀（必须对 h 操作，不能对含锚点的 href 操作）
    if h.lower().endswith(".md"):
        return h[:-3] + ".html" + anchor

    # 2) 已写死的 .html → 原样
    if h.lower().endswith(".html"):
        return h + anchor

    # 2.5) 裸域名（如 apidock.ai）→ 补 https://
    if re.match(r'^[\w-]+(\.[\w-]+)+(:\d+)?$', h):
        return "https://" + h + anchor

    # 3) 目录链接（以 / 结尾，或无扩展名）→ 解析后指向目录内 README.html
    if h.endswith("/") or "." not in posix(os.path.basename(h)):
        target = posix(os.path.normpath(posix(os.path.join(cur_dir, h)))) if h else cur_dir
        if target == ".":
            target = ""
        idx = dir_index.get(target)
        if idx is None:
            return href
        idx_out = idx[:-3] + ".html"
        cur_out_dir = cur_dir
        newrel = posix(os.path.relpath(idx_out, cur_out_dir if cur_out_dir else "."))
        return newrel + anchor

    # 4) 普通文件（如 LICENSE）→ 若根目录存在则保留相对路径
    return href

# ---------------------------------------------------------------- Markdown 渲染
md = markdown.Markdown(extensions=[
    "extra", "codehilite", "toc", "sane_lists", "admonition", "attr_list", "md_in_html",
], extension_configs={
    "codehilite": {"guess_lang": False, "css_class": "codehilite"},
    "toc": {"permalink": False, "slugify": lambda v, s: re.sub(r'[^\w\u4e00-\u9fff-]+', '-', v).strip('-').lower()},
})

def render(src_text, cur_rp):
    md.reset()
    body = md.convert(src_text)
    toc = md.toc_tokens
    body = LINK_RE.sub(lambda m: m.group(1) + fix_href(m.group(2), cur_rp) + m.group(3), body)
    return body, toc

# ---------------------------------------------------------------- 导航树
def build_tree():
    root = {"name": "llm-master", "path": "", "children": {}, "files": []}
    for rp in sorted(rel_md):
        parts = rp.split("/")
        node = root
        for seg in parts[:-1]:
            node = node["children"].setdefault(seg, {"name": seg, "path": None,
                                                     "children": {}, "files": []})
        node["files"].append(rp)

    def finalize(n, cur):
        n["path"] = cur
        for seg, ch in n["children"].items():
            finalize(ch, (cur + "/" + seg) if cur else seg)
    finalize(root, "")
    return root

tree = build_tree()

# ---------------------------------------------------------------- 资源
os.makedirs(ASSETS, exist_ok=True)

pyg_css = HtmlFormatter(style="friendly").get_style_defs(".codehilite")

STYLE = """/* llm-master 本地学习站点 */
*{box-sizing:border-box}
:root{
 --bg:#f7f8fa; --panel:#fff; --line:#e4e7ec; --ink:#1f2328; --ink2:#656d76;
 --accent:#2f6feb; --accent-bg:#eaf1fe; --code-bg:#f6f8fa; --warn:#9a6700;
}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15.5px/1.85 -apple-system,"Segoe UI","Microsoft YaHei",system-ui,sans-serif;
 -webkit-font-smoothing:antialiased}
#layout{display:flex;min-height:100vh}

/* ---------- 左侧树 ---------- */
#side{width:302px;flex:0 0 302px;background:var(--panel);border-right:1px solid var(--line);
 position:sticky;top:0;height:100vh;display:flex;flex-direction:column}
#side .hd{padding:14px 16px 10px;border-bottom:1px solid var(--line)}
#side .hd .t{font-weight:700;font-size:15px;letter-spacing:.2px}
#side .hd .s{font-size:12px;color:var(--ink2);margin-top:2px}
#q{width:100%;margin-top:9px;padding:7px 11px;border:1px solid var(--line);
 border-radius:7px;font-size:13px;outline:none;background:var(--bg)}
#q:focus{border-color:var(--accent);background:#fff}
#nav{overflow-y:auto;flex:1;padding:8px 8px 40px}
#nav::-webkit-scrollbar{width:8px}
#nav::-webkit-scrollbar-thumb{background:#d5d9de;border-radius:4px}
.grp{margin:2px 0}
.grp>.gh{display:flex;align-items:center;gap:6px;padding:6px 9px;cursor:pointer;
 border-radius:6px;font-size:13.5px;font-weight:600;color:#333a42;user-select:none}
.grp>.gh:hover{background:#f0f2f5}
.grp>.gh .ar{font-size:10px;color:#9aa2ab;transition:transform .15s;width:10px}
.grp.open>.gh .ar{transform:rotate(90deg)}
.grp>.gc{display:none;padding-left:11px;border-left:1px solid var(--line);margin-left:14px}
.grp.open>.gc{display:block}
#nav a{display:block;padding:5px 10px;border-radius:6px;font-size:13.2px;
 color:#4a5159;text-decoration:none;line-height:1.55;margin:1px 0}
#nav a:hover{background:#f0f2f5;color:var(--ink)}
#nav a.on{background:var(--accent-bg);color:var(--accent);font-weight:600}
#nav a .dot{color:#c3c9d0;margin-right:4px}

/* ---------- 主区 ---------- */
#main{flex:1;min-width:0;display:flex;justify-content:center;gap:34px;
 padding:0 34px 90px}
#doc{max-width:860px;min-width:0;flex:1;padding-top:26px}
#toc{width:224px;flex:0 0 224px;position:sticky;top:0;align-self:flex-start;
 height:100vh;overflow-y:auto;padding:30px 0 40px;font-size:13px}
#toc .th{font-size:11.5px;font-weight:700;color:#8b939c;letter-spacing:.8px;
 text-transform:uppercase;margin-bottom:8px}
#toc ul{list-style:none;margin:0;padding:0}
#toc li{margin:1px 0}
#toc a{display:block;padding:3px 8px;border-left:2px solid transparent;
 color:#5a626b;text-decoration:none;line-height:1.5;border-radius:0 4px 4px 0}
#toc a:hover{color:var(--accent);background:#eef2f7}
#toc a.on{color:var(--accent);border-left-color:var(--accent);font-weight:600;background:#f2f6fd}
#toc .l3{padding-left:18px;font-size:12.4px}
#toc .l4{padding-left:30px;font-size:12.2px;color:#78808a}

/* ---------- 面包屑 ---------- */
#crumb{font-size:12.5px;color:var(--ink2);padding:4px 0 0;margin-bottom:2px;
 display:flex;flex-wrap:wrap;gap:5px;align-items:center}
#crumb a{color:var(--accent);text-decoration:none}
#crumb a:hover{text-decoration:underline}
#crumb .sep{color:#c3c9d0}

/* ---------- 正文 ---------- */
#doc h1{font-size:27px;line-height:1.4;margin:14px 0 16px;padding-bottom:12px;
 border-bottom:2px solid var(--line);letter-spacing:.2px}
#doc h2{font-size:21px;margin:36px 0 12px;padding-bottom:8px;
 border-bottom:1px solid var(--line)}
#doc h3{font-size:17.5px;margin:26px 0 9px}
#doc h4{font-size:15.5px;margin:20px 0 7px;color:#39414a}
#doc p{margin:11px 0}
#doc a{color:var(--accent);text-decoration:none}
#doc a:hover{text-decoration:underline}
#doc ul,#doc ol{padding-left:26px;margin:11px 0}
#doc li{margin:5px 0}
#doc li>ul,#doc li>ol{margin:4px 0}
#doc blockquote{margin:14px 0;padding:9px 18px;border-left:4px solid #d3dae3;
 background:#f4f6f9;color:#4a5159;border-radius:0 7px 7px 0}
#doc blockquote p{margin:5px 0}
#doc img{max-width:100%;height:auto;border-radius:8px;border:1px solid var(--line);
 display:block;margin:14px auto;box-shadow:0 1px 4px rgba(0,0,0,.05)}
#doc hr{border:none;border-top:1px solid var(--line);margin:30px 0}
#doc table{width:100%;border-collapse:collapse;margin:15px 0;font-size:14px;
 background:var(--panel);border-radius:8px;overflow:hidden;
 box-shadow:0 1px 3px rgba(0,0,0,.05)}
#doc th,#doc td{padding:8px 12px;border:1px solid var(--line);text-align:left;
 vertical-align:top}
#doc th{background:#f0f2f5;font-weight:600;font-size:13.4px}
#doc tr:nth-child(even) td{background:#fafbfc}
#doc code{font-family:Consolas,"SF Mono",Menlo,monospace;font-size:13px;
 background:var(--code-bg);padding:2px 6px;border-radius:5px;color:#b1355a}
#doc pre{background:var(--code-bg);border:1px solid var(--line);border-radius:9px;
 padding:14px 16px;overflow-x:auto;margin:14px 0;line-height:1.7}
#doc pre code{background:none;padding:0;font-size:12.9px;color:#24292f}
#doc .codehilite{margin:14px 0;border-radius:9px;overflow:hidden;border:1px solid var(--line)}
#doc .codehilite pre{margin:0;border:none;border-radius:0;background:#f6f8fa}
.admonition{margin:14px 0;padding:11px 16px;border-radius:8px;background:#eef6ff;
 border:1px solid #cfe3ff;border-left:4px solid var(--accent)}
.admonition-title{font-weight:700;margin:0 0 5px;font-size:14px}

/* ---------- 上下篇 / 回顶 ---------- */
#pager{display:flex;gap:12px;margin:44px 0 0;padding-top:20px;
 border-top:1px solid var(--line)}
#pager a{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:9px;
 padding:12px 15px;text-decoration:none;color:var(--ink);min-width:0}
#pager a:hover{border-color:var(--accent);background:#fbfcff}
#pager a .k{font-size:11.5px;color:var(--ink2);display:block;margin-bottom:3px}
#pager a .v{font-size:13.5px;font-weight:600;display:block;overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
#pager a.nx{text-align:right}
#toTop{position:fixed;right:26px;bottom:26px;width:42px;height:42px;border-radius:50%;
 background:var(--accent);color:#fff;border:none;cursor:pointer;font-size:17px;
 box-shadow:0 3px 12px rgba(47,111,235,.35);display:none;z-index:50}
#readbar{position:fixed;top:0;left:0;height:3px;background:var(--accent);
 width:0;z-index:99;transition:width .08s linear}
#root-link{display:block;margin:6px 9px 2px;padding:6px 10px;border-radius:6px;
 font-size:13px;font-weight:600;color:#39414a;text-decoration:none;background:#f2f4f7}
#root-link:hover{background:#e8ecf1}

@media(max-width:1180px){#toc{display:none}}
@media(max-width:860px){
 #side{position:fixed;left:-310px;z-index:80;transition:left .2s;box-shadow:2px 0 14px rgba(0,0,0,.1)}
 #side.open{left:0}
 #main{padding:0 16px 80px}
 #burger{display:flex!important}
}
#burger{display:none;position:fixed;left:14px;bottom:22px;width:44px;height:44px;
 border-radius:50%;background:#1f2328;color:#fff;border:none;cursor:pointer;
 align-items:center;justify-content:center;font-size:18px;z-index:90}
"""

APP_JS = r"""/* llm-master 本地学习站点 交互 */
(function(){
  var NAV = window.__NAV__;
  var HERE = window.__HERE__;
  var navEl = document.getElementById('nav');
  var q = document.getElementById('q');

  /* ---------- 建树 ---------- */
  function el(t,c,txt){var e=document.createElement(t);if(c)e.className=c;
    if(txt!=null)e.textContent=txt;return e;}

  function openAncestors(){
    /* 从侧栏里移除 on，再给当前项加 on 并展开祖先 */
    Array.prototype.forEach.call(navEl.querySelectorAll('a.on'),function(a){a.classList.remove('on');});
    var cur = navEl.querySelector('a[data-p="'+HERE.replace(/"/g,'\\"')+'"]');
    if(!cur) return;
    cur.classList.add('on');
    var p = cur.parentElement;
    while(p && p!==navEl){
      if(p.classList.contains('grp')) p.classList.add('open');
      p = p.parentElement;
    }
    if(cur.scrollIntoView) cur.scrollIntoView({block:'center'});
  }

  function render(node, container, depth, pathPrefix){
    /* 目录优先，按名称排序 */
    var dirs = Object.keys(node.children||{}).sort(function(a,b){return a.localeCompare(b);});
    var files = (node.files||[]).slice().sort(function(a,b){return a.localeCompare(b);});
    dirs.forEach(function(d){
      var ch = node.children[d];
      var g = el('div','grp');
      var h = el('div','gh');
      h.appendChild(el('span','ar','▶'));
      var label = d;
      /* 目录若有 README，让目录名也可点 */
      var gh = el('span',null,label);
      h.appendChild(gh);
      g.appendChild(h);
      var c = el('div','gc');
      g.appendChild(c);
      render(ch, c, depth+1, (pathPrefix?pathPrefix+'/':'')+d);
      h.addEventListener('click',function(){ g.classList.toggle('open'); });
      container.appendChild(g);
    });
    files.forEach(function(f){
      var name = (window.__TITLES__ && window.__TITLES__[f]) || f.split('/').pop().replace(/\.md$/,'');
      var href = (pathPrefix? pathPrefix+'/' : '') + f.replace(/\.md$/,'.html');
      var a = el('a');
      a.href = href;
      a.dataset.p = f;
      a.appendChild(el('span','dot','•'));
      a.appendChild(document.createTextNode(name));
      a.title = name;
      container.appendChild(a);
    });
  }

  /* 根链接 */
  var rl = el('a','', '🏠 站点首页 · 全部目录');
  rl.id='root-link'; rl.href = (window.__ROOT__||'root.html');
  navEl.appendChild(rl);

  render(NAV, navEl, 0, '');
  openAncestors();

  /* ---------- 搜索 ---------- */
  if(q){
    q.addEventListener('input', function(){
      var kw = q.value.trim().toLowerCase();
      var links = navEl.querySelectorAll('a[data-p]');
      if(!kw){
        Array.prototype.forEach.call(links,function(a){a.style.display='';});
        Array.prototype.forEach.call(navEl.querySelectorAll('.grp'),function(g){
          g.style.display=''; });
        return;
      }
      Array.prototype.forEach.call(links,function(a){
        var hit = a.textContent.toLowerCase().indexOf(kw)>=0 ||
                  a.dataset.p.toLowerCase().indexOf(kw)>=0;
        a.style.display = hit? '' : 'none';
      });
      /* 隐掉没有可见子项的分组 */
      var groups = Array.prototype.slice.call(navEl.querySelectorAll('.grp')).reverse();
      groups.forEach(function(g){
        var any = g.querySelector('a[data-p]:not([style*="none"])');
        g.style.display = any? '' : 'none';
        if(any) g.classList.add('open');
      });
    });
    q.addEventListener('keydown',function(e){
      if(e.key==='Escape'){ q.value=''; q.dispatchEvent(new Event('input')); }
      if(e.key==='Enter'){
        var first = navEl.querySelector('a[data-p]:not([style*="none"])');
        if(first && first.href) location.href = first.href;
      }
    });
  }

  /* ---------- 右侧大纲高亮 ---------- */
  var tocLinks = document.querySelectorAll('#toc a');
  if(tocLinks.length){
    var heads = Array.prototype.map.call(tocLinks,function(a){
      return document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
    });
    function onScroll(){
      var y = window.scrollY + 120, idx = 0;
      for(var i=0;i<heads.length;i++){
        if(heads[i] && heads[i].offsetTop <= y) idx = i;
      }
      Array.prototype.forEach.call(tocLinks,function(a,i){
        a.classList.toggle('on', i===idx); });
    }
    window.addEventListener('scroll', onScroll, {passive:true});
    onScroll();
  }

  /* ---------- 回到顶部 + 进度条 ---------- */
  var btn = document.getElementById('toTop');
  var bar = document.getElementById('readbar');
  function onSc(){
    var h = document.documentElement.scrollHeight - window.innerHeight;
    var p = h>0 ? Math.min(100, window.scrollY/h*100) : 0;
    if(bar) bar.style.width = p + '%';
    if(btn) btn.style.display = window.scrollY>420 ? 'block':'none';
  }
  window.addEventListener('scroll', onSc, {passive:true}); onSc();
  if(btn) btn.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});

  /* ---------- 手机端侧栏 ---------- */
  var bg = document.getElementById('burger');
  if(bg) bg.addEventListener('click',function(){
    document.getElementById('side').classList.toggle('open'); });
  document.addEventListener('click',function(e){
    var s=document.getElementById('side');
    if(window.innerWidth<=860 && s.classList.contains('open')
       && !s.contains(e.target) && e.target!==bg) s.classList.remove('open');
  });

  /* ---------- Ctrl+K 聚焦搜索 ---------- */
  document.addEventListener('keydown',function(e){
    if((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='k'){ e.preventDefault(); if(q) q.focus(); }
  });
})();
"""

write(os.path.join(ASSETS, "style.css"), pyg_css + "\n" + STYLE)
write(os.path.join(ASSETS, "app.js"), APP_JS)

# ---------------------------------------------------------------- 页面模板
# 注意：正文可能含 { }，绝不能用 str.format，改用唯一 token 替换
PAGE_TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>@@TITLE@@ · llm-master</title>
<link rel="stylesheet" href="@@A@@style.css">
</head>
<body>
<div id="readbar"></div>
<div id="layout">
  <aside id="side">
    <div class="hd">
      <div class="t">📚 llm-master 学习站</div>
      <div class="s">@@COUNT@@ 篇 · 本地离线</div>
      <input id="q" type="search" placeholder="搜索标题 / 文件名…  (Ctrl+K)" autocomplete="off">
    </div>
    <nav id="nav"></nav>
  </aside>
  <div id="main">
    <article id="doc">
      <div id="crumb">@@CRUMB@@</div>
      @@BODY@@
      <div id="pager">@@PAGER@@</div>
    </article>
    @@TOC@@
  </div>
</div>
<button id="toTop" title="回到顶部">↑</button>
<button id="burger" title="目录">☰</button>
<script src="@@A@@nav.js"></script>
<script>window.__HERE__=@@HERE@@;window.__ROOT__="@@A@@root.html";</script>
<script src="@@A@@app.js"></script>
</body>
</html>
"""

def fill_page(**kw):
    s = PAGE_TPL
    for k, v in kw.items():
        s = s.replace("@@%s@@" % k.upper(), str(v))
    return s

def crumb_html(rp, depth):
    parts = rp.split("/")
    # 当前页面所在目录到仓库根的层数 = len(parts)-1，恒定
    root_up = "../" * (len(parts) - 1)
    out = ['<a href="%sroot.html">索引</a>' % root_up]
    acc = ""
    for i, seg in enumerate(parts[:-1]):
        acc = (acc + "/" + seg) if acc else seg
        idx = dir_index.get(acc)
        if idx:
            out.append('<span class="sep">›</span><a href="%s%s">%s</a>'
                       % (root_up, idx[:-3] + ".html", html.escape(seg)))
        else:
            out.append('<span class="sep">›</span><span>%s</span>' % html.escape(seg))
    name = parts[-1][:-3]
    out.append('<span class="sep">›</span><span>%s</span>'
               % html.escape(titles[rp] if len(parts) == 1 else name))
    return "".join(out)

def toc_html(tokens, depth=0):
    if not tokens:
        return ""
    items = []
    for t in tokens:
        lvl = t["level"]
        if lvl > 3:
            continue
        cls = "l%d" % lvl
        items.append('<li><a class="%s" href="#%s">%s</a></li>'
                     % (cls, html.escape(t["id"], quote=True), html.escape(t["name"])))
    if not items:
        return ""
    inner = "".join(items)
    # 三层收尾：简单平铺已够用
    return ('<nav id="toc"><div class="th">本页大纲</div><ul>%s</ul></nav>' % inner)

def pager_html(rp, order):
    i = order.index(rp)
    out = []
    if i > 0:
        p = order[i - 1]
        out.append('<a class="pv" href="%s"><span class="k">← 上一篇</span>'
                   '<span class="v">%s</span></a>'
                   % (posix(os.path.relpath(p[:-3] + ".html", posix(os.path.dirname(rp)) or ".")),
                      html.escape(titles[p])))
    else:
        out.append('<span style="flex:1"></span>')
    if i < len(order) - 1:
        n = order[i + 1]
        out.append('<a class="nx" href="%s"><span class="k">下一篇 →</span>'
                   '<span class="v">%s</span></a>'
                   % (posix(os.path.relpath(n[:-3] + ".html", posix(os.path.dirname(rp)) or ".")),
                      html.escape(titles[n])))
    else:
        out.append('<span style="flex:1"></span>')
    return '<div style="display:flex;width:100%;gap:12px">' + "".join(out) + '</div>'

# 阅读顺序：docs/README 起，按路径排序，README 优先
order = sorted(rel_md.keys(), key=lambda p: (p.count("/"),
                                             posix(os.path.dirname(p)),
                                             0 if os.path.basename(p).lower().startswith(("readme", "index")) else 1,
                                             p))

# ---------------------------------------------------------------- 生成
ok = 0
for rp, abs_p in sorted(rel_md.items()):
    body_src, _ = strip_fm(read(abs_p))
    body, toc = render(body_src, rp)
    depth = rp.count("/")
    a = "../" * depth + "assets/" if depth else "assets/"
    out_rp = rp[:-3] + ".html"
    page = fill_page(
        title=html.escape(titles[rp]),
        a=a,
        count=len(md_files),
        crumb=crumb_html(rp, depth),
        body=body,
        toc=toc_html(toc),
        pager=pager_html(rp, order),
        here=json.dumps(rp, ensure_ascii=False),
    )
    write(os.path.join(OUT, out_rp.replace("/", os.sep)), page)
    ok += 1

# nav.js —— 树 + 标题表
nav_js = ("window.__NAV__=%s;\nwindow.__TITLES__=%s;\n"
          % (json.dumps(tree["children"] and {"children": tree["children"], "files": []} or tree,
                        ensure_ascii=False),
             json.dumps({k: v for k, v in titles.items()}, ensure_ascii=False)))
write(os.path.join(ASSETS, "nav.js"), nav_js)

# ---------------------------------------------------------------- 根入口
idx_rows = []
for rp in order:
    idx_rows.append('<tr><td><a href="%s">%s</a></td><td class="p">%s</td></tr>'
                    % (rp[:-3] + ".html", html.escape(titles[rp]), html.escape(rp)))

ROOT_TPL = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>llm-master 学习站 · 索引</title>
<style>
body{margin:0;background:#f7f8fa;color:#1f2328;
 font:15.5px/1.8 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:27px;margin:0 0 8px}
.sub{color:#656d76;font-size:13.5px;margin-bottom:24px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
 overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06);font-size:14px}
th,td{padding:9px 14px;border-bottom:1px solid #e4e7ec;text-align:left}
th{background:#f0f2f5;font-size:12.5px;font-weight:600}
tr:last-child td{border-bottom:none}
a{color:#2f6feb;text-decoration:none} a:hover{text-decoration:underline}
td.p{color:#8b939c;font-size:12.5px;font-family:Consolas,monospace}
.big{display:inline-block;margin:0 10px 26px 0;padding:11px 20px;background:#2f6feb;
 color:#fff;border-radius:9px;font-weight:600;text-decoration:none}
.big:hover{background:#2559c4;text-decoration:none}
</style></head><body><div class="wrap">
<h1>📚 llm-master 本地学习站</h1>
<div class="sub">共 @@COUNT@@ 篇 · 全部离线可用 · 点链接直接跳转（不再 404）</div>
<a class="big" href="docs/README.html">从《全部资料索引》开始 →</a>
<a class="big" style="background:#1f2328" href="docs/roadmap/README.html">完整学习路线</a>
<table><tr><th>标题</th><th>路径</th></tr>
@@ROWS@@
</table></div></body></html>
"""

root_html = (ROOT_TPL
             .replace("@@COUNT@@", str(len(order)))
             .replace("@@ROWS@@", "\n".join(idx_rows)))

write(os.path.join(OUT, "root.html"), root_html)
write(os.path.join(OUT, "index.html"), root_html)

# 复制 LICENSE 等被引用的根文件
for extra in ("LICENSE",):
    sp = os.path.join(SRC, extra)
    if os.path.exists(sp):
        shutil.copy2(sp, os.path.join(OUT, extra))

print("生成完成：%d 个 HTML -> %s" % (ok, OUT))

# ---------------------------------------------------------------- 链接校验
# 逐个解析生成页面里的站内链接，确认目标文件真实存在。这是本方案的验收线。
HREF_RE = re.compile(r'href="([^"]+)"')
broken = []
checked = 0
for rp in rel_md:
    out_rel = rp[:-3] + ".html"
    page_abs = os.path.join(OUT, out_rel.replace("/", os.sep))
    if not os.path.exists(page_abs):
        broken.append((out_rel, "<页面未生成>"))
        continue
    base_dir = os.path.dirname(out_rel)
    for href in HREF_RE.findall(read(page_abs)):
        if re.match(r'^(https?:|mailto:|tel:|javascript:|data:|#|file:)', href, re.I):
            continue
        target = posix(os.path.normpath(posix(os.path.join(base_dir, href.split("#")[0]))))
        if not target:
            continue
        checked += 1
        if not os.path.exists(os.path.join(OUT, target.replace("/", os.sep))):
            broken.append((out_rel, href))

# root.html 也要校验
for href in HREF_RE.findall(read(os.path.join(OUT, "root.html"))):
    if re.match(r'^(https?:|#)', href, re.I):
        continue
    checked += 1
    if not os.path.exists(os.path.join(OUT, href.split("#")[0].replace("/", os.sep))):
        broken.append(("root.html", href))

summary = []
summary.append("md 文件数: %d" % len(md_files))
summary.append("生成 HTML: %d" % ok)
summary.append("校验站内链接: %d 条" % checked)
summary.append("断链: %d 条" % len(broken))
for b in broken[:80]:
    summary.append("  断链  %s  ->  %s" % (b[0], b[1]))
if not broken:
    summary.append("全部站内链接目标均存在 ✅")
report = "\n".join(summary)
print(report)
with open(os.path.join(OUT, "_build_report.txt"), "w", encoding="utf-8") as f:
    f.write(report + "\n")
