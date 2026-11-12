"""Strictly offline tests for durable archive, de-duplication and lazy manifest."""
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

ENGINE = pathlib.Path(__file__).resolve().parents[1] / 'engine'
sys.path.insert(0, str(ENGINE))
import catalog
import generate
import verify


def record(id, kind, text, date='20261112'):
    return {
        'id':id, 'kind':kind, 'date':date, 'created_at':date,
        'source':'fixture', 'text':text,
    }


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        (self.root/'data').mkdir()
        (self.root/'archive'/'1962').mkdir(parents=True)
        (self.root/'archive'/'1962'/'19620101.txt').write_text('historical source remains\n',encoding='utf-8')
        self.seed=[record('a','fiction','1962 old archival passage alpha',date='19620101'),
                   record('b','fiction','another archival passage beta',date='19820215'),
                   record('c','fiction','old archival passage gamma',date='20010101')]
        (self.root/'data'/'seed.json').write_text(json.dumps(self.seed,ensure_ascii=False),encoding='utf-8')

    def write_log(self,name,rows):
        (self.root/'data'/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')

    def test_catalog_indexes_every_structured_record_even_if_old(self):
        rows=[record(f'e{i}','external',f'Random Wikipedia excerpt {i}: some more text') for i in range(700)]
        rows += [record('copy','external','1962 old archival passage alpha')]
        self.write_log('external.jsonl',rows)
        self.write_log('generated.jsonl',[record('ai','generated','A speaks about the archived city')])
        info=catalog.build_catalog(self.root,'2026-11-12T12:00:00+09:00')
        self.assertEqual(info['record_count'],704)
        self.assertGreater(info['shard_count'],1)
        shards=json.loads((self.root/'data'/'catalog.json').read_text())['shards']
        ids={r['id'] for shard in shards for r in json.loads((self.root/shard['url']).read_text())['records']}
        self.assertIn('a',ids)
        self.assertIn('e699',ids)
        self.assertNotIn('copy',ids)
        self.assertEqual(len(ids),704)

    def test_rebuild_does_not_delete_raw_logs_or_archive(self):
        generated=[record('g1','generated','Generated fictional document with precise provenance')]
        external=[record('x1','external','Wikipedia sourced sentence from another language')]
        self.write_log('external.jsonl',external)
        self.write_log('generated.jsonl',generated)
        orig=(self.root/'archive'/'1962'/'19620101.txt').read_bytes()
        with patch.multiple(generate,ROOT=self.root,DATA=self.root/'data',ARCHIVE=self.root/'archive',CACHE=self.root/'cache'):
            result=generate.rebuild()
        self.assertEqual(result['unique_visible_record_count'],5)
        self.assertEqual(result['record_count'],5)
        self.assertEqual((self.root/'archive'/'1962'/'19620101.txt').read_bytes(),orig)
        self.assertEqual(verify.verify(self.root)['unique'],5)

    def test_one_actual_record_is_not_duplicated_by_retry(self):
        g=record('g9','generated','AI document generated once on a free tier call')
        x=record('x9','external','A Wikipedia sentence with a real-source URL')
        self.write_log('external.jsonl',[])
        self.write_log('generated.jsonl',[])
        moment=datetime(2026,11,12,12,0,0,tzinfo=ZoneInfo('Asia/Tokyo'))
        # No external requests occur, because the functions are mocked.
        with patch.multiple(generate, ROOT=self.root,DATA=self.root/'data',ARCHIVE=self.root/'archive',CACHE=self.root/'cache',NOW=moment,DAY='20261112',STAMP=moment.isoformat()), \
             patch.dict(os.environ,{'GEMINI_API_KEY':'DUMMY_KEY','GITHUB_EVENT_NAME':'test'}), \
             patch.object(generate,'generate_ai',return_value=[g]), \
             patch.object(generate,'fetch_aozora_many',return_value=[]), \
             patch.object(generate,'fetch_multilingual_many',return_value=[x]):
            first=generate.run()
            second=generate.run()
        self.assertEqual(first['new']['generated'],1)
        self.assertEqual(first['new']['external'],1)
        self.assertEqual(second['new']['generated'],0)
        self.assertEqual(second['new']['external'],0)
        self.assertEqual(len(catalog.read_jsonl(self.root/'data'/'generated.jsonl')),1)
        self.assertEqual(len(catalog.read_jsonl(self.root/'data'/'external.jsonl')),1)
        self.assertEqual(verify.verify(self.root)['unique'],5)


if __name__=='__main__':unittest.main()
