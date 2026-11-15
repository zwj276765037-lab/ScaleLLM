#!/usr/bin/env python3
"""Continue qualified board candidates through placement and guarded bit output."""
import fcntl
import json
from pathlib import Path
import threading
import time
import traceback

import campaign
from select_candidate import select, synth_acceptance

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
NAMES = ("dsp_raw_only", "dsp_all")


def main():
    with (RUNS / ".campaign.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        old = RUNS / "campaign_state.json"
        previous = json.loads(old.read_text())
        if previous.get("status") != "FAIL":
            raise RuntimeError("Original campaign has not stopped with preserved failure evidence")
        campaign.STATE = RUNS / "campaign_resume_state.json"
        campaign.STATUS = dict(schema="scalellm_dsp_board_campaign_resume_v1",
            pid=__import__("os").getpid(), status="RUNNING", events=[],
            started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            previous_campaign_state=str(old), previous_campaign_state_sha256=campaign.sha(old),
            resume_script_sha256=campaign.sha(Path(__file__)),
            runner_sha256=campaign.sha(campaign.RUNNER),
            selector_sha256=campaign.sha(ROOT / "scripts/select_candidate.py"),
            build_tcl_sha256=campaign.sha(ROOT / "scripts/build_board.tcl"),
            post_opt_hook_sha256=campaign.sha(ROOT / "scripts/post_opt_guard.tcl"))
        campaign.save_status(dict(status="RESUME_STARTED"))
        results = {}
        threads = {}

        def placed(name):
            try:
                good, detail = synth_acceptance(RUNS / name)
                if not good:
                    raise RuntimeError("Fresh synthesis acceptance failed: " + detail)
                campaign.save_status(dict(candidate=name, stage="synth_acceptance", status="PASS",
                                          receipt=str(RUNS / name / "synth_acceptance.json"), detail=detail))
                campaign.run_native(name, "place", threads=32, timeout=28800, rss=192)
                results[name] = "PASS"
            except BaseException as exc:
                results[name] = "FAIL: " + str(exc)
                campaign.save_status(dict(candidate=name, status="CANDIDATE_FAILED", error=str(exc)))

        for name in NAMES:
            threads[name] = threading.Thread(target=placed, args=(name,), name=name)
            threads[name].start()
        for thread in threads.values():
            thread.join()

        selection = select()
        campaign.save_status(dict(stage="selection", status="PASS", candidate=selection["candidate"],
                                  reason=selection["reason"], result=str(RUNS / "selection.json")))
        output = campaign.run_physical(selection["candidate"])
        campaign.STATUS.update(status="PASS", finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                               final_artifact=str(RUNS / "final_artifact.json"))
        campaign.save_status(dict(stage="bitstream", status="PASS", bitstream=output["bitstream"],
                                  bitstream_sha256=output["bitstream_sha256"]))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        campaign.STATUS.update(status="FAIL", error=str(exc), traceback=traceback.format_exc(),
                               finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        campaign.save_status(dict(status="RESUME_FAILED", error=str(exc)))
        raise
