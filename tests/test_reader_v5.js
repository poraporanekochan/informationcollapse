// Behavioural test: 70/20/10 mix is *actual passage order*, not shard weights.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const {TextEncoder}=require('util');
const root=fs.readFileSync(require('path').join(__dirname,'../assets/stream-v5.js'),'utf8');
const groups={story:35,kk:12,external:8};
const chunks={};
const manifest={schema_version:5,as_of:'t',record_count:55,groups:{story:[],kk:[],external:[]}};
const all=[];
for(const [group,count] of Object.entries(groups)){
 const rows=Array.from({length:count},(_,i)=>({id:`${group}-${i}`,kind:group==='external'?'external':'generated',source:`${group}-${i}`,text:`文章${i}について。`}));
 chunks[group]={records:rows};all.push(...rows);
 manifest.groups[group]=[{id:`${group}/a`,url:`data/shards/${group}/a.json`,rev:'1',count,record_ids:rows.map(r=>r.id)}];
}
const area={children:[],appendChild(el){this.children.push(el);}};
const bitNode={textContent:''}, sourceNode={};const observed=[];
Object.defineProperty(sourceNode,'textContent',{get(){return this.value||'';},set(value){this.value=value;if(value && /^\w+-\d+$/.test(value))observed.push(value)}});
const timers=[],store={};
const sandbox={console,TextEncoder,Intl,Promise,Math,Array,Set,Map,Date,BigInt,Uint32Array,
 document:{getElementById(id){return {stream:area,bits:bitNode,source:sourceNode}[id]},createElement(){return {append(){},setAttribute(){},remove(){}}},createTextNode(text){return {textContent:text}},documentElement:{scrollHeight:0}},
 window:{scrollY:0,innerHeight:500,scrollTo(){}},
 localStorage:{getItem(k){return store[k]||null},setItem(k,v){store[k]=v},removeItem(k){delete store[k]}},
 setInterval(fn,ms){timers.push({fn,ms})},
 fetch(url){let result;
   if(url.startsWith('data/v5_catalog.json'))result=manifest;
   else if(url.startsWith('data/stats.json'))result={published_bits:'8000'};
   else if(url.startsWith('data/latest.json'))result={records:all};
   else {const g=url.match(/shards\/(story|kk|external)\/a\.json/)?.[1];if(g)result=chunks[g]}
   return Promise.resolve(result?{ok:true,json:async()=>result}:{ok:false,status:404});
 }
};
sandbox.globalThis=sandbox;vm.createContext(sandbox);vm.runInContext(root,sandbox);
(async()=>{
 for(let i=0;i<2400 && observed.length<30;i++){
   for(const t of timers)if(t.ms===1000)t.fn();
   await new Promise(resolve=>setImmediate(resolve));
 }
 assert.strictEqual(observed.length,30,'show 30 passages');
 assert.strictEqual(new Set(observed).size,30,'no repeated passages before group exhaustion');
 const first30=observed.slice(0,30);
 const counts=Object.fromEntries(Object.keys(groups).map(g=>[g,first30.filter(x=>x.startsWith(g+'-')).length]));
 assert.deepStrictEqual(counts,{story:21,kk:6,external:3},'exact 70/20/10 distribution across 30 passages');
 assert(observed[0].startsWith('story-'),'first passage must be from S novel');
 assert(bitNode.textContent.includes('8,000'));
 console.log('READER_V5_VERIFIED',JSON.stringify(counts));
})().catch(e=>{console.error(e);process.exitCode=1;});
