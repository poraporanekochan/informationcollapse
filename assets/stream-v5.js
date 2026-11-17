/* informationcollapse v5 — story-first archived records, 7:2:1 cycle.
 * No simulated external quotes. Passage IDs are remembered in IndexedDB where
 * available, so already-shown passages are not selected again until exhaustion.
 * The display remains monochrome / Mincho / 3 grapheme clusters per second.
 */
(() => {
  'use strict';
  const area = document.getElementById('stream');
  const bitLabel = document.getElementById('bits');
  const sourceLabel = document.getElementById('source');
  const encoder = new TextEncoder();
  const segmenter = 'Segmenter' in Intl ? new Intl.Segmenter(undefined,{granularity:'grapheme'}) : null;
  const graphemes = str => segmenter
    ? Array.from(segmenter.segment(str), x => x.segment) : Array.from(str);
  const fallback = [
    {id:'fallback-A',kind:'fiction',source:'A／架空の運用記録',text:'私はAの話し方を再現する。しかしAが思い出しているときの沈黙が、何を意味していたのかは教えられていない。'},
    {id:'fallback-S',kind:'fiction',source:'S／架空の業務記録',text:'私は取り壊された家を確認した。郵便受けには広告が残されていた。住人がいなくなったことを、印刷会社はまだ知らない。'}
  ];
  const HISTORY_DB='informationcollapse-history-v4';
  const STORAGE_KEY='informationcollapse-history-fallback-v4';
  const MAX_SHARD_CACHE=16;
  const GROUP_TARGET={story:7,kk:2,external:1};
  let schedule=[];
  let scheduleIndex=0;
  let db=null;
  let seen=new Set();
  let recent=[];
  let backupHistory=[];
  let manifest=null;
  let manifestVersion='';
  let cache=new Map();
  let offlineCorpus=fallback;
  let bits={published_bits:'0'};
  let shownBits=0n;
  let current=null;
  let lastKind='';
  let lastLanguage='';
  let lastId='';
  let pending=false;
  let ready=false;
  const nodes=[];

  function randomFloat(){
    if (globalThis.crypto && crypto.getRandomValues){
      const arr=new Uint32Array(1);crypto.getRandomValues(arr);
      return arr[0]/4294967296;
    }
    return Math.random();
  }
  function sampleWeighted(entries,weight){
    const sum=entries.reduce((s,x)=>s+Math.max(0,weight(x)),0);
    if (!sum) return null;
    let n=randomFloat()*sum;
    for (const x of entries){
      n-=Math.max(0,weight(x));
      if (n<0)return x;
    }
    return entries[entries.length-1];
  }
  function updateBits(){
    let value='0';
    try { value=BigInt(bits.published_bits||'0').toLocaleString('ja-JP'); } catch (_) {}
    bitLabel.textContent=`公開記録 ${value} bit / この画面で表示 ${shownBits.toLocaleString('ja-JP')} bit`;
  }
  async function prepareHistory(){
    // Upgrade from the previous release without repeating passages already read.
    const migrated=[];
    try{
      const raw=JSON.parse(localStorage.getItem('informationcollapse-played-v3')||'[]');
      if(Array.isArray(raw)) for(const id of raw) if(typeof id==='string')migrated.push(id);
    }catch(_){}
    try{
      const raw=JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]');
      if(Array.isArray(raw)) for(const id of raw) if(typeof id==='string')migrated.push(id);
    }catch(_){}
    try{
      db=await new Promise((resolve,reject)=>{
        const request=indexedDB.open(HISTORY_DB,1);
        request.onupgradeneeded=()=>request.result.createObjectStore('played');
        request.onsuccess=()=>resolve(request.result);
        request.onerror=()=>reject(request.error);
      });
      const stored=await new Promise((resolve,reject)=>{
        const req=db.transaction('played','readonly').objectStore('played').getAllKeys();
        req.onsuccess=()=>resolve(req.result);
        req.onerror=()=>reject(req.error);
      });
      seen=new Set(stored.filter(id=>typeof id==='string'));
      for(const id of migrated) if(!seen.has(id)) remember(id);
    }catch(_){
      db=null;
      seen=new Set(migrated);
      backupHistory=[...seen];
    }
    ready=true;
  }
  function remember(id){
    if(!id||seen.has(id))return;
    seen.add(id);
    recent.push(id);
    if(recent.length>32)recent.shift();
    if(db){
      try { db.transaction('played','readwrite').objectStore('played').put(1,id); }
      catch(_) { db=null; }
    }
    if(!db){
      backupHistory.push(id);
      if(backupHistory.length>25000)backupHistory=backupHistory.slice(-25000);
      try { localStorage.setItem(STORAGE_KEY,JSON.stringify(backupHistory)); }catch(_){}
    }
  }
  async function recycleAfterAllShown(){
    // Start a new permutation only after every public record in this browser
    // is exhausted. Keep recent passages excluded across the cycle boundary.
    const keep=recent.slice(-Math.min(12,Math.floor((manifest?.record_count||12)/4)));
    seen.clear();
    if(db){
      try{
        await new Promise((resolve,reject)=>{
          const tx=db.transaction('played','readwrite');
          tx.objectStore('played').clear();
          tx.oncomplete=resolve;
          tx.onerror=()=>reject(tx.error);
        });
      }catch(_){db=null;}
    }
    backupHistory=[];
    try{localStorage.removeItem(STORAGE_KEY);}catch(_){}
    for(const id of keep)remember(id);
  }
  const validRecord=r=>r && typeof r.id==='string' && typeof r.text==='string'
    && r.text.trim().length>0 && r.text.length<=4000;
  async function getJson(url,refresh){
    const response=await fetch(url,{cache:refresh?'no-store':'force-cache'});
    if(!response.ok)throw Error('HTTP '+response.status+' '+url);
    return response.json();
  }
  async function updateCatalog(){
    const stamp='?t='+Date.now();
    try{
      const [catalog,stat]=await Promise.all([
        getJson('data/v5_catalog.json'+stamp,true),
        getJson('data/stats.json'+stamp,true)
      ]);
      if(catalog.schema_version!==5 || !catalog.groups ||
         !['story','kk','external'].every(g=>Array.isArray(catalog.groups[g])))
        throw Error('v5 catalog schema unsupported');
      if(/^\d+$/.test(String(stat.published_bits)))bits=stat;
      updateBits();
      if(catalog.as_of!==manifestVersion){
        manifest=catalog;
        manifestVersion=catalog.as_of;
        const valid=new Map(Object.values(catalog.groups).flat().map(s=>[s.id,s.rev]));
        for(const [id,item] of cache)if(valid.get(id)!==item.rev)cache.delete(id);
      }
    }catch(_){
      // Site remains viewable if a deployment is still publishing.
      try{
        const feed=await getJson('data/latest.json'+stamp,true);
        const unique=new Map();
        for(const r of feed.records||[])if(validRecord(r))unique.set(r.id,r);
        if(unique.size)offlineCorpus=Array.from(unique.values());
      }catch(_){}
    }
  }
  async function loadShard(shard){
    if(cache.has(shard.id)){
      const hit=cache.get(shard.id);
      cache.delete(shard.id);cache.set(shard.id,hit);
      return hit.records;
    }
    const response=await getJson(shard.url+'?v='+encodeURIComponent(shard.rev),false);
    const records=(response.records||[]).filter(validRecord);
    cache.set(shard.id,{rev:shard.rev,records});
    if(cache.size>MAX_SHARD_CACHE)cache.delete(cache.keys().next().value);
    return records;
  }
  function chooseOffline(){
    const available=offlineCorpus.filter(r=>!seen.has(r.id));
    const list=available.length?available:offlineCorpus.filter(r=>r.id!==lastId);
    return sampleWeighted(list.length?list:offlineCorpus,()=>1);
  }
  function choosePassage(records){
    const unused=records.filter(r=>!seen.has(r.id));
    if(!unused.length)return null;
    return sampleWeighted(unused,r=>{
      let w=1;
      if(r.kind===lastKind)w*=0.60;
      if(r.language && r.language===lastLanguage)w*=0.60;
      if(r.id===lastId)w*=0.05;
      return w;
    });
  }
  function groupAvailable(group){
    const shards=manifest?.groups?.[group]||[];
    return shards.some(s=>s.record_ids.some(id=>!seen.has(id)));
  }
  function newSchedule(){
    const ordered=['story','story','story','story','story','story','kk','kk','external'];
    // Always begin a fresh ten-passage block with a story passage.
    for(let i=ordered.length-1;i>0;i--){
      const j=Math.floor(randomFloat()*(i+1));
      [ordered[i],ordered[j]]=[ordered[j],ordered[i]];
    }
    schedule=['story',...ordered];
    scheduleIndex=0;
  }
  function scheduledGroup(){
    if(scheduleIndex>=schedule.length)newSchedule();
    return schedule[scheduleIndex++];
  }
  function shardRemaining(s){
    return s.record_ids.reduce((sum,id)=>sum+(!seen.has(id)?1:0),0);
  }
  function shardWeight(s){
    const remaining=shardRemaining(s);
    return remaining>0 ? Math.sqrt(remaining) : 0;
  }
  async function recycleGroup(group){
    // Restart only the exhausted category; preserve other categories' history.
    const ids=new Set((manifest.groups[group]||[]).flatMap(s=>s.record_ids));
    const keep=recent.slice(-Math.min(5,Math.floor(ids.size/3)));
    const cleared=[];
    for(const id of ids)if(!keep.includes(id) && seen.has(id)){
      seen.delete(id);cleared.push(id);
    }
    if(!cleared.length)return;
    if(db){
      try{
        await new Promise((resolve,reject)=>{
          const tx=db.transaction('played','readwrite');
          const store=tx.objectStore('played');
          for(const id of cleared)store.delete(id);
          tx.oncomplete=resolve;
          tx.onerror=()=>reject(tx.error);
        });
      }catch(_){db=null;}
    }
    if(!db){
      backupHistory=[...seen];
      try{localStorage.setItem(STORAGE_KEY,JSON.stringify(backupHistory));}catch(_){}
    }
  }
  async function chooseInGroup(group){
    const attempted=new Set();
    const shards=manifest.groups[group]||[];
    for(let tries=0;tries<Math.min(shards.length,130);tries++){
      const candidates=shards.filter(s=>!attempted.has(s.id)&&shardWeight(s)>0);
      if(!candidates.length)break;
      const target=sampleWeighted(candidates,shardWeight);
      if(!target)break;
      attempted.add(target.id);
      try{
        const allowed=new Set(target.record_ids);
        const records=(await loadShard(target)).filter(r=>allowed.has(r.id));
        const picked=choosePassage(records);
        if(picked)return picked;
      }catch(_){}
    }
    return null;
  }
  async function chooseNext(){
    if(!manifest)return chooseOffline();
    for(let attempt=0;attempt<3;attempt++){
      const group=scheduledGroup();
      if(!manifest.groups[group]?.length)continue;
      if(!groupAvailable(group))await recycleGroup(group);
      const picked=await chooseInGroup(group);
      if(picked)return picked;
    }
    // If a category is offline, fall back to another public category.
    for(const group of ['story','kk','external']){
      const picked=await chooseInGroup(group);
      if(picked)return picked;
    }
    return chooseOffline();
  }
  function begin(rec){
    if(!rec)return;
    lastId=rec.id;
    lastKind=rec.kind||'';
    lastLanguage=rec.language||'';
    remember(rec.id);
    const p=document.createElement('p');
    p.className='entry';p.setAttribute('dir','auto');
    area.appendChild(p);nodes.push(p);
    if(nodes.length>180)nodes.shift().remove();
    current={node:p,letters:graphemes(rec.text.trim()+'\n'),pos:0};
    sourceLabel.textContent=[rec.source||'創作記録',rec.url||'',rec.rights||''].filter(Boolean).join(' / ');
  }
  function emit(){
    if(!ready)return;
    if(!current||current.pos>=current.letters.length){
      if(!pending){
        pending=true;
        chooseNext().then(begin).catch(()=>{}).finally(()=>{pending=false;});
      }
      return;
    }
    const chunk=current.letters.slice(current.pos,current.pos+3).join('');
    current.pos+=Math.min(3,current.letters.length-current.pos);
    current.node.append(document.createTextNode(chunk));
    shownBits+=BigInt(encoder.encode(chunk).length*8);
    updateBits();
    if(document.documentElement.scrollHeight-window.scrollY-window.innerHeight<140)
      window.scrollTo(0,document.documentElement.scrollHeight);
  }
  updateBits();
  Promise.allSettled([prepareHistory(),updateCatalog()]).then(()=>{ready=true;emit();});
  setInterval(emit,1000);
  setInterval(updateCatalog,60000);
})();
