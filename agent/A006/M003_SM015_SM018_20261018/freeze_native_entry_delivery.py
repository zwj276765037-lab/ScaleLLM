from pathlib import Path
import hashlib,json,shutil,difflib,datetime
R=Path('.').resolve();E=R/'project/E011_m003_joint_routability_implementation';P=E/'experiment_source/R002_native_entry_fix';H=R/'project/hardware'
def fid(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
manifest=H/'vivado/constraints/m003_entry_manifest.json';current=json.loads(manifest.read_text());previous=json.loads((P/'entry_manifest_before_native_fix.json').read_text());old={x['path']:x for x in previous['sources']};new={x['path']:x for x in current['sources']};assert set(old)<=set(new) and len(new)==45
archive=json.loads((E/'experiment_results/runs/R002/attempts/AT003_fresh_selected_synthesis/evidence/jobs/fresh_synth/source_archive.json').read_text())['bindings'];original={x['original']['path']:Path(x['preserved']['path']) for x in archive}
out=P/'frozen_sources_v1';out.mkdir();diffs=P/'diffs_v1';diffs.mkdir();bindings=[];changed=[]
for name,row in sorted(new.items()):
 p=Path(name);assert fid(p)['sha256']==row['sha256'];q=out/(row['sha256']+'_'+p.name);shutil.copyfile(p,q);bindings.append(dict(current=fid(p),preserved=fid(q)))
 if name not in old or old[name]['sha256']!=row['sha256']:
  before=original[name].read_text() if name in old else '';after=p.read_text();d=diffs/(p.name+'.diff');d.write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=name+' (AT003 archived)' if name in old else '/dev/null',tofile=name)))
  changed.append(dict(path=name,kind='entry-only modified' if name in old else 'entry-only helper added',before=fid(original[name]) if name in old else None,after=fid(p),diff=fid(d)))
q=out/manifest.name;shutil.copyfile(manifest,q)
reg=P/'qualified_regression_v1/receipt.json';x=json.loads(reg.read_text());assert x['exit_code']==0 and x['source_unchanged'];assert 'Ran 201 tests' in (reg.parent/'unittest.log').read_text()
raw=E/'experiment_results/runs/R002/attempts/AT003_fresh_selected_synthesis/evidence/AT003_terminal_and_raw_native_lineage.json';probe=E/'experiment_results/runs/R002/attempts/AT007_native_tcl_and_complete_init_prefix_probe/evidence/native_init_mechanism_binding.json';review=R/'agent/A007/M003_SM015_SM017_review_20261018/AT007_native_init_mechanism_review.json'
value=dict(schema='M003_native_entry_repair_delivery_v1',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Ordinary selector/TCL constraint/current-native INIT/dual-attempt post-report entry repair only; no RTL/architecture/pool/budget/strategy changes',source_manifest=fid(manifest),preserved_manifest=fid(q),previous_source_manifest=fid(P/'entry_manifest_before_native_fix.json'),source_count=len(new),bindings=bindings,changes=changed,regression=fid(reg),regression_log=fid(reg.parent/'unittest.log'),raw_failed_AT003_lineage=fid(raw),native_mechanism_AT007=fid(probe),native_mechanism_independent_review=fid(review),new_schema='M003_fresh_native_synthesis_postreport_recovery_v1',producer='AT003 original native23/22 success while outer native1 retained',consumer='new AT008 planned actual native selected postreport/apply/graph/budget; native0 not yet available',all_three_RTL_unchanged=all(old[name]['sha256']==new[name]['sha256'] for name in new if '/rtl/' in name),unverified=['Formal production selected native role/API/pool/protection qualification','Strict INIT/OPT/debug G4 and actual A007 no-blocker','Place/route/timing/DRC/CDC/reset/IO final signoff'],recovery_contract='Pinned raw AT003 receipt2b43590a; validate only closed entry delta and3 new helpers; all original production inputs/DCP23/22 unchanged; new native0 qualifies current graph separately; original status1 never rewritten; original reports copied with origin identities, no timing/physical PASS inferred',restore_contract='HAP_M003_RESTORE_VERIFY_ONLY before open_checkpoint; increment/trace every apply attempt before rejecting; assert counter unchanged; then stored constraints/pin/pool snapshot before place; no source/reapply')
p=P/'native_entry_fix_delivery_v1.json';assert not p.exists();p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
text='''# M003 SM017：原生入口修复集中交付 v1

AT003保留自然native1终态；本版23个native综合网表与22实际消费DCP逐SHA绑定，379原build输入与188原归档已在终态核一致。新版本只修collector/implementation入口，三RTL、F4池、预算和策略不变。

45项入口源已冻结，manifest `'''+fid(manifest)['sha256']+'''`；受影响联合回归201项全部通过，测试期间源不变。逐文件旧/新身份、原字节副本与diff见同名JSON。

修复：payload精确head/tail、各6560覆盖且所有异常仍拒绝；正式overlay保留原名与implementation-only/global/LATE，显式FILE_TYPE=TCL及绑定脚本根；实际apply成功回执与source SHA独立检查；Vivado当前生成driver原字节保存、完整INIT前缀语法/边界/固定hook资格化后原生执行，严格INIT检查后才显式OPT；约束证据读取真实当前native日志并保留Parsing XDC/Sourcing Tcl原语义；恢复前先启用verify-only并验attempt计数未增加，随后核原DCP约束。

AT007原生机制证明已独立接受，仅小图加载/INIT-only/apply/restore适用。正式本版新图尚待新AT008原生验证，不能把CPU回归或TCL注册当G4。

复用使用明确双尝试schema：`M003_fresh_native_synthesis_postreport_recovery_v1`，AT003原生1与后继native0分开；闭合允许差异、原生产源/IP/参数/时钟不变以及23/22本版新图后，再实际selected对象/预算验证。原始报告按原身份继承，时序不冒充新物理结果。无新综合计算，不使用旧基线DCP。

待A007对本集中source/recovery增量无阻断后直接真实新AT；常规适配无新增用户门。严格G4与独立无阻断后，固定place→physopt→route连续执行。TOP01−2.896ns和22049对账仍OPEN，不保证一次布通。
'''
(P/'native_entry_fix_delivery_v1.md').write_text(text)
print(json.dumps(dict(delivery=fid(p),manifest=fid(manifest),source_count=45,changed=len(changed),three_RTL_unchanged=value['all_three_RTL_unchanged']),ensure_ascii=False))
