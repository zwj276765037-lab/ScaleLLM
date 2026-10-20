"""Focused source-selection checks for the format05 board builder."""

from pathlib import Path
import os
import re
import subprocess
import tempfile
import time
import unittest

from vivado.scripts.check_rebuild_static import balanced, expand_manifest, sv_tokens


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "vivado/scripts/build_vcu118_board.tcl"
MANIFEST = Path("vivado/manifests/attention_mlp_board_core_v5_sources.list")
S24 = "hap_mlp_projection_repack12_to16_s24_history2"
S32 = "hap_mlp_projection_repack12_to16_s32_history2"
CURRENT = {
    "hap_axi512_dual_engine_dedicated_read.sv",
    "hap_axi256_dedicated_data_router.sv",
    "hap_mlp_gate_up_v5_scheduler16_q4.sv",
    "hap_mlp_down_v5_scheduler16_s54.sv",
    "hap_mlp_serial_ddr_command16_v5_s54.sv",
    "hap_mlp_full_command16_v5_s54.sv",
    f"{S24}.sv",
    f"{S32}.sv",
}
STALE = {
    f"hap_mlp_{stem}.sv" for stem in (
        "down_group_major_accum_s45",
        "down_v5_scheduler16_s45",
        "shared_dual_slice16x12_s43_s45",
        "serial_ddr_command16_v5_s45",
        "full_command16_v5_s45",
        "down_group_major_accum_s46",
        "down_v5_scheduler16_s46",
        "shared_dual_slice16x12_s44_s46",
        "serial_ddr_command16_v5_s46",
        "full_command16_v5_s46",
    )
}


