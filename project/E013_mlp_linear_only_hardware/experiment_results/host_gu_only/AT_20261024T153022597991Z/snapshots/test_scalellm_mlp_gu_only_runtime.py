"""CPU task/lease contracts with explicit mock transport; no hardware claim."""
import dataclasses
import threading
import unittest

import numpy as np

from host import scalellm_mlp_gu_only_abi as abi
from host.scalellm_mlp_gu_only import DownWeights
from host.scalellm_mlp_gu_only_runtime import (GuCompletion,GuDescriptor,GuOnlyPipeline,
                                               validate_gu_only_abi)
from host.scalellm_runtime import RuntimeContractError


class Backend:
    def __init__(self):
        self.calls=[];self.acks=[];self.descriptors=[];self.buffer=bytearray(1376256)
        self.identity={**abi.IDS,'capabilities':abi.CAPABILITIES}
        self.quiet=True;self.prefetch_hook=None;self.ack_hook=None;self.completion_hook=None
    def discover(self):return self.identity
    def stage_gu_layer(self,layer_id,epoch_id):
        self.calls.append(('stage_GU',layer_id,epoch_id));return layer_id+1
    def run_attention(self,cohort,layer,previous):
        self.calls.append(('Attention',cohort,layer,previous));return None
    def run_gu(self,descriptor,payload):
        self.descriptors.append(descriptor);self.calls.append(('GU',descriptor))
        self.buffer[0]=descriptor.layer_id*2+descriptor.cohort_id
        result=GuCompletion(descriptor,self.buffer)
        return self.completion_hook(result) if self.completion_hook else result
    def ack_gu(self,command_id):
        self.acks.append(command_id);self.calls.append(('ACK',command_id))
        self.buffer[0]=255 # Host-owned copy must survive reuse of transport buffer.
        if self.ack_hook:self.ack_hook(command_id)
    def quiescent(self):return self.quiet
    def release_gu_layer(self,layer_id,epoch_id):self.calls.append(('release_FPGA',layer_id,epoch_id))
    def prefetch_gu_layer(self,layer_id):
        self.calls.append(('prefetch_GU',layer_id))
        if self.prefetch_hook:self.prefetch_hook(layer_id)


def weights(layer):
    return DownWeights(np.full((448,16,32),layer%16-8,np.int8),
                       np.ones((448,16),np.uint8),np.full((448,16),6,np.uint8),layer_id=layer)


def mock_cpu_down(payload,handle):
    if payload[0]//2!=handle.layer_id:raise AssertionError('transport overwrite corrupted owned GU copy')
    return np.full((16,4096),handle.layer_id*10+payload[0]%2,np.int64)


