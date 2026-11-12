// Offline behavioural test: v4 reader must see all manifest shards and avoid repeats.
const fs=require('fs');
const vm=require('vm');
const assert=require('assert');
const {TextEncoder}=require('util');
const root=fs.readFileSync(require('path').join(__dirname,'../assets/stream.js'),'utf8');
const rows=Array.from({length:12},(_,i)=>({
  id:`id-${i}`,kind:i%2?'external':'fiction',language:i%2?'ja':undefined,
  source:`source-${i}`,text:`異なる記録番号${i}を閲覧しました。`
}));
const chunks=Array.from({length:3},(_,i)=>({records:rows.slice(i*4,(i+1)*4)}));
const catalog={schema_version:4,as_of:'v1',record_count:12,shards:chunks.map((x,i)=>({id:`fiction/${i}`,kind:'fiction',url:`data/shards/fiction/${i}.json`,count:x.records.length,rev:'abc'}))};
const rootNode={children:[],appendChild(x){this.children.push(x);}};
const bitNode={textContent:''};
const sourceNode={textContent:''};
const prior=[];
let n=0;
Object.defineProperty(sourceNode,'textContent',{get(){return this._txt||'';},set(x){this._txt=x;if(x&&x.startsWith('source-'))prior.push(x);}});
const timers=[];
const store={};
const sandbox={
 console,TextEncoder,Intl,Promise,Math,Array,Set,Map,Date,BigInt,Uint32Array,
 document:{getElementById(id){return {stream:rootNode,bits:bitNode,source:sourceNode}[id]},createElement(){return {textContent:'',append(x){this.textContent+=x.textContent;},setAttribute(){},remove(){}}},createTextNode(x){return {textContent:x}},documentElement:{scrollHeight:0}},
 window:{scrollY:0,innerHeight:100,scrollTo(){}},
 localStorage:{getItem(key){return store[key]||null;},setItem(k,v){store[k]=v},removeItem(k){delete store[k]}},
 setInterval(fn,ms){timers.push({fn,ms})},
 fetch(url){
   let payload;
   if(url.startsWith('data/catalog.json'))payload=catalog;
   else if(url.startsWith('data/stats.json'))payload={published_bits:'8000'};
   else if(url.startsWith('data/latest.json'))payload={records:rows};
   else {
     const i=Number(url.match(/\/(\d+)\.json/)?.[1]);
     if(Number.isFinite(i))payload=chunks[i];
   }
   if(!payload)return Promise.resolve({ok:false,status:404});
   return Promise.resolve({ok:true,json:async()=>payload});
 }
};
sandbox.globalThis=sandbox;
vm.createContext(sandbox);
vm.runInContext(root,sandbox);
(async()=>{
  for(let i=0;i<1200&&prior.length<12;i++){
    for(const t of timers)if(t.ms===1000)t.fn();
    await new Promise(resolve=>setImmediate(resolve));
  }
  assert.strictEqual(prior.length,12,'must visit 12 distinct archived records');
  assert.strictEqual(new Set(prior).size,12,'must not repeat while unseen records exist');
  assert(bitNode.textContent.includes('8,000'));
  console.log('READER_VERIFIED',prior.length,'distinct records without repetition across 3 shards');
})().catch(e=>{console.error(e);process.exitCode=1;});
