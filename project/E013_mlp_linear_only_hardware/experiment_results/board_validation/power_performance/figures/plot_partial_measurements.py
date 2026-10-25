from pathlib import Path
import datetime as dt
import hashlib
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

base=Path(__file__).resolve().parents[1]
formal=base/"attempts/AT_20261025T014505.113183Z_native_formal"
power_path=formal/"orchestration_recovered/telemetry.json"
receipt_path=formal/"native_recovered/receipt.json"
pilot_path=base/"attempts/AT_20261025T014420.840244Z_native_pilot/native/receipt.json"
power=json.loads(power_path.read_text(encoding="utf-8-sig"));formal_run=json.loads(receipt_path.read_text(encoding="utf-8-sig"));pilot=json.loads(pilot_path.read_text(encoding="utf-8-sig"))
def stamp(s):return dt.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()
markers={m["phase"]:m for m in formal_run["markers"]}
left=stamp(markers["idle_before_begin"]["utc"]);right=stamp(markers["load_begin"]["utc"])
rows=[]
for sample in power["samples"]:
    a=stamp(sample["sweep_started_utc"]);b=stamp(sample["sweep_ended_utc"])
    value=float(sample["monitored_power_w"])
    assert abs(sum(r["power_w"] for r in sample["rails"])-value)<1e-8
    rows.append(((a+b)/2,value,a>=left and b<=right))
idle=[r for r in rows if r[2]];t=np.array([r[0] for r in idle]);v=np.array([r[1] for r in idle])
mean=float(np.sum(np.diff(t)*(v[:-1]+v[1:])/2)/(t[-1]-t[0]))
assert len(idle)==21 and abs(mean-11.278003)<1e-5
points=[]
for run,group in [(pilot,"Pilot"),(formal_run,"Interrupted run")]:
    for i,c in enumerate(run["commands"]):
        assert c["acked"] and c["comparison"]=="PASS"
        points.append({"group":group,"tag":c["tag"],"command":c["command"],"compute_ms":c["done"]["0x354"]/1e5})
origin=rows[0][0];x=np.array([r[0]-origin for r in rows]);y=np.array([r[1] for r in rows]);known=np.array([r[2] for r in rows])
fig,axes=plt.subplots(1,2,figsize=(12,4.4),gridspec_kw={"width_ratios":[1.45,1]})
ax=axes[0]
ax.fill_between(x,y-3,y+3,color="#d8dce2",alpha=.55,label="Approx. encoding half-step sum (+/-3 W)")
ax.plot(x,y,color="#8c95a3",lw=1.2,label="Telemetry: workload unverified after boundary")
ax.plot(x[known],y[known],color="#1767a5",lw=2,marker="o",ms=3,label="Verified idle sweeps (N=21)")
ax.axvline(right-origin,color="#b13d35",ls="--",lw=1.3,label="Load attempted; no measured command completed")
ax.set(xlabel="Seconds from first telemetry midpoint",ylabel="Sum of 7 monitored rail outputs (W)",title=f"Verified idle average: {mean:.2f} W")
ax.set_ylim(min(y)-3.5,max(y)+3.5);ax.grid(alpha=.2);ax.legend(fontsize=7,loc="upper left")
ax=axes[1]
for i,point in enumerate(points):
    color="#1767a5" if point["group"]=="Pilot" else "#c78224"
    ax.scatter(i+1,point["compute_ms"],color=color,s=45,zorder=3)
    ax.annotate(f'{point["compute_ms"]:.4f}',(i+1,point["compute_ms"]),xytext=(0,8),textcoords="offset points",ha="center",fontsize=8)
ax.set_xticks(range(1,len(points)+1));ax.set_xticklabels([p["tag"]+"\n"+p["group"] for p in points],fontsize=7)
ax.set(ylabel="Hardware compute window (ms, 100 MHz)",title="Successful exploratory samples only")
ax.set_ylim(min(p["compute_ms"] for p in points)-.004,max(p["compute_ms"] for p in points)+.006);ax.grid(axis="y",alpha=.25)
fig.suptitle("Partial measurement: continuous-load run interrupted by Windows bugcheck 0x133",fontsize=12)
fig.text(.5,.015,"Power is not whole-board input power. Formal measured N=0; active power, sustained throughput and energy/job are not established.",ha="center",fontsize=8,color="#555")
fig.tight_layout(rect=(0,.06,1,.93));fig.savefig(Path(__file__).with_name("partial_measurements.png"),dpi=170);plt.close(fig)
summary={"scope":"verified idle power and successful exploratory hardware compute windows; interrupted formal load is excluded","idle_power_w":mean,"idle_valid_sweeps":len(idle),"idle_midpoint_coverage_s":float(t[-1]-t[0]),"formal_measured_commands":0,"load_power_status":"NOT_ESTABLISHED","samples":points,"source_files":[{"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in (power_path,receipt_path,pilot_path)]}
Path(__file__).with_name("partial_measurements.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps({"idle_power_w":mean,"idle_valid_sweeps":len(idle),"compute_samples":len(points),"figure":str(Path(__file__).with_name("partial_measurements.png"))}))
