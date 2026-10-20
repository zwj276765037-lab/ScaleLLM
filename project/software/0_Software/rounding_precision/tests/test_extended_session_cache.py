import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from extended_session_cache import ExtendedSessionCache


class SessionCacheTests(unittest.TestCase):
    def test_two_groups_one_assembly_and_context_restore(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);count={'base':0,'attach':0,'head':0};base=object();audit=object()
            def load(model_dir,device,directory):
                count['base']+=1;(directory/'stream_loader_validation.json').write_text(json.dumps({'base':'CPU test'}));return base
            def attach(model,**kwargs):count['attach']+=1;return dict(format='05'),audit
            def head(model_dir,device,evidence):
                count['head']+=1;evidence.mkdir(parents=True)
                source={'sha256':'same'};(evidence/'output_head_identity.json').write_text(json.dumps(source))
                return types.SimpleNamespace(source=source)
            loader=types.SimpleNamespace(load_streamed_bf16_model=load)
            compat=types.SimpleNamespace(attach_v5_fullchain_compatible=attach)
            heads=types.SimpleNamespace(load_output_head=head)
            cache=ExtendedSessionCache(directory/'session',directory/'model')
            with cache.context(loader,compat,heads):
                seen=[]
                for group in range(2):
                    b=loader.load_streamed_bf16_model(directory/'model','cuda:0',directory/f'g{group}')
                    meta,a=compat.attach_v5_fullchain_compatible(types.SimpleNamespace(model=b),checkpoint_dir=directory/'model',device='cuda:0',strict=True)
                    meta['mutated_by_group']=group
                    h=heads.load_output_head(directory/'model','cuda:0',directory/f'g{group}/output_head')
                    seen.append((b,a,h))
                self.assertTrue(all(a is b for a,b in zip(seen[0],seen[1])))
                self.assertNotIn('mutated_by_group',cache.metadata)
                with self.assertRaisesRegex(ValueError,'options changed'):
                    compat.attach_v5_fullchain_compatible(types.SimpleNamespace(model=base),checkpoint_dir=directory/'model',device='cuda:0',strict=False)
            self.assertEqual(count,{'base':1,'attach':1,'head':1})
            self.assertIs(loader.load_streamed_bf16_model,load)
            self.assertIs(compat.attach_v5_fullchain_compatible,attach)
            self.assertIs(heads.load_output_head,head)
            self.assertEqual(len((directory/'session/session_cache_events.jsonl').read_text().splitlines()),6)

    def test_exception_and_changed_identity_are_bounded_and_restore(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            def original(*a,**k):
                if len(a)==3 and isinstance(a[2],Path):(a[2]/'stream_loader_validation.json').write_text('{}')
                return object()
            loader=types.SimpleNamespace(load_streamed_bf16_model=original)
            compat=types.SimpleNamespace(attach_v5_fullchain_compatible=original)
            heads=types.SimpleNamespace(load_output_head=original)
            cache=ExtendedSessionCache(p/'session',p/'model')
            with self.assertRaisesRegex(ValueError,'checkpoint changed'):
                with cache.context(loader,compat,heads):loader.load_streamed_bf16_model(p/'other','cpu',p/'group')
            self.assertIs(loader.load_streamed_bf16_model,original)
            with cache.context(loader,compat,heads):
                loader.load_streamed_bf16_model(p/'model','cpu',p/'group')
                with self.assertRaisesRegex(ValueError,'device changed'):
                    loader.load_streamed_bf16_model(p/'model','cuda:0',p/'group')


if __name__=='__main__':unittest.main()
