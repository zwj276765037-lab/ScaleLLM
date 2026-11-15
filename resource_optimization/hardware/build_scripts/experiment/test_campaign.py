#!/usr/bin/env python3
"""Small CPU fixtures for campaign handoff, selection, and publication gates."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import campaign
import select_candidate


def candidate(name, setup=True, hold=True, wns=0.1, whs=0.1, lut=100):
    return dict(candidate=name, feasible=True, reasons=[], setup_pass=setup, hold_pass=hold,
                timing=dict(wns=wns, tns=0 if setup else -1, setup_fail=0 if setup else 1,
                            whs=whs, ths=0 if hold else -1, hold_fail=0 if hold else 1),
                maximum_slr_clb_percent=80, maximum_slr_dsp_percent=80, top={"lut":{"used":lut}})


def valid_result():
    return dict(returncode=0, stop_reason=None, native_pass_marker=True, elapsed_seconds=100)


class SelectionTests(unittest.TestCase):
    def test_closed_candidates_preserve_dsp(self):
        self.assertEqual(select_candidate.choose(candidate("dsp_raw_only"), candidate("dsp_all"))[0], "dsp_raw_only")

    def test_setup_then_hold_priority(self):
        raw = candidate("dsp_raw_only", setup=False, hold=True, wns=-0.1)
        all_dsp = candidate("dsp_all", setup=True, hold=False, whs=-0.1)
        self.assertEqual(select_candidate.choose(raw, all_dsp)[0], "dsp_all")
        raw = candidate("dsp_raw_only", setup=True, hold=False, whs=-0.1)
        all_dsp = candidate("dsp_all", setup=True, hold=True)
        self.assertEqual(select_candidate.choose(raw, all_dsp)[0], "dsp_all")

    def test_unclosed_lexicographic_timing(self):
        raw = candidate("dsp_raw_only", setup=False, hold=False, wns=-0.02, whs=-0.1, lut=50)
        all_dsp = candidate("dsp_all", setup=False, hold=False, wns=-0.01, whs=-0.2, lut=10)
        self.assertEqual(select_candidate.choose(raw, all_dsp)[0], "dsp_all")

    def test_empty_or_malformed_mapping_is_not_feasible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root/"runs/dsp_raw_only"
            for stage in ("synth", "place"):
                (work/stage/"reports").mkdir(parents=True)
                (work/stage/"result.json").write_text(json.dumps(valid_result()))
            reports = work/"place/reports"
            top = "\n".join("| %s | %s | 0 | 0 | %s | %s |" % row for row in (
                ("CLB LUTs*", 90, 300, 30), ("CLB Registers", 90, 600, 15),
                ("Register as Flip Flop", 90, 600, 15), ("CLB", 90, 300, 30),
                ("Block RAM Tile", 3, 30, 10), ("URAM", 3, 30, 10), ("DSPs", 192, 600, 32)))
            slr = "\n".join(("| CLB | 30 | 30 | 30 | 30.00 | 30.00 | 30.00 |",
                             "| CLB LUTs* | 30 | 30 | 30 | 30.00 | 30.00 | 30.00 |",
                             "| DSPs | 64 | 64 | 64 | 32.00 | 32.00 | 32.00 |"))
            timing = "WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints WPWS(ns) TPWS(ns) TPWS Failing Endpoints TPWS Total Endpoints\n" \
                     "0.1 0 0 100 0.1 0 0 100 0 0 0 100\n"
            hierarchy = "\n".join("| u_recover | core_hap_a8w4_scalecode_recover2_lut_%d | 2 | 2 | 0 | 0 | 4 | 0 | 0 | 0 | 2 |" % i for i in range(96))
            (reports/"utilization.rpt").write_text(top)
            (reports/"utilization_slr.rpt").write_text(slr)
            (reports/"timing_summary.rpt").write_text(timing)
            (reports/"utilization_hierarchical.rpt").write_text(hierarchy)
            (reports/"blackboxes.txt").write_text("")
            (reports/"blackboxes_post_opt.tsv").write_text("name\tref_name\n")
            (reports/"opt_design.dcp").write_text("post-opt checkpoint")
            place_receipt = valid_result()
            place_receipt["reports"] = {"reports/blackboxes_post_opt.tsv": select_candidate.sha(reports/"blackboxes_post_opt.tsv"),
                                        "reports/opt_design.dcp": select_candidate.sha(reports/"opt_design.dcp")}
            (work/"place/result.json").write_text(json.dumps(place_receipt))
            inventory = reports/"dsp_inventory.tsv"
            inventory.write_text("name\tref_name\tloc\tbel\torig_ref_name\n" + "\n".join(
                "leaf%d/raw%d_reg\tDSP48E2\t\t\tDSP48E2" % (i, col)
                for i in range(96) for col in range(2)))
            mapping = reports/"recovery_mapping.tsv"
            mapping.write_text("name\tref\torig\tdsp\n")
            self.assertFalse(select_candidate.read_candidate("dsp_raw_only", root)["feasible"])
            mapping.write_text("name\tref\torig\tdsp\n" + "\n".join("leaf%d\tref\torig\t2" % i for i in range(95)) + "\nwrong\n")
            self.assertFalse(select_candidate.read_candidate("dsp_raw_only", root)["feasible"])
            mapping.write_text("name\tref\torig\tdsp\n" + "\n".join("leaf%d\tref\torig\t0" % i for i in range(96)))
            self.assertTrue(select_candidate.read_candidate("dsp_raw_only", root)["feasible"])
            inventory.write_text(inventory.read_text().replace("leaf0/raw0_reg\tDSP48E2", "other/raw0_reg\tDSP48E2"))
            self.assertFalse(select_candidate.read_candidate("dsp_raw_only", root)["feasible"])

    def test_failed_synth_needs_bound_qualified_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)/"dsp_raw_only"
            (work/"synth/reports").mkdir(parents=True)
            (work/"synth_qualified").mkdir()
            original = dict(returncode=1, stop_reason=None, changed_inputs=[], native_pass_marker=False)
            (work/"synth/result.json").write_text(json.dumps(original))
            self.assertFalse(select_candidate.synth_acceptance(work)[0])
            probe = work/"synth_qualified/result.json"
            probe.write_text("probe")
            dcp = work/"synth/reports/synthesized.dcp"
            dcp.write_text("DCP")
            mapping = work/"synth_acceptance_recovery_mapping.tsv"
            mapping.write_text("mapping")
            accepted = dict(status="PASS", candidate="dsp_raw_only", classification="OPEN_DEBUG_PLACEHOLDER",
                            physical_blackbox_requirement="ZERO_AFTER_OPT_AND_LATER",
                            original_synth_result_sha256=select_candidate.sha(work/"synth/result.json"),
                            fresh_probe_result_sha256=select_candidate.sha(probe),
                            checkpoint_sha256=select_candidate.sha(dcp),
                            corrected_mapping_sha256=select_candidate.sha(mapping))
            (work/"synth_acceptance.json").write_text(json.dumps(accepted))
            self.assertTrue(select_candidate.synth_acceptance(work)[0])
            dcp.write_text("changed")
            self.assertFalse(select_candidate.synth_acceptance(work)[0])


class CampaignTests(unittest.TestCase):
    def test_shared_budget_is_deducted(self):
        self.assertEqual(campaign.remaining_seconds(28800, 100.2), 28698)
        self.assertEqual(campaign.remaining_seconds(7200, 100, 200), 6899)
        with self.assertRaises(RuntimeError):
            campaign.remaining_seconds(28800, 28799.9)

    def test_running_synth_is_adopted_with_exact_input_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root/"dsp_raw_only"
            stage = work/"synth"
            stage.mkdir(parents=True)
            (work/"build.json").write_text("build")
            (work/"candidate_manifest.json").write_text("manifest")
            script = root/"build.tcl"
            script.write_text("set x 1\n")
            progress = dict(status="RUNNING", candidate="dsp_raw_only", stage="synth", pid=1234,
                            started_utc="2026-11-14T01:00:00Z", command=["vivado","-mode","batch","-notrace","-source",str(script)])
            inputs = dict(candidate="dsp_raw_only", stage="synth", build_json_sha256=campaign.sha(work/"build.json"),
                          candidate_manifest_sha256=campaign.sha(work/"candidate_manifest.json"),
                          stage_tcl_sha256=campaign.sha(script))
            (stage/"progress.json").write_text(json.dumps(progress))
            (stage/"stage_inputs.json").write_text(json.dumps(inputs))
            original = Path.read_bytes
            def fake_read(path):
                if str(path) == "/proc/1234/cmdline":
                    return ("/bin/bash vivado -log " + str(stage/"vivado.log")).encode()
                return original(path)
            with (mock.patch.object(campaign, "RUNS", root),
                  mock.patch.object(campaign, "wait_existing", return_value=valid_result()) as wait,
                  mock.patch.object(campaign, "save_status"),
                  mock.patch.object(Path, "read_bytes", autospec=True, side_effect=fake_read)):
                with mock.patch.object(campaign.time, "time", return_value=1794618100):
                    self.assertEqual(campaign.adopt_running_stage("dsp_raw_only", "synth", 10800), valid_result())
                wait.assert_called_once()

    def test_failed_native_route_cannot_publish_bit(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs = Path(temporary)
            name = "dsp_raw_only"
            (runs/name/"place").mkdir(parents=True)
            (runs/name/"place/result.json").write_text(json.dumps(valid_result()))
            reports = runs/name/"route/reports"
            reports.mkdir(parents=True)
            (reports/"routed.dcp").write_text("checkpoint")
            (reports/"timing_gate.txt").write_text("FAIL: DRC Error")
            (reports/"route_status_pre_gate.rpt").write_text("fully routed")
            closed = dict(wns=0.1, tns=0, setup_fail=0, whs=0.1, ths=0, hold_fail=0,
                          wpws=0, tpws=0, pulse_fail=0)
            with (mock.patch.object(campaign, "RUNS", runs),
                  mock.patch.object(campaign, "run_native", return_value={"returncode":1}) as native,
                  mock.patch.object(campaign, "timing_from", return_value=closed)):
                with self.assertRaisesRegex(RuntimeError, "native route/DRC"):
                    campaign.run_physical(name)
                self.assertEqual(native.call_count, 1)
                self.assertFalse((runs/"final_artifact.json").exists())
            with (mock.patch.object(campaign, "RUNS", runs),
                  mock.patch.object(campaign, "run_native", return_value={"returncode":0}) as native,
                  mock.patch.object(campaign, "timing_from", return_value=closed),
                  mock.patch.object(campaign, "valid_native_result", return_value=False)):
                with self.assertRaisesRegex(RuntimeError, "native route/timing/DRC"):
                    campaign.run_physical(name)
                self.assertEqual(native.call_count, 1)
                self.assertFalse((runs/"final_artifact.json").exists())


if __name__ == "__main__":
    unittest.main()
