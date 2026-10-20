from pathlib import Path
import os,subprocess,sys
report=Path(os.environ['HAP_REPORT_DIR']);report.mkdir()
cmd=['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado','-mode','batch','-notrace','-source',sys.argv[1],'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou'),'-tclargs',sys.argv[2],sys.argv[3],sys.argv[5]]
sys.exit(subprocess.run(cmd,cwd=report,env={**os.environ,'HAP_PROBE_HELPER':sys.argv[4]}).returncode)
