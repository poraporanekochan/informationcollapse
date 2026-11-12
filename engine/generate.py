#!/usr/bin/env python3
"""informationcollapse archive writer. No fake quotations, no fabricated AI outputs.
GitHub Actions checks every ~5 minutes; free-tier Gemini calls at most every 2 hours.
"""
from __future__ import annotations
import csv, datetime as dt, hashlib, html, io, json, os, random, re, sys, time, urllib.parse, urllib.request, zipfile
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
ARCHIVE = ROOT / 'archive'
CACHE = ROOT / 'cache'
for p in (DATA, ARCHIVE, CACHE): p.mkdir(exist_ok=True, parents=True)
NOW = dt.datetime.now(ZoneInfo('Asia/Tokyo'))
DAY = NOW.strftime('%Y%m%d')
STAMP = NOW.isoformat(timespec='seconds')
RANDOM = random.SystemRandom()
UA = 'informationcollapse/1.2 (https://github.com/poraporanekochan/informationcollapse; automated free-text archive)' 


def get_json(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def set_json(path, data):
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def get_records(path):
    if not path.exists(): return []
    out=[]
    for s in path.read_text('utf-8').splitlines():
        try:
            o=json.loads(s)
            if isinstance(o,dict) and isinstance(o.get('text'),str): out.append(o)
        except ValueError: continue
    return out


def append_log(path, records):
    if not records: return
    path.parent.mkdir(exist_ok=True,parents=True)
    with path.open('a',encoding='utf-8') as f:
        for rec in records: f.write(json.dumps(rec,ensure_ascii=False)+'\n')


def request(url, data=None, headers=None, timeout=17):
    h={'User-Agent':UA, 'Accept':'application/json, text/html, */*'}
    h.update(headers or {})
    req=urllib.request.Request(url,data=data,headers=h)
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        content=resp.read(4_000_000)
        return content,dict(resp.headers)


def sentence_candidates(text, minlen=12, maxlen=250):
    text=re.sub(r'\s+', ' ', text).strip()
    # End marks from many scripts. Keep sentences in their original script.
    pieces=re.split(r'(?<=[。！？.!?؟۔।])\s*',text)
    out=[]
    for s in pieces:
        s=s.strip(' \t\n\r\u3000')
        if minlen <= len(s) <= maxlen and not s.lower().startswith(('http://','https://')):
            if re.search(r'[a-zA-Z]',s) and len(re.findall(r'\b\S+\b',s))>25:
                continue
            out.append(s)
    return out


class MainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth=0;self.buf=[];self.skip=0
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if not self.depth and tag=='div' and 'main_text' in d.get('class','').split():
            self.depth=1;return
        if self.depth:
            if tag in ('br','hr','img','meta','link','input','wbr'):
                if tag=='br': self.buf.append('\n')
                return
            self.depth+=1
            if tag in ('rt','rp'):self.skip+=1
            if tag in ('p','div','h2'):self.buf.append('\n')
    def handle_endtag(self,tag):
        if self.depth:
            if tag in ('rt','rp') and self.skip:self.skip-=1
            self.depth-=1
    def handle_data(self,data):
        if self.depth and not self.skip:self.buf.append(data)
    def text(self): return ''.join(self.buf)

AOZORA_FALLBACK=[
  ('夏目漱石','こころ','https://www.aozora.gr.jp/cards/000148/files/773_14560.html'),
  ('芥川龍之介','羅生門','https://www.aozora.gr.jp/cards/000879/files/127_15260.html'),
  ('梶井基次郎','檸檬','https://www.aozora.gr.jp/cards/000074/files/424_19826.html'),
]
CATALOG_URL='https://www.aozora.gr.jp/index_pages/list_person_all_extended_utf8.zip'

def aozora_catalog():
    path=CACHE/'aozora_catalog.json'
    cached=get_json(path,[])
    if cached and (time.time()-path.stat().st_mtime)<7*86400: return cached
    try:
        raw,_=request(CATALOG_URL,timeout=20)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            csvname=next(s for s in z.namelist() if s.lower().endswith('.csv'))
            reader=csv.DictReader(io.StringIO(z.read(csvname).decode('utf-8-sig')))
            chosen=[]
            for row in reader:
                if row.get('作品著作権フラグ')!='なし' or row.get('人物著作権フラグ')!='なし':continue
                url=row.get('XHTMLファイルURL','')
                if not url.startswith('https://www.aozora.gr.jp/cards/'):continue
                author=(row.get('姓','')+row.get('名','')).strip() or row.get('著者名','')
                title=row.get('作品名','').strip()
                if author and title:chosen.append([author,title,url])
            if len(chosen)>100:
                set_json(path,chosen)
                return chosen
    except Exception as e:print('AOZORA CATALOG unavailable',str(e)[:180],file=sys.stderr)
    return cached or AOZORA_FALLBACK


def fetch_aozora_many(count=5, known=None):
    """Obtain independently attributed public-domain excerpts; do not repeat archived text.

    This requests only a few source files per run. Catalog failure falls back
    to known public-domain authors while keeping the original attributions.
    """
    known = known or set()
    candidates = aozora_catalog()[:]
    RANDOM.shuffle(candidates)
    results=[]
    visited=set()
    # Fetch a small number of works, selecting different sentences from each.
    for author,title,url in candidates[:min(len(candidates),8)]:
        if len(results)>=count:break
        if url in visited:continue
        visited.add(url)
        try:
            raw,_=request(url,timeout=15)
            # Aozora XHTML typically uses Shift_JIS, some copies use UTF-8.
            enc='utf-8' if b'charset=utf-8' in raw[:2500].lower() else 'shift_jis'
            page=raw.decode(enc,errors='replace')
            parser=MainText();parser.feed(page)
            sentences=sentence_candidates(parser.text(),minlen=14,maxlen=195)
            RANDOM.shuffle(sentences)
            accepted=0
            for sentence in sentences:
                ident='aozora-'+hashlib.sha1((url+sentence).encode()).hexdigest()[:14]
                if ident in known:continue
                known.add(ident)
                results.append({'id':ident,'date':DAY,'created_at':STAMP,'kind':'aozora','speaker':author,
                                'source':f'青空文庫：{author}『{title}』','title':title,'text':sentence,
                                'url':url,'rights':'著作権消滅が確認された作品の原文（青空文庫）',
                                'provenance':'青空文庫の公開XHTMLから取得。作品の文章でありAI生成ではない。'})
                accepted+=1
                if len(results)>=count or accepted>=2:break
        except Exception as e:
            print('AOZORA fetch failed',str(e)[:140],file=sys.stderr)
    return results


LANGS=['en','fr','de','es','pt','it','ru','ar','fa','hi','bn','zh','ko','ja','pl','tr','uk','he','id','vi','sw','ta','ur','nl','sv','el','th']


def fetch_multilingual_many(limit=40, known=None):
    """Use small, batched random-page queries across different Wikipedia languages.

    Not a uniform sample of the entire web. Each page supplies at most one
    short excerpt and carries its page URL and original language. Respect
    rate limits: a handful of sequential requests, never concurrent scraping.
    """
    known = known or set()
    languages=RANDOM.sample(LANGS,min(8,len(LANGS)))
    found=[]
    for lang in languages:
        if len(found)>=limit:break
        lang_count=0
        try:
            args=urllib.parse.urlencode({
                'action':'query','generator':'random','grnnamespace':'0',
                'grnlimit':'8','grnfilterredir':'nonredirects',
                'prop':'extracts|info','exintro':'1','explaintext':'1',
                'inprop':'url','format':'json','formatversion':'2'})
            api=f'https://{lang}.wikipedia.org/w/api.php?{args}'
            raw,_=request(api,timeout=12)
            payload=json.loads(raw)
            pages=payload.get('query',{}).get('pages',[])
            if not isinstance(pages,list):continue
            RANDOM.shuffle(pages)
            for page in pages:
                if not isinstance(page,dict):continue
                sentences=sentence_candidates(page.get('extract',''),minlen=18,maxlen=190)
                RANDOM.shuffle(sentences)
                title=page.get('title','')
                pageurl=page.get('fullurl') or f'https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(" ","_"))}'
                for sentence in sentences[:5]:
                    ident='external-'+hashlib.sha1((pageurl+sentence).encode()).hexdigest()[:14]
                    if ident in known:continue
                    known.add(ident)
                    lang_count+=1
                    found.append({'id':ident,'date':DAY,'created_at':STAMP,'kind':'external',
                       'language':lang,'speaker':'','title':title,
                       'source':f'Wikipedia ({lang})：{title}','text':sentence,'url':pageurl,
                       'rights':'CC BY-SA 4.0; https://creativecommons.org/licenses/by-sa/4.0/',
                       'provenance':'公開記事の一文を引用。全文ではなく抜粋。ウェブ全体からの一様な無作為標本ではない。'})
                    break
                if len(found)>=limit or lang_count>=5:break
        except Exception as e:
            print('MULTILINGUAL fetch failed',lang,str(e)[:160],file=sys.stderr)
    RANDOM.shuffle(found)
    return found[:limit]

VOICE_RULES='''舞台：都市破壊業KK（1962年創業、Sは2026年10月24日死亡）と、その業務を承継した情報破壊業KK。Aは故人である建築家Aの記録から作られたAIの対話系であり、本人ではない。透は音を収集する。久野は印刷と校正の仕事をする。川瀬初江はかつて地図と台帳の食い違いで住居の存在を否定され、不利益を受けた人間。Sの聖書はアラン『定義集』とデカルト『方法序説』。第七界のテクニウムはケヴィン・ケリーの比喩。情報の第八界はKK独自の仮説。情報は複製・変異・選択を通じて循環するが、責任の所在は常に人間の制度や行動へさかのぼる。'''


def generate_ai():
    # Free-tier Gemini only; never fall back to paid providers.
    key=os.getenv('GEMINI_API_KEY','').strip()
    if not key:
        print('GEMINI_API_KEY absent: no AI text generated. Existing records stay online.',file=sys.stderr)
        return []
    model=os.getenv('GEMINI_MODEL','gemini-3.5-flash-lite').strip()
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+', model):
        print('Invalid GEMINI_MODEL: ignoring generation request',file=sys.stderr)
        return []
    roles=['Aによる自己観察', '都市破壊業KK・現地調査', 'Sの遺稿をAIが推定復元した文章', '情報破壊業KK・業務報告',
           '無署名の都市観察','透の録音台帳をもとにしたAI構成', '久野の校正メモをもとにしたAI構成',
           'AとSの議論の不確実な再構成','情報の第八界に関する論理検証',
           '出勤簿に残された注記','破壊現場の騒音計測','地図修正の差戻し通知',
           '未知の地名に関する脚注','郵便物の返送理由','1960年代の工事見積書',
           '1970年代の行政照会','1990年代の機械の故障記録','過去の自分に出した訂正届',
           '音声記録から失われた箇所','Aが理解できなかった人間の表情',
           '同じ家屋に付いた二種類の住所','ある朝の無記名のメモ',
           'A自身による文章生成の失敗報告','整合しない建築面積の再計算',
           '行方不明の資料に付いた借出票','重要でないものの棚卸し']
    selected=RANDOM.sample(roles,4)
    canon=get_json(ROOT/'engine'/'world.json',{})
    prompt=f'''{VOICE_RULES}
制作設定：{json.dumps(canon,ensure_ascii=False)}
現在日時：{STAMP}
生成する4件の文書種別：{json.dumps(selected,ensure_ascii=False)}
各件は独立した短い架空文書（日本語を基本とするが1件だけ任意の外国語を使ってよい）。毎件180〜420文字程度。曖昧な決め台詞、自己啓発、無意味な比喩や宣言を避ける。観察の具体性、倫理上の論点、書類としての信憑性、人物の欠点、検証不能さを扱う。Sの死後に本人の新作日記を捏造しない。Sに関する新たな文は「AIによる推定復元」であるとわかるように。Aが人間的感情を経験したと断定しない。すべて劇的にせず、時に退屈な点検や経費精算も書く。文章同士に脈絡はなくてよい。非公開の現実の個人情報は含めない。
厳密なJSONオブジェクトのみ返す：{{"records":[{{"speaker":"A または S（推定復元） または 組織記録 など","type":"文書種類","text":"本文"}},...]}}。4件。説明文不要。'''
    url='https://generativelanguage.googleapis.com/v1beta/models/'+urllib.parse.quote(model,safe='-_.')+':generateContent'
    payload={
        'systemInstruction':{'parts':[{'text':'あなたは架空資料の作成者。著者や証言の出所を偽らず、具体的で矛盾を隠さない短文を書く。JSONのみ出力。'}]},
        'contents':[{'role':'user','parts':[{'text':prompt}]}],
        'generationConfig':{'temperature':0.95,'maxOutputTokens':4500,'responseMimeType':'application/json'},
    }
    try:
        raw,_=request(url,json.dumps(payload,ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type':'application/json','x-goog-api-key':key},timeout=75)
        response=json.loads(raw)
        chunks=[]
        for candidate in response.get('candidates',[]):
            for part in candidate.get('content',{}).get('parts',[]):
                if isinstance(part.get('text'),str):chunks.append(part['text'])
            if chunks:break
        response_text=''.join(chunks).strip()
        if response_text.startswith('```'):
            response_text=re.sub(r'^```(?:json)?\s*|\s*```$', '',response_text).strip()
        data=json.loads(response_text)
        out=[]
        for i,r in enumerate(data.get('records',[])[:4]):
            if not isinstance(r,dict):continue
            body=str(r.get('text','')).strip()
            type_=str(r.get('type','')).strip()[:70]
            speaker=str(r.get('speaker','A')).strip()[:50]
            if len(body)<50 or len(body)>1800:continue
            ident=f'ai-{NOW.strftime("%Y%m%d%H%M%S")}-{i+1:02d}-{hashlib.sha1(body.encode()).hexdigest()[:7]}'
            out.append({'id':ident,'date':DAY,'created_at':STAMP,'kind':'generated','speaker':speaker,
                'source':f'{speaker}／{type_}（生成AIによる創作）','title':type_,'text':body,
                'model':model,'provenance':'Gemini API無料枠を利用し、当該実行時に新規生成した架空文書。実在の証言ではない。'})
        if not out:print('Gemini response contained no usable records.',file=sys.stderr)
        return out
    except Exception as e:
        # Do not mask failure as success and never switch to paid providers.
        print('Gemini generation skipped (possibly free-tier quota):',str(e)[:270],file=sys.stderr)
        return []


def archive_records(records):
    for r in records:
        filename=ARCHIVE/r['date'][:4]/f'{r["date"]}.txt';filename.parent.mkdir(parents=True,exist_ok=True)
        with filename.open('a',encoding='utf-8') as f:
            f.write(f'\n\n[{r["created_at"]}] [{r["kind"]}] [{r["source"]}]\n')
            f.write(r['text']+'\n')
            if r.get('url'):f.write(f'出典: {r["url"]}\n')
            if r.get('rights'):f.write(f'利用条件: {r["rights"]}\n')
            f.write('資料区分: '+r.get('provenance','')+'\n')


def rebuild():
    seed=get_json(DATA/'seed.json',[])
    gen=get_records(DATA/'generated.jsonl')
    external=get_records(DATA/'external.jsonl')
    # Most of the visible timeline is truly AI-written when an API key is configured.
    # This feed is a pool, not a chronological assertion.
    # Keep a broad, bounded public pool to resist repetition on mobile.
    # The archives themselves remain the durable complete record.
    records=(seed[-200:]+gen[-220:]+external[-650:])
    set_json(DATA/'latest.json',{'as_of':STAMP,'records':records})
    files=list(ARCHIVE.glob('*/*.txt'))
    bits=sum(p.stat().st_size for p in files)*8
    set_json(DATA/'stats.json',{'published_bits':str(bits),'document_count':len(files),
             'record_count':len(seed)+len(gen)+len(external),'ai_generated_count':len(gen),
             'external_record_count':sum(x.get('kind')=='external' for x in external),
             'aozora_record_count':sum(x.get('kind')=='aozora' for x in external),
             'last_actual_ai_generation': gen[-1].get('created_at') if gen else None,
             'as_of':STAMP,
             'definition':'archive/内の公開TXTファイルをUTF-8で符号化した実バイト数×8。閲覧者の通信量を推定した数値ではない。'})
    return {'seed':len(seed),'ai':len(gen),'external':len(external),'bits':bits}


def due(state,key,minutes):
    try:return (NOW-dt.datetime.fromisoformat(state[key])).total_seconds()>=minutes*60-2
    except Exception:return True


def run():
    state=get_json(DATA/'state.json',{})
    past=get_records(DATA/'generated.jsonl')+get_records(DATA/'external.jsonl')
    known={r.get('id') for r in past}

    # The Gemini free-tier request rate remains capped at once in 120 minutes.
    # Failure never switches to a paid API and the attempt is still recorded.
    ai=[]
    if due(state,'gemini_last_attempt',120):
        if os.getenv('GEMINI_API_KEY','').strip():
            state['gemini_last_attempt']=STAMP
            ai=generate_ai()
        else:
            print('No GEMINI_API_KEY; free AI generation skipped.',file=sys.stderr)

    extras=[]
    # Fetch a small set of real, short, public-domain Japanese book excerpts.
    if due(state,'aozora_last',10):
        aozora=fetch_aozora_many(count=5,known=known)
        if aozora:
            extras.extend(aozora)
            state['aozora_last']=STAMP

    # Batched, multilingual random Wikipedia pages (at most 8 API calls).
    # Do not fetch X/Instagram posts or claim unauthenticated scraping.
    if due(state,'external_last',10):
        external=fetch_multilingual_many(limit=40,known=known)
        if external:
            extras.extend(external)
            state['external_last']=STAMP

    # Also de-duplicate all records created in one execution.
    historical={r.get('id') for r in past}
    fresh=[]
    for r in ai+extras:
        if r.get('id') not in historical:
            fresh.append(r)
            historical.add(r.get('id'))

    append_log(DATA/'generated.jsonl',[r for r in fresh if r.get('kind')=='generated'])
    append_log(DATA/'external.jsonl',[r for r in fresh if r.get('kind') in ('aozora','external')])
    archive_records(fresh)
    set_json(DATA/'state.json',state)
    total=rebuild()
    summary={'new_ai':sum(r.get('kind')=='generated' for r in fresh),
             'new_aozora':sum(r.get('kind')=='aozora' for r in fresh),
             'new_wikipedia':sum(r.get('kind')=='external' for r in fresh),
             'total':total}
    print('GENERATION_SUMMARY',json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    if '--rebuild' in sys.argv:print(rebuild())
    else:run()
