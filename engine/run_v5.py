"""v5 orchestrator: resilient Gemini fiction + restrained external collection.

Does not replace or rewrite the existing append-only archive engine. It wraps
its stable run()/rebuild() interface and preserves all historical source files.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import generate as legacy
from build_v5_catalog import build as build_catalog


def parse_gemini_records(body):
    """Accept both {records:[...]} and [...] JSON; fail clearly otherwise."""
    if isinstance(body,dict):
        records=body.get('records',body.get('items'))
        if isinstance(records,dict):
            records=records.get('records',records.get('items'))
    elif isinstance(body,list):
        records=body
    else:
        records=None
    if not isinstance(records,list):
        raise ValueError('Gemini response must be a list or an object with records list')
    return [r for r in records if isinstance(r,dict)]


def story_context():
    prior=legacy.get_records(legacy.DATA/'generated.jsonl')
    recent=prior[-12:]
    excerpts=[]
    for r in recent:
        txt=str(r.get('text','')).strip()
        if txt:
            excerpts.append({'source':str(r.get('source',''))[:100],
                             'track':r.get('track','legacy'),
                             'text':txt[:520]})
    existing_story=sum(r.get('track')=='story' for r in prior)
    return existing_story,excerpts


def generate_ai_v5():
    key=os.getenv('GEMINI_API_KEY','').strip()
    model=os.getenv('GEMINI_MODEL','gemini-3.5-flash-lite').strip()
    if not key:
        legacy.AI_OUTCOME.update(status='missing_key',detail='GEMINI_API_KEY is absent',new=0)
        return []
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+',model):
        legacy.AI_OUTCOME.update(status='invalid_model',detail='GEMINI_MODEL has invalid characters',new=0)
        return []
    n,previous=story_context()
    canon=legacy.get_json(legacy.ROOT/'engine'/'world.json',{})
    roles=[
        '語り手がSの残した資料を調査する場面（具体的な行動を描く）',
        '久野または透の視点から、前の場面を変化させる新事実',
        'S・Aに関する断片と、次の調査につながる小さな手がかり',
        '情報破壊業KKの業務記録またはAの技術的な自己監査',
    ]
    prompt=f'''次の4件を、情報破壊業KKの架空文書として執筆してください。

世界設定（歴史的な事実ではなくフィクション）：{json.dumps(canon,ensure_ascii=False)}
既存の物語の直近の断片（事実として固定せず、不確実性を保持）：{json.dumps(previous,ensure_ascii=False)}
これまでのv5物語断片数：{n}。今回の3つの物語文書は#{n+1}〜#{n+3}。
今回の文書の役割：{json.dumps(roles,ensure_ascii=False)}

重要：最初の3件は『Sをめぐる冒険』の同じ時間軸上で少しずつ因果が進む文章。
既出の内容を言い換えて水増ししない。毎回ひとつは小さくても新しい物的証拠、行動、会話、関係の変化を提示する。
4件目だけが情報破壊業KKの独立した業務記録。
久野と透の存在や人格を尊重し、安易な恋愛成就・万能のAI・安易な謎解き・実在の秘密情報を避ける。
Sは2026年10月24日に死亡。Sの死後の一人称文は必ず「AIによる推定復元」と明示。
AI Aは故A本人ではない。架空文書と実際の引用は混同しない。
抽象的な宣言だけで終わらず、紙、建物、動線、音、言い淀み、領収書など具体物に根差す。
各件180〜420文字程度。日本語。意図的な文章間の矛盾は記録に理由を添える。

厳密なJSONを返すこと。次の形式が望ましい：
{{"records":[{{"speaker":"語り手","type":"第{n+1}断片／調査記録","text":"..."}},{{"speaker":"久野または透","type":"第{n+2}断片／...","text":"..."}},{{"speaker":"S関連／資料","type":"第{n+3}断片／...","text":"..."}},{{"speaker":"情報破壊業KK","type":"業務報告","text":"..."}}]}}
説明文・Markdown不要。JSON配列で返ってきた場合も受け付ける。'''
    url='https://generativelanguage.googleapis.com/v1beta/models/'+urllib.parse.quote(model,safe='-_.')+':generateContent'
    payload={
        'systemInstruction':{'parts':[{'text':'あなたは連続する架空の文学作品と業務記録を執筆する編集者。既存記録を丁寧に読み、実在資料と混同させず、JSONだけを返す。'}]},
        'contents':[{'role':'user','parts':[{'text':prompt}]}],
        'generationConfig':{'temperature':0.90,'maxOutputTokens':5000,'responseMimeType':'application/json'},
    }
    try:
        raw,_=legacy.request(url,json.dumps(payload,ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type':'application/json','x-goog-api-key':key},timeout=75)
        response=json.loads(raw)
        if not isinstance(response,dict):
            raise ValueError('Gemini API top-level response was not an object')
        chunks=[]
        for candidate in response.get('candidates',[]):
            if not isinstance(candidate,dict):continue
            content=candidate.get('content',{})
            if not isinstance(content,dict):continue
            for part in content.get('parts',[]):
                if isinstance(part,dict) and isinstance(part.get('text'),str):
                    chunks.append(part['text'])
            if chunks:break
        response_text=''.join(chunks).strip()
        if response_text.startswith('```'):
            response_text=re.sub(r'^```(?:json)?\s*|\s*```$','',response_text).strip()
        records=parse_gemini_records(json.loads(response_text))
        if len(records)<4:
            raise ValueError(f'Gemini returned only {len(records)} of 4 requested documents')
        out=[]
        for i,r in enumerate(records[:4]):
            body=str(r.get('text','')).strip()
            if not 65<=len(body)<=1800:
                raise ValueError(f'Invalid length for document {i+1}: {len(body)}')
            speaker=str(r.get('speaker','記録者')).strip()[:65]
            title=str(r.get('type','断片')).strip()[:90]
            track='story' if i<3 else 'kk'
            seq=n+i+1 if i<3 else None
            ident=f'ai-{legacy.NOW.strftime("%Y%m%d%H%M%S")}-{i+1:02d}-{hashlib.sha1(body.encode()).hexdigest()[:7]}'
            display_title=f'Sをめぐる冒険／第{seq}断片／{title}' if track=='story' else f'情報破壊業KK／{title}'
            out.append({
                'id':ident,'date':legacy.DAY,'created_at':legacy.STAMP,'kind':'generated',
                'track':track,'story_sequence':seq,'speaker':speaker,'title':display_title,
                'source':f'{speaker}／{display_title}（生成AIによる創作）',
                'text':body,'model':model,
                'provenance':'Gemini API無料枠による創作。SとAは作品内の架空人物。実在の証言ではない。',
            })
        legacy.AI_OUTCOME.update(status='ok',detail='',new=len(out))
        return out
    except Exception as exc:
        legacy.AI_OUTCOME.update(status='error',detail=f'{type(exc).__name__}: {str(exc)[:180]}',new=0)
        print('Gemini v5 generation failed:',type(exc).__name__,str(exc)[:260],file=sys.stderr)
        return []


def tune_collection():
    old_due=legacy.due
    old_wiki=legacy.fetch_multilingual_many
    old_aozora=legacy.fetch_aozora_many
    def due(state,key,minutes,legacy_key=None):
        if key=='external_last_attempt': minutes=24*60
        if key=='aozora_last_attempt': minutes=24*60
        return old_due(state,key,minutes,legacy_key)
    def wiki(limit=40,known=None):
        return old_wiki(limit=min(int(limit),3),known=known)
    def aozora(count=5,known=None):
        return old_aozora(count=min(int(count),2),known=known)
    legacy.due=due
    legacy.fetch_multilingual_many=wiki
    legacy.fetch_aozora_many=aozora
    legacy.generate_ai=generate_ai_v5


def run():
    tune_collection()
    report=legacy.run()
    build_catalog()
    health_file=legacy.DATA/'health.json'
    if health_file.exists():
        health=json.loads(health_file.read_text(encoding='utf-8'))
        health['v5_policy']={'story_documents_per_ai_success':3,'kk_documents_per_ai_success':1,
                             'wikipedia_max_per_day':3,'aozora_max_per_day':2,
                             'stream_target_percent':{'story':70,'kk':20,'external':10}}
        # The v4 engine reports the requested (up to 40) budget before our
        # wrapper caps it; health.json should report the effective cap.
        if isinstance(health.get('wikipedia'),dict) and 'target_max' in health['wikipedia']:
            health['wikipedia']['target_max']=3
        if isinstance(health.get('aozora'),dict) and health['aozora'].get('status')!='not_due':
            health['aozora']['target_max']=2
        # The original 2-hour staleness flag applied to the older 15-minute
        # external collection schedule; 24-hour sampling is deliberate now.
        state=legacy.get_json(legacy.DATA/'state.json',{})
        last=state.get('external_last') if isinstance(state,dict) else None
        try:
            age=(legacy.NOW-dt.datetime.fromisoformat(last)).total_seconds()
            health['stale_external_collection']=age>72*3600
        except (TypeError,ValueError):
            health['stale_external_collection']=True
        health_file.write_text(json.dumps(health,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    if '--rebuild' in sys.argv:
        legacy.rebuild()
        build_catalog()
    else:
        run()
