"""Original exporter record producer and strict legacy artifact adapter tests."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from host.scalellm_artifacts import LAYER_ARTIFACT_SIZES, ROPE_BYTES
from host.scalellm_mlp_gu_only import DownWeights
from host.scalellm_mlp_gu_only_artifacts import GuOnlyArtifactManifest
from host.scalellm_runtime import RuntimeContractError
from model.export_scalellm_llama31_artifacts import _write_mlp_tile


class OriginalExporterTests(unittest.TestCase):
    def test_real_exporter_write_mlp_tile_group_major_to_Host_decoder(self):
        groups,columns=448,32
        g=np.arange(groups)[:,None,None];c=np.arange(columns)[None,:,None];k=np.arange(32)[None,None,:]
        w=((g*7+c*3+k*11)%16-8).astype(np.int8)
        codes=(1+(g[...,0]*5+c[...,0]*7)%255).astype(np.uint8)
        shifts=((g[...,0]*3+c[...,0]*5)%64).astype(np.uint8)
        writers={key:io.BytesIO() for key in ('c0','c1','meta')}
        # Exactly the original export_mlp Down record traversal; actual original
        # _write_mlp_tile calls pack_w4 and pack_mlp_meta, not our test packer.
        for group in range(groups):
            for start in range(0,columns,16):
                _write_mlp_tile(writers,w[group,start:start+16,None,:],
                                codes[group,start:start+16,None],shifts[group,start:start+16,None],1)
        actual=DownWeights.from_records(*(writers[key].getvalue() for key in ('c0','c1','meta')),columns=columns)
        np.testing.assert_array_equal(actual.values,w)
        np.testing.assert_array_equal(actual.codes,codes)
        np.testing.assert_array_equal(actual.shifts,shifts)


class StrictManifestAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        def record(name,size):
            path=cls.root/name
            with path.open('wb') as stream:stream.truncate(size)
            return {'path':name,'size':size,'sha256':'0'*64}
        # Sparse catalog fixtures only; not model/hash validation. Default
        # verify_hashes=True is tested to reject these deliberately false SHAs.
        layers=[]
        for layer in range(32):
            layers.append({'layer_id':layer,'artifacts':{name:record(f'{layer}_{name}.bin',size) for name,size in LAYER_ARTIFACT_SIZES.items()}})
        cls.raw=dict(schema_version=2,model_id='meta-llama/Llama-3.1-8B-Instruct',checkpoint_id='1'*64,
                     checkpoint_sha256='1'*64,layer_count=32,attention_format_id=0x48384103,
                     attention_abi=0x00020000,mlp_format_id=0x48384605,mlp_abi=0x00050000,
                     rope=record('rope.bin',ROPE_BYTES),layers=layers)
        cls.path=cls.root/'manifest.json'
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def write_manifest(self,raw):self.path.write_text(json.dumps(raw));return self.path
    def test_schema2_original_v5_and_schema3_catalog_strict_size_order(self):
        original=self.write_manifest(self.raw).read_bytes()
        result=GuOnlyArtifactManifest.load(self.path,verify_hashes=False)
        self.assertEqual(result.schema_version,2);self.assertEqual(result.weight_layout_id,0x57344635)
        self.assertEqual(self.path.read_bytes(),original)
        schema3=copy.deepcopy(self.raw);schema3['schema_version']=3;del schema3['mlp_abi'];schema3['mlp_weight_layout_id']=0x57344635
        self.assertEqual(GuOnlyArtifactManifest.load(self.write_manifest(schema3),verify_hashes=False).schema_version,3)
    def test_default_hash_verification_and_Down_read_cannot_be_bypassed_by_catalog_mode(self):
        self.write_manifest(self.raw)
        with self.assertRaisesRegex(RuntimeContractError,'SHA256'):GuOnlyArtifactManifest.load(self.path)
        catalog=GuOnlyArtifactManifest.load(self.path,verify_hashes=False)
        with self.assertRaisesRegex(RuntimeContractError,'SHA256'):catalog.down_weights(0)
    def test_reject_path_size_duplicate_layers_and_unknown_fields(self):
        broken=[]
        x=copy.deepcopy(self.raw);x['layers'][1]['layer_id']=0;broken.append(x)
        x=copy.deepcopy(self.raw);x['layers'][0]['artifacts']['mlp_down_c0']['size']-=1;broken.append(x)
        x=copy.deepcopy(self.raw);x['layers'][0]['artifacts']['mlp_down_c0']['path']='../escape.bin';broken.append(x)
        x=copy.deepcopy(self.raw);x['layers'][1]['artifacts']['mlp_down_c0']=x['layers'][0]['artifacts']['mlp_down_c0'];broken.append(x)
        x=copy.deepcopy(self.raw);x['unexpected']=0;broken.append(x)
        for raw in broken:
            with self.assertRaises(RuntimeContractError):GuOnlyArtifactManifest.load(self.write_manifest(raw),verify_hashes=False)


if __name__=='__main__':unittest.main()
