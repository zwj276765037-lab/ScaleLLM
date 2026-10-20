"""Falsifiable strict checks for actual native export-completeness audit."""
import copy,unittest
from check_native_boundary_exports import ANCHORS,CORE,verify,names

def fixture():
 cs={k:v+' alias_'+k for k,v in ANCHORS.items()};cs.update(clock_group='G0',clock_pin='clkbuf/O')
 raw=dict(schema='M003_native_grouped_stream_v1',meta=dict(kind='native'),cells=[],helper_pins=[],memory_pins=[],control_sources=cs,connection_groups=[dict(id='G0',nets=[CORE+'/core_clk'],canonical_top_net=CORE+'/core_clk',leaf_drivers=['clkbuf/O'],driver_cells=['clkbuf'],driver_refs=['BUFGCE'],primary_ports=[],primary_port_directions=[])],connection_endpoints=[dict(pin='clkbuf/O',group='G0',direct_nets=[CORE+'/core_clk'])],connection_counts=dict(groups=1,endpoints=1),connection_api_counts={k:dict(calls=1) for k in ['segments','drivers','canonical','ports']})
 events=[dict(event='boundary_source_selected',tag=k,anchor=v,segment_count='2') for k,v in ANCHORS.items()];events.append(dict(event='boundary_clock_source',anchor=CORE+'/core_clk',endpoint='clkbuf/O',group='G0'))
 return raw,events
class Exports(unittest.TestCase):
 def test_valid_full_exports_and_Tcl_lists(self):
  self.assertTrue(verify(*fixture())['passed']);self.assertEqual(names('{a[0]} b'),['a[0]','b']);self.assertEqual(names('a {} b'),['a','','b'])
 def test_each_source_short_empty_duplicate_or_foreign_rejected(self):
  for tag,anchor in ANCHORS.items():
   for text in [anchor,anchor+' {}',anchor+' '+anchor,'foreign alias']:
    with self.subTest(tag=tag,text=text):
     raw,events=fixture();raw['control_sources'][tag]=text
     with self.assertRaises(ValueError):verify(raw,events)
 def test_missing_duplicate_or_forged_native_events_reject(self):
  for mode in ['missing','duplicate','wrong_anchor','wrong_count','wrong_clock_anchor','wrong_clock_source']:
   raw,events=fixture()
   if mode=='missing':events.pop(0)
   if mode=='duplicate':events.append(copy.deepcopy(events[0]))
   if mode=='wrong_anchor':events[0]['anchor']='foreign'
   if mode=='wrong_count':events[0]['segment_count']='1'
   if mode=='wrong_clock_anchor':events[-1]['anchor']='foreign'
   if mode=='wrong_clock_source':events[-1]['endpoint']='sink/C'
   with self.subTest(mode=mode):
    with self.assertRaises(ValueError):verify(raw,events)
 def test_group_source_membership_and_K_cost_reject(self):
  for mode in ['foreignclock','dualsource','notK']:
   raw,events=fixture()
   if mode=='foreignclock':raw['connection_groups'][0]['nets']=['wrongclk'];raw['connection_groups'][0]['canonical_top_net']='wrongclk';raw['connection_endpoints'][0]['direct_nets']=['wrongclk']
   if mode=='dualsource':raw['connection_groups'][0]['primary_ports']=['clk'];raw['connection_groups'][0]['primary_port_directions']=['IN']
   if mode=='notK':raw['connection_api_counts']['segments']['calls']=2
   with self.subTest(mode=mode):
    with self.assertRaises(ValueError):verify(raw,events)
if __name__=='__main__':unittest.main(verbosity=2)