class Vcu118BuilderSourcesTest(unittest.TestCase):
    def test_m002_bd_validation_mode_stops_before_ip_generation(self):
        create = (ROOT / "vivado/scripts/create_vcu118_board.tcl").read_text()
        mode = create.index("if {$validate_only} {")
        generated = create.index("generate_target all")
        window = create[mode:generated]
        self.assertLess(create.index("validate_bd_design"), mode)
        self.assertIn("exit 0", window)
        self.assertIn("M002_BD_VALIDATION_PASS", window)
        self.assertIn("get_bd_intf_pins core/M_AXI_MLP_DATA", window)
        self.assertNotIn("launch_runs", window)

    def test_m002_constraint_policy_executes_without_timing_or_placement_changes(self):
        xdc = ROOT / "vivado/constraints/ddr_timing_recovery.xdc"
        # Plain Tcl has no timing/placement commands: an active exception or LOC
        # added here fails execution, as does unescaped [M002] in a message.
        result = subprocess.run(["tclsh", str(xdc)], text=True,
                                capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("core100 / DDR UI200", result.stdout)
        create = (ROOT / "vivado/scripts/create_vcu118_board.tcl").read_text()
        self.assertIn("add_files -norecurse -fileset constrs_1 $m002_xdc", create)
        self.assertIn("ddr_timing_recovery.xdc", BUILDER.read_text())

    def test_m002_data_route_audit_rejects_wrong_target_and_missing_cdc_clock(self):
        script = BUILDER.read_text()
        procedures = []
        for name in ("require_m002_link", "require_m002_data_map", "require_m002_bd"):
            match = re.search(r"(?ms)^proc " + name + r" \{[^\n]*\} \{\n.*?^\}", script)
            self.assertIsNotNone(match)
            procedures.append(match.group(0))
        harness = "\n".join(procedures) + r'''
proc require_bd_number {cell key expected} {
    set actual [dict get {NUM_SI 3 NUM_MI 1 NUM_CLKS 2} $key]
    if {$actual != $expected} {error "wrong SmartConnect configuration"}
}
proc get_bd_intf_pins {args} {return [lindex $args end]}
proc get_bd_intf_nets {args} {
    set pin [lindex $args end]
    foreach {a b} {
        core/M_AXI_DATA d0_smc/S00_AXI
        core/M_AXI_MLP_DATA d1_smc/S00_AXI
        core/M_AXI_WEIGHT_C0 d0_smc/S01_AXI
        core/M_AXI_WEIGHT_C1 d1_smc/S02_AXI
        host_split/M00_AXI d0_smc/S02_AXI
        host_split/M01_AXI d1_smc/S01_AXI
    } {if {$pin eq $a || $pin eq $b} {return $a}}
    return {}
}
proc get_bd_addr_spaces {args} {return [lindex $args end]}
proc get_bd_addr_segs {args} {
    if {[lindex $args end] eq "core/M_AXI_MLP_DATA"} {return $::mlp_target}
    return ddr4_0/segment
}
proc get_property {key object} {
    if {$key eq "OFFSET"} {return 0}
    if {$key eq "RANGE"} {return 0x80000000}
    error "unexpected property $key"
}
proc get_bd_pins {args} {return [lindex $args end]}
proc get_bd_nets {args} {
    if {$::bad_clock && [lindex $args end] eq "d1_smc/aclk1"} {return ddr1_clk}
    return core_clk
}
require_m002_bd
puts M002_BD_AUDIT_PASS
'''
        for target, bad_clock, accepted in (("ddr4_1/segment", 0, True),
                                             ("ddr4_0/segment", 0, False),
                                             ("ddr4_1/segment", 1, False)):
            result = subprocess.run(
                ["tclsh", "/dev/stdin"], input=f"set mlp_target {target}\nset bad_clock {bad_clock}\n" + harness,
                text=True, capture_output=True, timeout=10, check=False)
            self.assertEqual(result.returncode == 0, accepted, result.stderr)
        create = (ROOT / "vivado/scripts/create_vcu118_board.tcl").read_text()
        self.assertIn("d1_smc 3 1 2", create)
        self.assertIn("core/M_AXI_MLP_DATA d1_smc/S00_AXI", create)
        self.assertIn("d1_smc/aclk1 $cclk", create)
        self.assertIn("$core_mlp_data $mem1 0x00000000 0x80000000", create)

    def test_m002_elaboration_reads_complete_manifest_and_requires_rtl_mode(self):
        report_root = ROOT / "vivado/reports"
        report_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="m002_tcl_test_", dir=report_root) as temp:
            harness = r'''
proc version {args} {return 2025.2}
proc set_param {args} {}
proc create_project {args} {}
proc current_fileset {} {return sources_1}
proc set_property {args} {}
proc read_verilog {args} {set ::rtl [lindex $args end]}
proc synth_design {args} {
    if {[lsearch -exact $args -rtl] < 0} {error "normal synthesis is forbidden"}
    if {[llength $::rtl] < 60} {error "incomplete production source graph"}
    if {![llength [lsearch -all -glob $::rtl */hap_axi512_dual_engine_dedicated_read.sv]]} {
        error "dedicated DDR adapter missing"
    }
}
proc get_cells {args} {return {}}
proc close_design {} {}
proc close_project {} {puts ELAB_SCRIPT_TEST_PASS}
source [lindex $argv 0]
'''
            path = Path(temp) / "harness.tcl"
            path.write_text(harness)
            result = subprocess.run(["tclsh", str(path), str(ROOT / "vivado/scripts/m002_elaborate_verify.tcl")],
                                    env={**os.environ, "HAP_ELAB_REPORT_DIR": temp, "HAP_JOBS": "8"},
                                    text=True, capture_output=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ELAB_SCRIPT_TEST_PASS", result.stdout)

    def test_legacy_floorplan_is_preserved_but_not_a_default_m002_input(self):
        import hashlib
        xdc = ROOT / "vivado/constraints/mission0005_coordinated_partition.xdc"
        self.assertEqual(hashlib.sha256(xdc.read_bytes()).hexdigest(),
                         "4f3ea708271f99d4892115b078ab7caca1ed2a0f75f68052d74d93d097a73d2b")
        create = (ROOT / "vivado/scripts/create_vcu118_board.tcl").read_text()
        self.assertNotIn("$metadata_xdc", create)
        self.assertNotIn("$partition_xdc", create)
        build = BUILDER.read_text()
        self.assertIn("Legacy native025 physical constraints are not M002 inputs", build)
        self.assertIn("M002 physical checks are not adapted", build)
        self.assertLess(build.index("M002 physical checks are not adapted"),
                        build.index("open_project $project_file"))
        self.assertNotIn("mission0004_require_metadata 0", build)

    def test_rtstat13_is_stage_specific_not_a_drc_waiver(self):
        script = BUILDER.read_text(encoding="utf-8")
        match = re.search(
            r"(?ms)^proc require_no_drc_blockers \{[^\n]*\} \{\n.*?^\}",
            script,
        )
        self.assertIsNotNone(match)
        for stage, violation, severity, accepted in (
            ("pre_implementation", "RTSTAT-13#1", "Critical Warning", True),
            ("pre_place", "RTSTAT-13#1", "Critical Warning", True),
            ("physopt", "RTSTAT-13#1", "Critical Warning", True),
            ("post_route", "RTSTAT-13#1", "Critical Warning", False),
            ("unknown", "RTSTAT-13#1", "Critical Warning", False),
            ("physopt", "RTSTAT-13#1", "Error", False),
            ("physopt", "RTSTAT-1#1", "Critical Warning", False),
            ("physopt", "RTSTAT-130#1", "Critical Warning", False),
            ("physopt", "OTHER-1#1", "Critical Warning", False),
            ("physopt", "OTHER-1#1", "Error", False),
            ("post_route", "OTHER-1#1", "Warning", True),
        ):
            with self.subTest(stage=stage, violation=violation, severity=severity):
                harness = f"""
{match.group(0)}
proc get_drc_violations {{args}} {{return {{{violation}}}}}
proc get_property {{args}} {{return {{{severity}}}}}
require_no_drc_blockers {stage}
puts DRC_GUARD_PASS
"""
                result = subprocess.run(
                    ["tclsh", "/dev/stdin"], input=harness, text=True,
                    capture_output=True, timeout=10, check=False,
                )
                self.assertEqual(result.returncode == 0, accepted, result.stderr)
                if accepted and violation == "RTSTAT-13#1":
                    self.assertIn("PRE_ROUTE_DRC_RETAINED", result.stdout)

    def test_impl_step_requires_fresh_success_evidence(self):
        script = BUILDER.read_text(encoding="utf-8")
        match = re.search(
            r"(?ms)^proc require_completed_impl_step \{[^\n]*\} \{\n.*?^\}",
            script,
        )
        self.assertIsNotNone(match)
        for step, checkpoint, status, mutation, accepted in (
            ("opt_design", "wrapper_opt.dcp", "Not started place_design", "", True),
            ("phys_opt_design", "wrapper_physopt.dcp", "Not started route_design", "", True),
            ("route_design", "wrapper_routed.dcp", "Not started write_bitstream", "", True),
            ("opt_design", "wrapper_opt.dcp", "Not started place_design", "missing_end", False),
            ("opt_design", "wrapper_opt.dcp", "Not started place_design", "failed", False),
            ("opt_design", "wrapper_opt.dcp", "Not started place_design", "empty_dcp", False),
            ("opt_design", "wrapper_opt.dcp", "Not started place_design", "stale_time", False),
            ("opt_design", "wrapper_opt.dcp", "Not started place_design", "stale_run", False),
            ("opt_design", "wrapper_opt.dcp", "Failed", "", False),
        ):
            with self.subTest(step=step, mutation=mutation, status=status):
                with tempfile.TemporaryDirectory(prefix=".impl_guard_test_", dir=ROOT) as temp:
                    directory = Path(temp)
                    end = directory / f".{step}.end.rst"
                    end.touch()
                    (directory / ".vivado.end.rst").touch()
                    design = directory / checkpoint
                    design.write_bytes(b"checkpoint")
                    launched_at = int(time.time()) - 2
                    if mutation == "missing_end":
                        end.unlink()
                    elif mutation == "failed":
                        (directory / f".{step}.error.rst").touch()
                    elif mutation == "empty_dcp":
                        design.write_bytes(b"")
                    elif mutation == "stale_time":
                        launched_at = int(time.time()) + 2
                    stale = "1" if mutation == "stale_run" else "0"
                    harness = f"""
{match.group(0)}
set directory {{{directory}}}
set status {{{status}}}
set stale {{{stale}}}
proc get_runs {{args}} {{return impl_1}}
proc get_property {{args}} {{
    set property [lindex $args end-1]
    if {{$property eq "STATUS"}} {{return $::status}}
    if {{$property eq "NEEDS_REFRESH"}} {{return $::stale}}
    if {{$property eq "DIRECTORY"}} {{return $::directory}}
    error "unexpected property $property"
}}
puts "CHECKPOINT [require_completed_impl_step {step} {checkpoint} {launched_at}]"
"""
                    result = subprocess.run(
                        ["tclsh", "/dev/stdin"], input=harness, text=True,
                        capture_output=True, timeout=10, check=False,
                    )
                    self.assertEqual(result.returncode == 0, accepted,
                                     result.stderr)
                    if accepted:
                        self.assertIn(f"CHECKPOINT {design}\n", result.stdout)

    def test_partial_impl_checkpoints_restore_run_project(self):
        script = BUILDER.read_text(encoding="utf-8")
        physical = script[script.index('if {$stage eq "place"} {\n    reset_run impl_1'):]
        route = physical[physical.index('if {$stage eq "route"} {'):]
        self.assertNotIn("open_run impl_1", physical)
        self.assertNotIn("reset_run impl_1", route)
        self.assertEqual(physical.count("open_checkpoint $opt_checkpoint"), 1)
        self.assertEqual(physical.count("open_checkpoint $physical_checkpoint"), 1)
        self.assertEqual(route.count("open_checkpoint $routed_run_checkpoint"), 1)
        for opened, following in (
            ("open_checkpoint $opt_checkpoint", "launch_runs impl_1 -to_step phys_opt_design"),
            ("open_checkpoint $physical_checkpoint", 'if {$stage eq "route"} {'),
            ("open_checkpoint $routed_run_checkpoint", "verify_inputs $inputs"),
        ):
            window = physical[physical.index(opened):physical.index(following, physical.index(opened))]
            self.assertIn("close_design\n    close_project\n    open_project $project_file\n"
                          "    require_disabled_ip_cache", window)
        self.assertLess(physical.index("require_completed_impl_step opt_design"),
                        physical.index("open_checkpoint $opt_checkpoint"))
        self.assertLess(physical.index("require_completed_impl_step phys_opt_design"),
                        physical.index("open_checkpoint $physical_checkpoint"))
        self.assertLess(route.index("require_completed_impl_step route_design"),
                        route.index("open_checkpoint $routed_run_checkpoint"))
        for guard in ('s3_screen.txt', '[dict get $screen decision] ne "PASS"',
                      '[dict get $marker checkpoint_sha256] ne',
                      '[dict get $screen place_marker_sha256] ne'):
            self.assertIn(guard, route[:route.index("launch_runs impl_1")])
        self.assertNotIn('[dict get $marker physical_started]+86400', route)
        self.assertNotIn('cumulative24-hour budget', route)

    def test_detailed_native_timing_checks_at_existing_stages(self):
        script = BUILDER.read_text(encoding="utf-8")
        stages = {"post_synth": "clocks", "pre_place": "clocks",
                  "physopt": "cdc", "post_route": "clocks"}
        self.assertEqual(script.count("check_timing -verbose -file"), 4)
        for stage, following in stages.items():
            with self.subTest(stage=stage):
                timing = f"timing_{stage}.rpt"
                detail = f"check_timing_{stage}.rpt"
                clocks = f"{following}_{stage}.rpt"
                self.assertEqual(script.count(detail), 1)
                self.assertLess(script.index(timing), script.index(detail))
                self.assertLess(script.index(detail), script.index(clocks))
                self.assertIn(
                    f"check_timing -verbose -file [file join $report_dir {detail}]",
                    script,
                )
        self.assertNotIn("check_timing -quiet", script)
        self.assertNotIn("check_timing -override_defaults", script)

    def test_builder_guards_both_live_gearboxes_and_old_variants(self):
        script = BUILDER.read_text(encoding="utf-8")
        blocks = re.findall(
            r"foreach name \{([^{}]*)\} \{(require_file|reject_file) \$name\}",
            script,
        )
        self.assertEqual([action for _, action in blocks].count("require_file"), 1)
        self.assertEqual([action for _, action in blocks].count("reject_file"), 1)
        selected = {action: set(names.split()) for names, action in blocks}
        self.assertTrue(CURRENT <= selected["require_file"])
        self.assertTrue(STALE <= selected["reject_file"])
        self.assertFalse(CURRENT & selected["reject_file"])
        self.assertFalse(STALE & selected["require_file"])
        self.assertLess(script.index("} {reject_file $name}"),
                        script.index("create_ip_run $bd_files"))

    def test_board_manifest_follows_both_scheduler_dependencies(self):
        _, leaves = expand_manifest(ROOT, MANIFEST)
        names = {path.name for path in leaves}
        self.assertTrue(CURRENT <= names)
        self.assertFalse(STALE & names)

        create = (ROOT / "vivado/scripts/create_vcu118_board.tcl").read_text(
            encoding="utf-8")
        build = BUILDER.read_text(encoding="utf-8")
        define = "HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54"
        self.assertIn(define, create)
        self.assertIn(define, build)

        self.assert_instantiates("rtl/integration/hap_attention_mlp_resource_top.sv",
                                 "hap_mlp_full_command16_s54", "u_mlp")
        full = "rtl/mlp/hap_mlp_full_command16_v5_s54.sv"
        tokens = sv_tokens(ROOT / full)
        self.assertTrue(any(tokens[i:i + 3] == [
            "module", "`", "HAP_MLP_FULL_COMMAND_V5_MODULE"
        ] for i in range(len(tokens) - 2)))
        self.assert_instantiates(full, "hap_mlp_serial_ddr_command16_v5_s54",
                                 "u_serial_command")
        serial = "rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv"
        self.assert_instantiates(serial, "hap_mlp_gate_up_v5_scheduler16_q4",
                                 "u_gate_scheduler")
        self.assert_instantiates(serial, "hap_mlp_down_v5_scheduler16_s54",
                                 "u_down_scheduler")
        self.assert_instantiates("rtl/mlp/hap_mlp_gate_up_v5_scheduler16_q4.sv",
                                 S24, "u_projection_repack")
        self.assert_instantiates("rtl/mlp/hap_mlp_down_v5_scheduler16_s54.sv",
                                 S32, "u_projection_repack")

    def assert_instantiates(self, source, module, instance):
        tokens = sv_tokens(ROOT / source)
        for index, token in enumerate(tokens):
            if token != module:
                continue
            cursor = index + 1
            if tokens[cursor] == "#":
                _, cursor = balanced(tokens, cursor + 1)
            if tokens[cursor:cursor + 2] == [instance, "("]:
                return
        self.fail(f"{source} does not instantiate {module} as {instance}")


if __name__ == "__main__":
    unittest.main()
