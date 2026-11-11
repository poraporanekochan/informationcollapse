/* informationcollapse: plain text, three grapheme clusters each visible second. */
(() => {
  'use strict';
  const stream = document.getElementById('stream');
  const bits = document.getElementById('bits');
  const source = document.getElementById('source');
  const enc = new TextEncoder();
  const seg = ('Segmenter' in Intl) ? new Intl.Segmenter(undefined,{granularity:'grapheme'}) : null;
  const charArray = x => seg ? Array.from(seg.segment(x),v=>v.segment) : Array.from(x);
  const initial = [
    {id:'fallback-A',kind:'fiction',speaker:'A',source:'A／架空の運用記録',text:'私はAの話し方を再現する。しかしAが思い出しているときの沈黙が、何を意味していたのかは教えられていない。'},
    {id:'fallback-S',kind:'fiction',speaker:'S',source:'S／架空の業務記録',text:'私は取り壊された家を確認した。郵便受けには広告が残されていた。住人がいなくなったことを、印刷会社はまだ知らない。'},
  ];
  let corpus=initial.slice();
  let stats={published_bits:'0',ai_generated_count:0};
  let displayedBits=0n;
  let current=null;
  let last='';
  let paragraphs=[];
  const openedAt=Date.now();
  let aozoraSlot=0;
  let externalSlot=0;
  let refreshError=false;

  function randomInt(max){
    if(max<=1)return 0;
    if(globalThis.crypto && crypto.getRandomValues){
      const a=new Uint32Array(1);crypto.getRandomValues(a);return a[0]%max;
    }
    return Math.floor(Math.random()*max);
  }
  const pick = items => items.length ? items[randomInt(items.length)] : null;
  function updateBits(){
    bits.textContent = `公開記録 ${BigInt(stats.published_bits||'0').toLocaleString('ja-JP')} bit / この画面で表示 ${displayedBits.toLocaleString('ja-JP')} bit`;
  }
  async function refresh(){
    try{
      const q='?refresh='+Date.now();
      const [r,s]=await Promise.all([fetch('data/latest.json'+q,{cache:'no-store'}),fetch('data/stats.json'+q,{cache:'no-store'})]);
      if(!r.ok||!s.ok)throw Error('archive unavailable');
      const [feed,stat]=await Promise.all([r.json(),s.json()]);
      const rows=(feed.records||[]).filter(x=>x && typeof x.text==='string' && x.text.trim() && x.text.length<4000);
      if(rows.length)corpus=rows;
      if(/^\d+$/.test(String(stat.published_bits))) stats=stat;
      refreshError=false;
      updateBits();
    }catch(e){
      refreshError=true;
      if(!current)source.textContent='保存済み記録を再生中';
    }
  }
  function choice(){
    const seconds=(Date.now()-openedAt)/1000;
    const aos=corpus.filter(r=>r.kind==='aozora'&&r.id!==last);
    const ex=corpus.filter(r=>r.kind==='external'&&r.id!==last);
    const gen=corpus.filter(r=>r.kind==='generated'&&r.id!==last);
    const seed=corpus.filter(r=>r.kind==='fiction'&&r.id!==last);
    // These are presentation intervals measured since this browser tab opened.
    // No quotations are simulated when real external records are unavailable.
    const aSlot=Math.floor(seconds/300),eSlot=Math.floor(seconds/600);
    if(aSlot>aozoraSlot){aozoraSlot=aSlot;if(aos.length)return pick(aos);}
    if(eSlot>externalSlot){externalSlot=eSlot;if(ex.length)return pick(ex);}
    // Authentically AI-written material is the main stream whenever available.
    if(gen.length && randomInt(100)<87)return pick(gen);
    return pick(seed.length?seed:(gen.length?gen:corpus.filter(r=>r.id!==last))) || pick(corpus);
  }
  function begin(r){
    if(!r)return;
    last=r.id;
    const p=document.createElement('p');
    p.className='entry';p.setAttribute('dir','auto');
    stream.appendChild(p);paragraphs.push(p);
    while(paragraphs.length>180){const old=paragraphs.shift();old.remove();}
    current={node:p,chars:charArray(r.text.trim()+'\n'),at:0};
    source.textContent=[r.source||'創作記録',r.url||'',r.rights||''].filter(Boolean).join(' / ');
  }
  function emit(){
    if(!current||current.at>=current.chars.length)begin(choice());
    if(!current)return;
    const chunk=current.chars.slice(current.at,current.at+3).join('');
    current.at+=Math.min(3,current.chars.length-current.at);
    current.node.append(document.createTextNode(chunk));
    displayedBits+=BigInt(enc.encode(chunk).length*8);
    updateBits();
    const remaining=document.documentElement.scrollHeight-window.scrollY-innerHeight;
    if(remaining<140)window.scrollTo(0,document.documentElement.scrollHeight);
  }
  updateBits();refresh();
  setInterval(emit,1000);
  setInterval(refresh,60000);
})();
