#!/usr/bin/env python3
"""Verify that all structured records have a durable, complete published index."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from catalog import canonical_records, read_json, read_jsonl


def verify(root: Path):
    data=root/'data'
    manifest=read_json(data/'catalog.json',None)
    stats=read_json(data/'stats.json',None)
    if not isinstance(manifest,dict) or manifest.get('schema_version')!=4:
        raise ValueError('catalog missing or not v4')
    if not isinstance(stats,dict):
        raise ValueError('stats missing')
    seed=read_json(data/'seed.json',[])
    gen=read_jsonl(data/'generated.jsonl')
    external=read_jsonl(data/'external.jsonl')
    expected=canonical_records(seed,gen,external)
    ids=set()
    count=0
    for shard in manifest.get('shards',[]):
        # The URL is a repo-relative path controlled by catalog.py, not user input.
        path=root/shard['url']
        parsed=read_json(path,None)
        if not isinstance(parsed,dict) or not isinstance(parsed.get('records'),list):
            raise ValueError(f'bad shard: {path}')
        if len(parsed['records'])!=shard['count']:
            raise ValueError(f'shard count mismatch {shard["url"]}')
        for row in parsed['records']:
            if row['id'] in ids:raise ValueError('duplicate record id in shards')
            ids.add(row['id'])
            count+=1
    expected_ids={r['id'] for r in expected}
    if ids!=expected_ids:
        raise ValueError(f'catalog missing {len(expected_ids-ids)} or extra {len(ids-expected_ids)} records')
    if manifest['record_count']!=count or int(stats['unique_visible_record_count'])!=count:
        raise ValueError('manifest/stats count mismatch')
    files=list((root/'archive').glob('*/*.txt'))
    bits=sum(p.stat().st_size for p in files)*8
    if int(stats['published_bits'])!=bits:
        raise ValueError('published_bits incorrect')
    return {'unique':count,'shards':len(manifest['shards']),'archive_bits':bits}


if __name__=='__main__':
    result=verify(Path(__file__).resolve().parents[1])
    print('ARCHIVE_VERIFIED',json.dumps(result,ensure_ascii=False))
