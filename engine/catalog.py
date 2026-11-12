#!/usr/bin/env python3
"""Build a complete, lazily-loadable public catalogue from durable structured logs.

Only structured records from seed.json, generated.jsonl and external.jsonl enter
this index. Original TXT records and JSONL logs are never removed or overwritten.
No network access or third-party dependencies are necessary.
"""
from __future__ import annotations
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

VALID_KINDS = {'fiction', 'generated', 'external', 'aozora'}


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def read_jsonl(path: Path):
    if not path.exists():
        return []
    items = []
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                items.append(item)
        except ValueError:
            print(f'WARN invalid JSONL {path.name}:{line_number}')
    return items


def norm_text(value: str) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', value)).strip().casefold()


def canonical_records(seed, generated, external):
    """Deduplicate same ID and exact normalized text; preserve oldest source.

    Duplicates remain in append-only source files for provenance but are not
    streamed repeatedly. Records carry real provenance; no invented sources.
    """
    by_id = set()
    by_text = set()
    unique = []
    for rec in [*seed, *generated, *external]:
        if not isinstance(rec, dict):
            continue
        key = rec.get('id')
        kind = rec.get('kind')
        body = rec.get('text')
        if not isinstance(key, str) or not key or kind not in VALID_KINDS:
            continue
        if not isinstance(body, str) or not body.strip() or len(body) > 4000:
            continue
        norm = norm_text(body)
        if len(norm) < 8 or key in by_id or norm in by_text:
            continue
        by_id.add(key)
        by_text.add(norm)
        safe = {
            field: rec[field] for field in
            ('id', 'date', 'created_at', 'kind', 'speaker', 'source',
             'title', 'text', 'language', 'url', 'rights', 'provenance', 'model')
            if field in rec and isinstance(rec[field], (str, int))
        }
        unique.append(safe)
    return unique


def write_if_changed(path: Path, payload) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    if path.is_file() and path.read_bytes() == body:
        return False
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(body)
    tmp.replace(path)
    return True


def build_catalog(root: Path, as_of: str):
    root = Path(root)
    data = root / 'data'
    seed = read_json(data/'seed.json', [])
    if not isinstance(seed, list):
        seed = []
    generated = read_jsonl(data/'generated.jsonl')
    external = read_jsonl(data/'external.jsonl')
    records = canonical_records(seed, generated, external)
    shards = defaultdict(list)
    for r in records:
        # Fixed shard identity prevents old records moving when new ones arrive.
        part = hashlib.sha256(r['id'].encode('utf-8')).hexdigest()[:2]
        shards[(r['kind'], part)].append(r)
    metadata = []
    root_shards = data / 'shards'
    paths = set()
    for (kind, prefix), members in sorted(shards.items()):
        members.sort(key=lambda x: x['id'])
        rel = f'data/shards/{kind}/{prefix}.json'
        dest = root / rel
        write_if_changed(dest, {'records': members})
        paths.add(dest)
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()[:12]
        metadata.append({
            'id': f'{kind}/{prefix}', 'kind': kind, 'url': rel,
            'count': len(members), 'rev': digest,
        })
    # Delete ONLY obsolete, derived shard files; NEVER delete archives / logs.
    if root_shards.exists():
        for old in root_shards.glob('*/*.json'):
            if old not in paths:
                old.unlink()
    kinds = {kind: sum(1 for r in records if r['kind'] == kind)
             for kind in sorted(VALID_KINDS)}
    manifest = {
        'schema_version': 4,
        'as_of': as_of,
        'record_count': len(records),
        'kinds': kinds,
        'shards': metadata,
        'scope': 'All structured public records in seed.json + generated.jsonl + external.jsonl, deduplicated.',
    }
    write_if_changed(data/'catalog.json', manifest)
    # Older clients still receive a bounded recent sample, but v4 uses ALL shards.
    newest = [*seed[-100:], *generated[-150:], *external[-150:]]
    newest = canonical_records(newest, [], [])
    write_if_changed(data/'latest.json', {'as_of': as_of, 'records': newest})
    return {'record_count': len(records), 'kinds': kinds, 'shard_count': len(metadata)}


if __name__ == '__main__':
    import argparse
    from datetime import datetime
    from zoneinfo import ZoneInfo
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    a = p.parse_args()
    print(build_catalog(a.root, datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')))
