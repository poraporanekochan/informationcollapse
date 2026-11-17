import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ENGINE=Path(__file__).resolve().parents[1]/'engine'
sys.path.insert(0,str(ENGINE))
import build_v5_catalog as catalog
import run_v5


class TestV5(unittest.TestCase):
    def test_parser_accepts_both_gemini_json_shapes(self):
        data=[{'speaker':'久野','type':'校正','text':'X'}]
        self.assertEqual(run_v5.parse_gemini_records(data),data)
        self.assertEqual(run_v5.parse_gemini_records({'records':data}),data)
        with self.assertRaises(ValueError):
            run_v5.parse_gemini_records({'records':'invalid'})

    def test_catalog_retains_all_and_classifies(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'data/shards/generated').mkdir(parents=True)
            (root/'data/shards/fiction').mkdir(parents=True)
            (root/'data/shards/external').mkdir(parents=True)
            rows=[
                {'id':'s1','kind':'fiction','text':'Sの文章'},
                {'id':'s2','kind':'generated','track':'story','text':'物語の断片'},
                {'id':'k1','kind':'generated','track':'kk','text':'組織の記録'},
                {'id':'e1','kind':'external','text':'外部引用'},
            ]
            groups={'fiction':[rows[0]],'generated':[rows[1],rows[2]],'external':[rows[3]]}
            shards=[]
            for k,records in groups.items():
                path=f'data/shards/{k}/a.json'
                (root/path).write_text(json.dumps({'records':records}),encoding='utf-8')
                shards.append({'id':f'{k}/a','url':path,'rev':'x','count':len(records),'kind':k})
            (root/'data/catalog.json').write_text(json.dumps({'schema_version':4,'as_of':'today','shards':shards}),encoding='utf-8')
            (root/'data/seed.json').write_text(json.dumps(rows[:1]),encoding='utf-8')
            (root/'data/generated.jsonl').write_text('\n'.join(json.dumps(r) for r in rows[1:3])+'\n',encoding='utf-8')
            (root/'data/external.jsonl').write_text(json.dumps(rows[3])+'\n',encoding='utf-8')
            output=catalog.build(root)
            self.assertEqual(output['record_count'],4)
            self.assertEqual(output['group_counts'],{'story':2,'kk':1,'external':1})
            self.assertEqual(sum(output['group_counts'].values()),4)
            self.assertTrue((root/'data/v5_catalog.json').exists())

    def test_gemini_array_response_generates_story_sequence(self):
        four=[{'speaker':'語り手','type':'記録','text':'文字' * 100} for _ in range(4)]
        payload={'candidates':[{'content':{'parts':[{'text':json.dumps(four,ensure_ascii=False)}]}}]}
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake-test-key','GEMINI_MODEL':'gemini-3.5-flash-lite'}):
            with patch.object(run_v5.legacy,'request',return_value=(json.dumps(payload).encode(),{})):
                with patch.object(run_v5,'story_context',return_value=(0,[])):
                    result=run_v5.generate_ai_v5()
        self.assertEqual([r['track'] for r in result],['story','story','story','kk'])
        self.assertEqual([r['story_sequence'] for r in result[:3]],[1,2,3])
        self.assertTrue(all(r['kind']=='generated' for r in result))


if __name__=='__main__':unittest.main()
