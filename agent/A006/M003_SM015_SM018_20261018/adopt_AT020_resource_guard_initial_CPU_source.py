# Exact inline CPU body preserved AFTER execution from tool call chunk9990b4.
# This file has not been re-executed and is not a pre-execution file archive.
import importlib.util
from pathlib import Path
p=Path('agent/A006/M003_SM015_SM018_20261018/adopt_AT020_resource_guard.py');sp=importlib.util.spec_from_file_location('g',p);g=importlib.util.module_from_spec(sp);sp.loader.exec_module(g);G=g.GIB
assert g.resource_reason(12*G,480*G,440*G,None,999999) is None
assert g.resource_reason(193*G,480*G,440*G,None,0)=='owned_tree_RSS_above_192GiB'
assert g.resource_reason(12*G,47*G,440*G,0,29.9) is None
assert g.resource_reason(12*G,47*G,440*G,0,30)=='MemAvailable_below_48GiB_for_30s'
assert g.resource_reason(12*G,480*G,29*G,None,0)=='disk_free_below_30GiB'
t={pid:dict(start_ticks=start,pgrp=g.LEADER) for pid,start in g.EXPECTED.items()};g.verify_initial(t)
t[86095]['start_ticks']+=1
try:g.verify_initial(t)
except RuntimeError:pass
else:raise AssertionError('PIDreuse accepted')
print('7 bounded protection/PID cases PASS; no native controls used')
