"""Build a non-destructive, story-first streaming index from the v4 archive.

The source of truth stays in seed.json, generated.jsonl, external.jsonl and
archive/. The v4 shards remain unchanged and usable by old clients.
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path):
    if not path.exists():
        return []
    out=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            obj=json.loads(line)
            if isinstance(obj,dict):out.append(obj)
    return out


def classify(record):
    kind=record.get('kind')
    if kind in ('external','aozora'):
        return 'external'
    explicit=record.get('track')
    if explicit in ('story','kk'):
        return explicit
    if kind=='fiction':
        return 'story'
    meta=' '.join(str(record.get(k,'')) for k in ('speaker','source','title'))
    # Older generated documents have no track field; this is an editorial
    # classification, not a claim that they are historical records.
    kk_terms=('業務報告','第八界','機械の故障','出勤簿','見積書','設備管理',
              '経費精算','棚卸し','行政照会','現地調査','文書管理','自己観察')
    if any(term in meta for term in kk_terms):
        return 'kk'
    return 'story'


def build(root: Path=ROOT):
    data=root/'data'
    original=json.loads((data/'catalog.json').read_text(encoding='utf-8'))
    if original.get('schema_version')!=4:
        raise ValueError('v4 catalog is missing or unsupported')
    seed=json.loads((data/'seed.json').read_text(encoding='utf-8'))
    generated=read_jsonl(data/'generated.jsonl')
    external=read_jsonl(data/'external.jsonl')
    by_id={r['id']:r for r in seed+generated+external if r.get('id')}
    groups={'story':[],'kk':[],'external':[]}
    assigned_ids=set()
    for shard in original.get('shards',[]):
        shard_file=root/shard['url']
        content=json.loads(shard_file.read_text(encoding='utf-8'))
        members={'story':[],'kk':[],'external':[]}
        for r in content['records']:
            rid=r['id']
            if rid not in by_id:
                raise ValueError(f'shard entry {rid} lacks original record')
            if rid in assigned_ids:
                raise ValueError(f'duplicate record id {rid}')
            assigned_ids.add(rid)
            members[classify(by_id[rid])].append(rid)
        for group,ids in members.items():
            if ids:
                groups[group].append({
                    'id':shard['id'], 'url':shard['url'], 'rev':shard['rev'],
                    'count':len(ids), 'record_ids':ids,
                })
    if assigned_ids != set(by_id):
        raise ValueError(f'missing from v4 shards: {len(set(by_id)-assigned_ids)} records')
    counts={name:sum(x['count'] for x in shards) for name,shards in groups.items()}
    if sum(counts.values())!=len(by_id):
        raise ValueError('record count does not match')
    result={
        'schema_version':5,
        'as_of':original['as_of'],
        'record_count':len(by_id),
        'target_mix':{'story':70,'kk':20,'external':10},
        'group_counts':counts,
        'groups':groups,
        'note':'Published source records are retained verbatim. Group labels are editorial stream categories.',
    }
    path=data/'v5_catalog.json'
    path.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    result=build()
    print('V5_CATALOG',json.dumps({'total':result['record_count'],'groups':result['group_counts']},ensure_ascii=False))
