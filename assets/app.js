/* llm-master 本地学习站点 交互 */
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