class GuOnlyRuntimeTests(unittest.TestCase):
    def test_32layer_two_cohort_CPU_graph_has128_hardware_commands_and_no_Down(self):
        backend=Backend();consumed=[]
        def after(cohort,layer,result):
            consumed.append((cohort,layer));return int(result[0,0])
        pipeline=GuOnlyPipeline(backend,weights,after,cpu_down=mock_cpu_down,prepare_gu=lambda x:bytes(73728))
        report=pipeline.run(request_id=9)
        self.assertEqual(report['hardware_commands'],128)
        self.assertEqual((report['attention_commands'],report['gu_commands'],report['cpu_down_tasks'],report['hardware_down_commands']),(64,64,64,0))
        self.assertEqual(len(backend.acks),64)
        self.assertEqual(len(consumed),64)
        self.assertTrue(all(d.opcode==1 and d.down_half0_base==d.down_half1_base==0 for d in backend.descriptors))
        self.assertEqual({c[0] for c in backend.calls},{'Attention','GU','ACK','stage_GU','release_FPGA','prefetch_GU'})
        self.assertFalse(pipeline.host_leases);self.assertIsNone(pipeline.fpga_lease)
        events=report['events']
        for layer in range(32):
            release=next(i for i,x in enumerate(events) if x['event']=='fpga_epoch_release' and x['layer']==layer)
            for cohort in (0,1):
                copied=next(i for i,x in enumerate(events) if x['event']=='gu_output_copied' and x['layer']==layer and x['cohort']==cohort)
                ack=next(i for i,x in enumerate(events) if x['event']=='gu_acked' and x['layer']==layer and x['cohort']==cohort)
                self.assertLess(copied,ack);self.assertLess(ack,release)
        # These mock tests prove graph/count/identity only, not numerical32layer/model performance.

    def test_FPGA_lease_releases_while_CPU_and_residual_retain_immutable_layer_handle(self):
        backend=Backend();consumer_entered=threading.Event();allow_consumer=threading.Event();observed=[]
        def after(cohort,layer,result):
            if layer==0:
                consumer_entered.set()
                if not allow_consumer.wait(10):raise AssertionError('consumer dependency deadlock')
            return (layer,cohort)
        pipeline=GuOnlyPipeline(backend,weights,after,cpu_down=mock_cpu_down,prepare_gu=lambda x:bytes(73728),layers=2)
        def prefetch(layer):
            if layer==1:
                self.assertTrue(consumer_entered.wait(10))
                self.assertIsNone(pipeline.fpga_lease)
                self.assertTrue(pipeline.host_leases)
                for lease in pipeline.host_leases.values():
                    self.assertEqual(lease.layer_id,0)
                    self.assertEqual(int(lease.weights.values[0,0,0]),-8)
                    self.assertIsInstance(lease.gu_payload,bytes)
                    with self.assertRaises(ValueError):lease.weights.values.setflags(write=True)
                observed.append(True);allow_consumer.set()
        backend.prefetch_hook=prefetch
        pipeline.run()
        self.assertEqual(observed,[True])
        self.assertFalse(pipeline.host_leases)
        events=pipeline.events
        for cohort in (0,1):
            old_consumed=next(i for i,x in enumerate(events) if x['event']=='host_consumer_retired' and x['layer']==0 and x['cohort']==cohort)
            new_copy=next(i for i,x in enumerate(events) if x['event']=='gu_output_copied' and x['layer']==1 and x['cohort']==cohort)
            self.assertLess(old_consumed,new_copy)

    def test_wrong_completion_stops_before_ACK_or_CPU_success(self):
        backend=Backend()
        backend.completion_hook=lambda result:dataclasses.replace(result,descriptor=dataclasses.replace(result.descriptor,command_id=999))
        pipeline=GuOnlyPipeline(backend,weights,lambda *x:None,cpu_down=mock_cpu_down,prepare_gu=lambda x:bytes(73728),layers=1)
        with self.assertRaisesRegex(RuntimeContractError,'completion'):pipeline.run()
        self.assertEqual(backend.acks,[])
        self.assertFalse(any(x['event']=='host_down_done' for x in pipeline.events))
        self.assertIsNotNone(pipeline.fpga_lease)

    def test_no_release_without_real_backend_quiescence(self):
        backend=Backend();backend.quiet=False
        pipeline=GuOnlyPipeline(backend,weights,lambda *x:None,cpu_down=mock_cpu_down,prepare_gu=lambda x:bytes(73728),layers=1)
        with self.assertRaisesRegex(RuntimeContractError,'drained'):pipeline.run()
        self.assertFalse(any(x[0]=='release_FPGA' for x in backend.calls))
        self.assertTrue(pipeline.host_leases)

    def test_CPU_failure_retains_host_lease_and_does_not_create_Down_completion(self):
        backend=Backend()
        def fail(*args):raise RuntimeContractError('numeric Down failure')
        pipeline=GuOnlyPipeline(backend,weights,lambda *x:None,cpu_down=fail,prepare_gu=lambda x:bytes(73728),layers=2)
        with self.assertRaisesRegex(RuntimeContractError,'numeric'):pipeline.run()
        self.assertTrue(pipeline.host_leases)
        self.assertFalse(any(x['event']=='host_consumer_retired' for x in pipeline.events))
        self.assertFalse(any(x[0]=='stage_GU' and x[1]==1 for x in backend.calls))

    def test_v7_discovery_rejects_v6_unknown_caps_and_missing_identity_before_any_command(self):
        for changed in ({'mlp_control_abi':0x00060000},{'linear_abi':0x4d4c0001},{'capabilities':0x1f},{'capabilities':0x1c},{'weight_layout':7}):
            backend=Backend();backend.identity.update(changed)
            pipeline=GuOnlyPipeline(backend,weights,lambda *x:None,layers=1)
            with self.assertRaises(RuntimeContractError):pipeline.run()
            self.assertEqual(backend.calls,[])
        validate_gu_only_abi({**abi.IDS,'capabilities':0x1d})

    def test_opcode2_high_bits_zero_and_reserved_Down_fields_reject(self):
        fields=dict(command_id=0,request_id=0,cohort_id=1,layer_id=31,buffer_id=5,buffer_generation=1,metadata_generation=1,epoch_id=1)
        for opcode in (0,2,0x101,0x10000001):
            with self.assertRaisesRegex(RuntimeContractError,'opcode1'):GuDescriptor(**fields,opcode=opcode)
        for key in ('down_half0_base','down_half1_base'):
            with self.assertRaisesRegex(RuntimeContractError,'reserved'):GuDescriptor(**fields,**{key:4})
        descriptor=GuDescriptor(**fields)
        self.assertEqual(len(descriptor.pack()),68)
        self.assertEqual(descriptor.words()[4],1);self.assertEqual(descriptor.words()[-2:],(0,0))
        self.assertEqual(descriptor.words()[6],0x12800000)
        self.assertEqual(descriptor.words()[7],0x12900000)
        self.assertEqual(int.from_bytes(descriptor.pack()[8:12],'little'),0x00050001)

    def test_command_epoch_and_slot_generations_do_not_repeat_across_runs(self):
        backend=Backend();pipeline=GuOnlyPipeline(backend,weights,lambda c,l,x:int(x[0,0]),cpu_down=mock_cpu_down,prepare_gu=lambda x:bytes(73728),layers=2)
        pipeline.run();pipeline.run(request_id=1)
        self.assertEqual(len({d.command_id for d in backend.descriptors}),8)
        self.assertEqual(len({d.epoch_id for d in backend.descriptors}),4)
        seen=set()
        for d in backend.descriptors:
            self.assertNotIn((d.buffer_id,d.buffer_generation),seen);seen.add((d.buffer_id,d.buffer_generation))


if __name__=='__main__':unittest.main()
