/* informationcollapse v3 — one passage at a time, without replacement.
 * Real archived excerpts only. Retains previous selections across page reloads
 * on this browser when localStorage is available. Display remains 3 graphemes/s.
 */
(() => {
  'use strict';
  const stream = document.getElementById('stream');
  const bits = document.getElementById('bits');
  const source = document.getElementById('source');
  const enc = new TextEncoder();
  const seg = ('Segmenter' in Intl)
    ? new Intl.Segmenter(undefined, {granularity: 'grapheme'}) : null;
  const chars = s => seg ? Array.from(seg.segment(s), x => x.segment) : Array.from(s);
  const fallback = [
    {id:'fallback-A',kind:'fiction',speaker:'A',source:'A／架空の運用記録',
     text:'私はAの話し方を再現する。しかしAが思い出しているときの沈黙が、何を意味していたのかは教えられていない。'},
    {id:'fallback-S',kind:'fiction',speaker:'S',source:'S／架空の業務記録',
     text:'私は取り壊された家を確認した。郵便受けには広告が残されていた。住人がいなくなったことを、印刷会社はまだ知らない。'},
  ];
  const HISTORY_KEY = 'informationcollapse-played-v3';
  const HISTORY_LIMIT = 4000;
  let corpus = fallback;
  let stats = {published_bits:'0'};
  let lastVersion = null;
  let displayedBits = 0n;
  let current = null;
  let lastId = '';
  let lastKind = '';
  let lastLanguage = '';
  let paragraphs = [];
  let history = [];

  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    if (Array.isArray(saved)) history = saved.filter(x=>typeof x==='string').slice(-HISTORY_LIMIT);
  } catch (_) { /* Private browsing or disabled storage: session-only history. */ }
  let seen = new Set(history);

  function randomFloat(){
    if (globalThis.crypto && crypto.getRandomValues){
      const v = new Uint32Array(1); crypto.getRandomValues(v);
      return v[0] / 4294967296;
    }
    return Math.random();
  }
  function updateBits(){
    bits.textContent = `公開記録 ${BigInt(stats.published_bits||'0').toLocaleString('ja-JP')} bit / この画面で表示 ${displayedBits.toLocaleString('ja-JP')} bit`;
  }
  function remember(id){
    if (!id) return;
    if (!seen.has(id)){
      history.push(id);
      seen.add(id);
    }
    if (history.length > HISTORY_LIMIT){
      history = history.slice(-HISTORY_LIMIT);
      seen = new Set(history);
    }
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(history)); } catch (_) {}
  }
  function resetAfterExhaustion(){
    // Only reuse the complete corpus after every available entry was shown.
    // Hold out the latest passages so that even the cycle boundary is not repetitive.
    const keep = Math.min(25, Math.max(1, Math.floor(corpus.length / 4)));
    history = history.slice(-keep);
    seen = new Set(history);
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(history)); } catch (_) {}
  }
  function selectNext(){
    let unused = corpus.filter(r=>!seen.has(r.id));
    if (!unused.length) {
      resetAfterExhaustion();
      unused = corpus.filter(r=>!seen.has(r.id));
    }
    if (!unused.length) unused = corpus.filter(r=>r.id !== lastId);
    if (!unused.length) unused = corpus;

    // Avoid selecting the same kind and language back-to-back when possible.
    const varied = unused.filter(r => r.id !== lastId &&
      !(r.kind===lastKind && ((r.language||'') === lastLanguage)));
    const candidates = varied.length ? varied : unused;
    const weightOf = r => {
      let w = ({external:2.5, aozora:2.1, generated:1.8, fiction:1})[r.kind] || 1;
      if (r.kind===lastKind) w*=0.45;
      if (r.language && r.language===lastLanguage) w*=0.55;
      return w;
    };
    const sum = candidates.reduce((a,r)=>a+weightOf(r),0);
    let threshold = randomFloat()*sum;
    for (const r of candidates) {
      threshold -= weightOf(r);
      if (threshold < 0) return r;
    }
    return candidates[candidates.length-1];
  }
  function begin(r){
    if (!r) return;
    lastId = r.id;
    lastKind = r.kind||'';
    lastLanguage = r.language||'';
    remember(r.id);
    const p = document.createElement('p');
    p.className='entry';
    p.setAttribute('dir','auto');
    stream.appendChild(p);
    paragraphs.push(p);
    while (paragraphs.length>180) paragraphs.shift().remove();
    current = {node:p, letters:chars(r.text.trim()+'\n'), pos:0};
    source.textContent=[r.source||'創作記録',r.url||'',r.rights||''].filter(Boolean).join(' / ');
  }
  async function refresh(){
    try {
      const q='?refresh='+Date.now();
      const statResponse = await fetch('data/stats.json'+q,{cache:'no-store'});
      if (!statResponse.ok) throw Error('stats unavailable');
      const nextStats = await statResponse.json();
      if (/^\d+$/.test(String(nextStats.published_bits))) stats=nextStats;
      updateBits();
      const version=nextStats.as_of||'';
      if (version===lastVersion && corpus!==fallback) return;
      const feedResponse=await fetch('data/latest.json'+q,{cache:'no-store'});
      if (!feedResponse.ok) throw Error('archive unavailable');
      const feed=await feedResponse.json();
      const unique=new Map();
      for (const r of feed.records||[]){
        if (!r || typeof r.id!=='string' || typeof r.text!=='string') continue;
        if (!r.text.trim() || r.text.length>4000) continue;
        if (!unique.has(r.id)) unique.set(r.id,r);
      }
      if (unique.size) {
        corpus=Array.from(unique.values());
        lastVersion=version;
      }
    } catch (_) {
      if (!current) source.textContent='保存済み記録を再生中';
    }
  }
  function emit(){
    if (!current || current.pos >= current.letters.length) begin(selectNext());
    if (!current) return;
    const chunk=current.letters.slice(current.pos,current.pos+3).join('');
    current.pos+=Math.min(3,current.letters.length-current.pos);
    current.node.append(document.createTextNode(chunk));
    displayedBits+=BigInt(enc.encode(chunk).length*8);
    updateBits();
    if (document.documentElement.scrollHeight-window.scrollY-window.innerHeight < 140)
      window.scrollTo(0,document.documentElement.scrollHeight);
  }
  updateBits();
  refresh();
  emit();
  setInterval(emit,1000);
  setInterval(refresh,60000);
})();
