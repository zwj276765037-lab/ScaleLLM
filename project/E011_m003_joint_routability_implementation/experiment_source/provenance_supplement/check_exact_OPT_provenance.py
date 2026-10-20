"""External actual-state supplement; does not change or impersonate live admission."""
from pathlib import Path
import argparse,copy,json,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'AT034_OPT_POST_requalification'))
import qualified_opt_evidence as e
r=e.r

def strict_equal(current,frozen):
    return json.dumps(current,sort_keys=True,separators=(',',':'),allow_nan=False)==json.dumps(frozen,sort_keys=True,separators=(',',':'),allow_nan=False)

def check(output):
    package=e.HERE/'qualified_OPT_debug_dependency_package.json';value=json.loads(package.read_text());r.old.verify_identity(value['qualified_OPT_POST'])
    receipt=json.loads(Path(value['qualified_OPT_POST']['path']).read_text());r.old.verify_identity(receipt['binding']);frozen=json.loads(Path(receipt['binding']['path']).read_text());current=e.q.provenance()
    r.old.require(strict_equal(current,frozen),'current actual M003 provenance differs from qualified frozen binding')
    for row in frozen['anchors']+frozen['reports']:r.old.verify_identity(row)
    for row in frozen['producers']:r.old.verify_identity(row['original']);r.old.verify_identity(row['preserved'])
    identity=next(row for row in receipt['outputs'] if Path(row['path']).name=='integrity_opt.json');r.old.verify_identity(identity);facts=json.loads(Path(identity['path']).read_text())
    r.old.verify_reset_proof(facts['reset_structure']);r.old.verify_cdc_proof(facts['cdc_classification'])
    negatives=[]
    for field in ['anchors','reports','producers']:
        for index in range(len(frozen[field])):
            changed=copy.deepcopy(current)
            if field=='producers':changed[field][index]['original']['sha256']='0'*64
            else:changed[field][index]['sha256']='0'*64
            r.old.require(not strict_equal(changed,frozen),'changed provenance identity was not rejected');negatives.append(dict(field=field,index=index,rejected=True))
    for field,number in [('object_limit',True),('raw_UNKNOWN_retained',1)]:
        changed=copy.deepcopy(current);changed[field]=number;r.old.require(not strict_equal(changed,frozen),'provenance JSON type change admitted');negatives.append(dict(field=field,type_change=True,rejected=True))
    result=dict(observed_utc=r.stage.now(),completed=True,new_EDA=False,source=r.old.file_id(Path(__file__)),exact_current_provenance_equals_frozen=True,comparison='canonical deterministic JSON; all fields, values and JSON types',frozen_binding=receipt['binding'],qualified_OPT_POST=value['qualified_OPT_POST'],dependency_package=r.old.file_id(package),anchors=len(frozen['anchors']),reports=len(frozen['reports']),producers=len(frozen['producers']),nested_reset_exports_and_models_verified=True,nested_CDC_proof_sources_verified=True,negative_mutations=negatives,live_entry_guard_was_modified=False,applicability='Current actual OPT-source consistency supplement only; live AT035 frozen entry equality gap remains a bounded future hardening item. No debug identity/safety/G4 admission is claimed.',formal_reset_cdc_safety='OPEN',G4=False)
    r.save(output,result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();x=check(a.output.resolve());print(json.dumps(dict(exact_current_equals_frozen=True,negative_mutations=len(x['negative_mutations']),live_sources_changed=False,new_EDA=False)))
