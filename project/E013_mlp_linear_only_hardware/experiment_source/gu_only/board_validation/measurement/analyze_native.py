#!/usr/bin/env python3
"""Analyze native timing and complete-sweep telemetry without edge extrapolation."""
import argparse
import datetime as dt
import json
from pathlib import Path
import numpy as np

MACS=2*16*4096*14336


def timestamp(value):return dt.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()


def stats(values):
    a=np.asarray(values,dtype=np.float64)
    if not len(a):return {'n':0}
    q=np.quantile(a,[.05,.5,.95],method='linear')
    return {'n':len(a),'mean':float(a.mean()),'min':float(a.min()),'p5':float(q[0]),'median':float(q[1]),'p95':float(q[2]),'max':float(a.max()),'quantile_method':'numpy linear'}


def analyze(path):
    receipt=json.loads((path/'native/receipt.json').read_text())
    telemetry_path=path/'orchestration/telemetry.json'
    commands=[c for c in receipt['commands'] if c['tag']=='measured']
    assert receipt['verdict']=='PASS' and receipt['retained_lease'] is None and receipt['retained_pending'] is None
    assert all(c['acked'] and c['comparison']=='PASS' and c['output_sha256']==c['gold_sha256'] for c in receipt['commands'])
    markers={m['phase']:m for m in receipt['markers']}
    start=markers['load_begin'];end=markers['load_end'];duration=end['monotonic_s']-start['monotonic_s']
    timing={name:stats([c['done'][csr]/1e8 for c in commands]) for name,csr in [('compute_window_s','0x354'),('input_load_phase_s','0x358'),('store_drain_window_s','0x35c'),('union_stall_cycles_as_s','0x360')]}
    timing.update({name:stats([c[name] for c in commands]) for name in ['start_to_first_done_observed_s','host_end_to_end_s','input_h2c_s','output_c2h_s','gold_compare_s','polls']})
    result={'schema':1,'attempt':str(path),'case':receipt['case'],'verdict':'PASS','warmup_commands':receipt['warmup_commands'],'successful_measured_commands':len(commands),'load_window_seconds':duration,'steady_state_commands_per_second':len(commands)/duration,'compute_window_duty':sum(c['done']['0x354'] for c in commands)/1e8/duration,'timing':timing,'dense_equivalent_macs_per_command':MACS,'dense_equivalent_ops_per_command':2*MACS,'compute_window_dense_equivalent_tops':stats([2*MACS/(c['done']['0x354']/1e8)/1e12 for c in commands]),'poll_requested_s':receipt['poll_s'],'power':{'status':'NOT_MEASURED'},'time_alignment':'Native/sampler same Dell UTC; do not subtract Python perf_counter from .NET Stopwatch raw ticks','phase_markers':receipt['markers']}
    if telemetry_path.exists():
        telemetry=json.loads(telemetry_path.read_text(encoding='utf-8-sig'))
        phases={'idle_before':(markers['idle_before_begin'],markers['load_begin']),'load':(markers['load_begin'],markers['load_end']),'idle_after':(markers['idle_after_begin'],markers['idle_after_end'])}
        classified={};samples=[]
        for sample in telemetry['samples']:
            item={'index':sample['index'],'start':timestamp(sample['sweep_started_utc']),'end':timestamp(sample['sweep_ended_utc']),'power_w':float(sample['monitored_power_w']),'sample':sample}
            valid=len(sample['rails'])==7 and all(rail.get('gate_pass') for rail in sample['rails'])
            label='invalid' if not valid else 'transition_or_outside'
            if valid:
                for name,(a,b) in phases.items():
                    if item['start']>=timestamp(a['utc']) and item['end']<=timestamp(b['utc']):label=name;break
            item['phase']=label;item['midpoint']=(item['start']+item['end'])/2;samples.append(item);classified[str(sample['index'])]=label
        power={'status':'MEASURED_SELECTED_SEVEN_RAILS','telemetry_pass':telemetry['pass'],'scope':'7 monitored FPGA regulator output powers; not12V whole-board input','sampler_schema':telemetry['schema_version'],'samples_total':len(samples),'sweep_duration_s':stats([x['end']-x['start'] for x in samples]),'sample_classification':classified,'phases':{},'integration':'trapezoid between valid complete-sweep midpoints only; no edge extrapolation or bridging gaps>3x median interval','reported_pout_quantization_half_step_sum_w':max(s['sample']['monitored_power_quantization_half_step_bound_w'] for s in samples),'other_uncertainty':'MAX15301 V*I is sequential; sensor/calibration/divider errors not included in the POUT quantization bound'}
        for name,(a,b) in phases.items():
            use=[s for s in samples if s['phase']==name];coverage=0;energy=0;segments=[]
            item={'phase_seconds':b['monotonic_s']-a['monotonic_s'],'n_complete_sweeps':len(use),'sweep_indexes':[s['index'] for s in use],'snapshot_power_w':stats([s['power_w'] for s in use])}
            if len(use)>=2:
                gaps=np.diff([s['midpoint'] for s in use]);max_gap=3*float(np.median(gaps))
                for left,right in zip(use,use[1:]):
                    gap=right['midpoint']-left['midpoint']
                    if gap<=0 or gap>max_gap:continue
                    coverage+=gap;energy+=(left['power_w']+right['power_w'])*gap/2;segments.append((left['midpoint'],right['midpoint']))
                item.update(covered_seconds=coverage,covered_energy_j=energy,time_weighted_mean_w=energy/coverage if coverage else None,coverage_start_utc=dt.datetime.fromtimestamp(use[0]['midpoint'],dt.timezone.utc).isoformat(),coverage_end_utc=dt.datetime.fromtimestamp(use[-1]['midpoint'],dt.timezone.utc).isoformat(),sample_midpoint_interval_s=stats(gaps))
                # These rails form the same fixed upstream/output cut in every
                # sample. Preserve individual values rather than estimating VIN.
                item['rails']={rail['address']:{'name':rail['name'],'power_source':rail['power_source'],'power_w':stats([next(x['power_w'] for x in s['sample']['rails'] if x['address']==rail['address']) for s in use])} for rail in use[0]['sample']['rails']}
                if name=='load' and coverage:
                    low=use[0]['midpoint'];high=use[-1]['midpoint']
                    whole=[c for c in commands if timestamp(c['started_utc'])>=low and timestamp(c['ended_utc'])<=high]
                    partial=[c for c in commands if timestamp(c['ended_utc'])>low and timestamp(c['started_utc'])<high and c not in whole]
                    item['matched_coverage_commands']=len(whole);item['boundary_partial_commands']=len(partial)
                    item['matched_compute_window_duty']=sum(c['done']['0x354'] for c in whole)/1e8/coverage
                    item['energy_per_whole_command_j']=energy/len(whole) if whole else None
                    item['energy_per_command_note']='Includes I/O/validation/waiting and possible boundary partial commands; not instantaneous-active energy. Whole commands counted only in the same power coverage.'
            else:item.update(covered_seconds=0,coverage_status='INSUFFICIENT_COMPLETE_SWEEPS')
            power['phases'][name]=item
        phases_summary=power['phases']
        if all(phases_summary[x].get('time_weighted_mean_w') is not None for x in phases):
            before=phases_summary['idle_before']['time_weighted_mean_w'];after=phases_summary['idle_after']['time_weighted_mean_w'];load=phases_summary['load']['time_weighted_mean_w']
            power['idle_before_after_difference_w']=after-before;power['incremental_load_power_w']=load-(before+after)/2
            power['incremental_pout_quantization_worst_case_bound_w']=2*power['reported_pout_quantization_half_step_sum_w']
        result['power']=power
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt',type=Path);args=parser.parse_args();result=analyze(args.attempt)
    (args.attempt/'measurement_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['case','successful_measured_commands','load_window_seconds','steady_state_commands_per_second','compute_window_duty','timing','compute_window_dense_equivalent_tops','power']},indent=2))


if __name__=='__main__':main()
