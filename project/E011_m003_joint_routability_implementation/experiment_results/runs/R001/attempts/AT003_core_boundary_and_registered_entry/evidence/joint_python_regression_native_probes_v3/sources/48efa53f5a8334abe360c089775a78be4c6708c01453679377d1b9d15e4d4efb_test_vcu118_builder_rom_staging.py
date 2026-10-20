"""CPU/Tcl regression for the board builder's relative ROM paths."""

import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "vivado/scripts/build_vcu118_board.tcl"
ROMS = {
    "softmax_exp_u17.mem": "3af91ffa7ead647b42b8440c9a098d84b0abb81ffdc09c96550c724bf7248967",
    "mlp_silu_q16.mem": "8263e8981b637b00143c6dfd6674f2397a73c85c6ed8934f0ee839f76db6ea67",
}
RUNS = ("synth_1", "scalellm_vcu118_f05_bd_core_0_synth_1",
        "another_generated_ip_synth_1")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tcl_word(value):
    value = str(value)
    if "}" in value:
        raise ValueError("test path cannot be braced for Tcl")
    return "{" + value + "}"


class Vcu118BuilderRomStagingTest(unittest.TestCase):
    def builder_procs(self, *required):
        script = BUILDER.read_text(encoding="utf-8")
        found = {match.group(1): match.group(0) for match in re.finditer(
            r"(?ms)^proc (\w+) \{[^\n]*\} \{\n.*?^\}", script)}
        for name in required:
            if name not in found:
                self.fail(f"builder needs Tcl proc {name}")
        return "\n".join(found.values())

    def run_tcl(self, procs, tree, source_root, action, *, reset=False,
                saved_inputs=None):
        pins = " ".join(f"{tcl_word(source_root / 'data' / name)} {tcl_word(sha)}"
                        for name, sha in ROMS.items())
        saved = ("$source_pins" if saved_inputs is None else
                 "[dict create " + " ".join(
                     f"{tcl_word(path)} {tcl_word(sha)}"
                     for path, sha in saved_inputs.items()) + "]")
        setup = "\n".join((
            f"set root {tcl_word(source_root)}",
            f"set source_pins [dict create {pins}]",
            f"set inputs {saved}",
            f"set test_base {tcl_word(tree)}",
            "set manifest [file join $test_base inputs.sha256]",
            "set runs {" + " ".join(RUNS) + "}",
            """
proc get_runs {args} {
    set last [lindex $args end]
    if {[lsearch -exact $args -filter] >= 0} {
        if {[string first "NAME ==" $last] >= 0} {
            return [list [lindex $::runs 1]]
        }
        return [lrange $::runs 1 end]
    }
    if {[lsearch -exact $::runs $last] >= 0} {return [list $last]}
    return $::runs
}
proc get_property {property run} {
    if {$property eq "DIRECTORY"} {return $::run_dir($run)}
    if {$property eq "NAME"} {return $run}
    error "unexpected property $property"
}
proc reset_run {run} {
    set ::run_dir($run) [file join $::test_base current $run]
    file mkdir $::run_dir($run)
}
""",
            "foreach run $runs {set run_dir($run) [file join $test_base old $run]}",
            "foreach run $runs {reset_run $run}" if reset else
            "foreach run $runs {set run_dir($run) [file join $test_base current $run]}",
        ))
        result = subprocess.run(
            ["tclsh", "/dev/stdin"], input=f"{procs}\n{setup}\n{action}\n",
            text=True, capture_output=True, cwd=tree.parent, timeout=10,
            check=False)
        return result

    def source_fixture(self, tree):
        source_root = tree / "source"
        (source_root / "data").mkdir(parents=True)
        for name, sha in ROMS.items():
            original = ROOT / "data" / name
            self.assertEqual(digest(original), sha)
            (source_root / "data" / name).write_bytes(original.read_bytes())
        return source_root

    def manifest_rows(self, path):
        rows = {}
        for row in path.read_text(encoding="utf-8").splitlines():
            sha, name = row.split("  ", 1)
            self.assertNotIn(name, rows)
            rows[name] = sha
        return rows

    def test_frozen_source_hashes(self):
        for name, sha in ROMS.items():
            self.assertEqual(digest(ROOT / "data" / name), sha)

    def test_live_post_reset_run_cwds_and_rom_integrity(self):
        procs = self.builder_procs("stage_synth_roms", "verify_synth_roms")
        with tempfile.TemporaryDirectory(prefix=".rom_staging_test_", dir=ROOT) as temp:
            tree = Path(temp)
            source_root = self.source_fixture(tree)
            runs = tree / "runs"
            result = self.run_tcl(procs, runs, source_root,
                                  "set staged_paths [stage_synth_roms $root $source_pins]\n"
                                  "set inputs [write_input_manifest "
                                  "[concat [dict keys $source_pins] $staged_paths] $manifest]\n"
                                  "verify_synth_roms $root $inputs\n"
                                  "foreach path $staged_paths {puts \"STAGED_PATH $path\"}",
                                  reset=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = {str(runs / "current" / run / "data" / name)
                        for run in RUNS for name in ROMS}
            returned = [row.removeprefix("STAGED_PATH ") for row in result.stdout.splitlines()
                        if row.startswith("STAGED_PATH ")]
            self.assertEqual(set(returned), expected)
            self.assertEqual(len(returned), 6)
            saved = self.manifest_rows(runs / "inputs.sha256")
            self.assertEqual(set(saved), expected | {
                str(source_root / "data" / name) for name in ROMS})
            for name, sha in ROMS.items():
                self.assertEqual(saved[str(source_root / "data" / name)], sha)
            for run in RUNS:
                for name, sha in ROMS.items():
                    staged = runs / "current" / run / "data" / name
                    self.assertEqual(staged.read_bytes(), (ROOT / "data" / name).read_bytes())
                    self.assertEqual(digest(staged), sha)
                    self.assertEqual(saved[str(staged)], sha)
                self.assertFalse((runs / "old" / run / "data").exists())

            staged = runs / "current" / RUNS[1] / "data" / "softmax_exp_u17.mem"
            staged.write_bytes(b"tampered\n")
            result = self.run_tcl(procs, runs, source_root,
                                  "verify_synth_roms $root $inputs", saved_inputs=saved)
            self.assertNotEqual(result.returncode, 0, "tampered staged ROM accepted")
            staged.write_bytes((ROOT / "data" / staged.name).read_bytes())
            staged.unlink()
            result = self.run_tcl(procs, runs, source_root,
                                  "verify_synth_roms $root $inputs", saved_inputs=saved)
            self.assertNotEqual(result.returncode, 0, "missing staged ROM accepted")

            staged.write_bytes((ROOT / "data" / staged.name).read_bytes())
            source = source_root / "data" / "mlp_silu_q16.mem"
            source.write_bytes(b"tampered\n")
            result = self.run_tcl(procs, runs, source_root,
                                  "verify_synth_roms $root $inputs", saved_inputs=saved)
            self.assertNotEqual(result.returncode, 0, "post-synth source ROM change accepted")
            result = self.run_tcl(procs, tree / "tampered_runs", source_root,
                                  "stage_synth_roms $root $source_pins", reset=True)
            self.assertNotEqual(result.returncode, 0, "tampered source ROM accepted")
            source.unlink()
            result = self.run_tcl(procs, tree / "missing_runs", source_root,
                                  "stage_synth_roms $root $source_pins", reset=True)
            self.assertNotEqual(result.returncode, 0, "missing source ROM accepted")

    def test_synth_84445_warning_is_fatal(self):
        procs = self.builder_procs("reject_synth_rom_warnings")
        with tempfile.TemporaryDirectory(prefix=".rom_staging_test_", dir=ROOT) as temp:
            tree = Path(temp)
            source_root = self.source_fixture(tree)
            runs = tree / "runs"
            for run in RUNS:
                directory = runs / "current" / run
                directory.mkdir(parents=True)
                (directory / "runme.log").write_text("synthesis complete\n", encoding="utf-8")
            result = self.run_tcl(procs, runs, source_root,
                                  "reject_synth_rom_warnings")
            self.assertEqual(result.returncode, 0, result.stderr)
            for run in RUNS:
                with self.subTest(run=run):
                    log = runs / "current" / run / "runme.log"
                    log.write_text("CRITICAL WARNING: [Synth 8-4445] could not open "
                                   "$readmem data file 'data/softmax_exp_u17.mem'\n",
                                   encoding="utf-8")
                    result = self.run_tcl(procs, runs, source_root,
                                          "reject_synth_rom_warnings")
                    self.assertNotEqual(result.returncode, 0,
                                        f"Synth 8-4445 warning accepted in {run}")
                    log.unlink()
                    result = self.run_tcl(procs, runs, source_root,
                                          "reject_synth_rom_warnings")
                    self.assertNotEqual(result.returncode, 0,
                                        f"missing runme.log accepted in {run}")
                    log.write_text("synthesis complete\n", encoding="utf-8")

    def test_route_rebuilds_identical_manifest_from_existing_copies(self):
        procs = self.builder_procs("stage_synth_roms", "verify_synth_roms",
                                   "reject_synth_rom_warnings")
        with tempfile.TemporaryDirectory(prefix=".rom_staging_test_", dir=ROOT) as temp:
            tree = Path(temp)
            source_root = self.source_fixture(tree)
            runs = tree / "runs"
            synth = self.run_tcl(
                procs, runs, source_root,
                "set staged_paths [stage_synth_roms $root $source_pins]\n"
                "set inputs [write_input_manifest [lsort -unique [concat "
                "[dict keys $source_pins] $staged_paths]] $manifest]\n"
                "verify_synth_roms $root $inputs", reset=True)
            self.assertEqual(synth.returncode, 0, synth.stderr)
            synth_bytes = (runs / "inputs.sha256").read_bytes()
            for run in RUNS:
                (runs / "current" / run / "runme.log").write_text(
                    "synthesis complete\n", encoding="utf-8")
            staged = [runs / "current" / run / "data" / name
                      for run in RUNS for name in ROMS]
            before = {path: (digest(path), path.stat().st_mtime_ns) for path in staged}
            route = self.run_tcl(
                procs, runs, source_root,
                "set staged_paths [synth_rom_paths]\n"
                "set route_manifest [file join $test_base route_inputs.sha256]\n"
                "set inputs [write_input_manifest [lsort -unique [concat "
                "[dict keys [synth_rom_sources $root]] $staged_paths]] "
                "$route_manifest]\n"
                "verify_synth_roms $root $inputs\n"
                "reject_synth_rom_warnings")
            self.assertEqual(route.returncode, 0, route.stderr)
            self.assertEqual((runs / "route_inputs.sha256").read_bytes(), synth_bytes)
            self.assertEqual({path: (digest(path), path.stat().st_mtime_ns)
                              for path in staged}, before)
            self.assertEqual(len(self.manifest_rows(runs / "route_inputs.sha256")), 8)

    def test_child_run_tcl_requires_disabled_ip_cache(self):
        procs = self.builder_procs("require_child_ip_cache_policy")
        with tempfile.TemporaryDirectory(prefix=".rom_staging_test_", dir=ROOT) as temp:
            tree = Path(temp)
            source_root = self.source_fixture(tree)
            runs = tree / "runs"
            for run in RUNS:
                directory = runs / "current" / run
                directory.mkdir(parents=True)
                (directory / f"{run}.tcl").write_text(
                    "set_property ip_cache_permissions {disable} [current_project]\n",
                    encoding="utf-8")
            result = self.run_tcl(procs, runs, source_root,
                                  "require_child_ip_cache_policy 1")
            self.assertEqual(result.returncode, 0, result.stderr)
            child = runs / "current" / RUNS[1] / f"{RUNS[1]}.tcl"
            disable_line = (
                "set_property ip_cache_permissions {disable} [current_project]\n")
            child.write_text(disable_line +
                             "set_property ip_cache_permissions {read write} "
                             "[current_project]\n", encoding="utf-8")
            result = self.run_tcl(procs, runs, source_root,
                                  "require_child_ip_cache_policy 1")
            self.assertNotEqual(result.returncode, 0,
                                "conflicting disable/read-write assignments accepted")
            child.write_text(disable_line + disable_line, encoding="utf-8")
            result = self.run_tcl(procs, runs, source_root,
                                  "require_child_ip_cache_policy 1")
            self.assertNotEqual(result.returncode, 0,
                                "duplicate disable assignments accepted")
            child.write_text(
                "set_property ip_cache_permissions {disable} [get_filesets sources_1]\n",
                encoding="utf-8")
            result = self.run_tcl(procs, runs, source_root,
                                  "require_child_ip_cache_policy 1")
            self.assertNotEqual(result.returncode, 0, "wrong cache property object accepted")
            child.write_text(disable_line, encoding="utf-8")
            second = child.with_name("another_generated_script.tcl")
            second.write_text(disable_line, encoding="utf-8")
            result = self.run_tcl(procs, runs, source_root,
                                  "require_child_ip_cache_policy 1")
            self.assertNotEqual(result.returncode, 0, "ambiguous child Tcl accepted")
            second.unlink()
            child.write_text(
                "set_property ip_cache_permissions {disabled} [current_project]\n",
                encoding="utf-8")
            result = self.run_tcl(procs, runs, source_root,
                                  "require_child_ip_cache_policy 1")
            self.assertNotEqual(result.returncode, 0, "noncanonical cache value accepted")
            child.write_text(
                "set_property ip_cache_permissions {read write} [current_project]\n",
                encoding="utf-8")
            result = self.run_tcl(procs, runs, source_root,
                                  "require_child_ip_cache_policy 1")
            self.assertNotEqual(result.returncode, 0, "cached child Tcl accepted")
            child.unlink()
            result = self.run_tcl(procs, runs, source_root,
                                  "require_child_ip_cache_policy 1")
            self.assertNotEqual(result.returncode, 0, "missing child Tcl accepted")

    def test_disabled_cache_identity_order_and_synth_jobs(self):
        script = BUILDER.read_text(encoding="utf-8")
        open_project = script.index("open_project $project_file")
        disable = script.index("config_ip_cache -disable_cache", open_project)
        guard = script.index("require_disabled_ip_cache", disable)
        create = script.index("create_ip_run $bd_files", guard)
        reset = script.index("reset_run synth_1", create)
        launch = script.index("launch_runs synth_1 -jobs $synth_jobs", reset)
        self.assertLess(open_project, disable)
        self.assertLess(disable, guard)
        self.assertLess(guard, create)
        self.assertLess(create, reset)
        self.assertLess(reset, launch)
        self.assertNotIn("require_child_ip_cache_policy 0", script)
        self.assertGreater(script.index("require_child_ip_cache_policy 1", launch), launch)
        identity_code = script[script.index("proc write_identity"):open_project]
        self.assertIn("set cache_policy [require_disabled_ip_cache]", identity_code)
        self.assertIn("ip_cache_permissions=$cache_policy", identity_code)
        self.assertNotIn("config_ip_cache -clear", script)
        self.assertIn("launch_runs impl_1 -to_step opt_design -jobs 1", script)
        self.assertIn("launch_runs impl_1 -to_step route_design -jobs 1", script)

        expression = re.search(r"(?m)^set synth_jobs \[expr \{[^\n]+\}\]$", script)
        self.assertIsNotNone(expression)
        for jobs, expected in ((1, 1), (2, 2), (32, 2)):
            with self.subTest(jobs=jobs):
                result = subprocess.run(
                    ["tclsh", "/dev/stdin"],
                    input=f"set jobs {jobs}\n{expression.group(0)}\nputs $synth_jobs\n",
                    text=True, capture_output=True, timeout=10, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), str(expected))

        procs = self.builder_procs("require_disabled_ip_cache", "write_identity")
        with tempfile.TemporaryDirectory(prefix=".rom_staging_test_", dir=ROOT) as temp:
            identity = Path(temp) / "identity.txt"
            route_identity = Path(temp) / "route_identity.txt"
            stubs = """
proc version {args} {return 2025.2}
proc current_project {} {return fixture}
proc get_filesets {name} {return $name}
proc get_files {args} {return {}}
proc get_runs {args} {return synth_1}
proc get_property {args} {
    set property [lindex $args end-1]
    if {$property eq "IP_CACHE_PERMISSIONS"} {return $::policy}
    return fixture
}
"""
            result = subprocess.run(
                ["tclsh", "/dev/stdin"],
                input=f"{procs}\n{stubs}\nset policy disable\n"
                      f"write_identity {tcl_word(identity)}\n"
                      f"write_identity {tcl_word(route_identity)}\n",
                text=True, capture_output=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ip_cache_permissions=disable\n",
                          identity.read_text(encoding="utf-8"))
            self.assertEqual(route_identity.read_bytes(), identity.read_bytes())
            result = subprocess.run(
                ["tclsh", "/dev/stdin"],
                input=f"{procs}\n{stubs}\nset policy disabled\n"
                      "require_disabled_ip_cache\n",
                text=True, capture_output=True, timeout=10, check=False)
            self.assertNotEqual(result.returncode, 0, "noncanonical cache value accepted")
            result = subprocess.run(
                ["tclsh", "/dev/stdin"],
                input=f"{procs}\n{stubs}\nset policy {{read write}}\n"
                      "require_disabled_ip_cache\n",
                text=True, capture_output=True, timeout=10, check=False)
            self.assertNotEqual(result.returncode, 0, "enabled IP cache accepted")

    def test_identity_excludes_only_unused_generated_ip_simulation_outputs(self):
        procs = self.builder_procs("require_disabled_ip_cache", "write_identity")
        with tempfile.TemporaryDirectory(prefix=".identity_test_", dir=ROOT) as temp:
            tree = Path(temp)
            generated = tree / "fixture.gen/sources_1/bd/fixture/ip/fixture_ip"
            generated.mkdir(parents=True)
            promises = [generated / f"ip{index}_sim_netlist.{extension}"
                        for index in range(7) for extension in ("v", "vhdl")]
            generated_output = generated / "existing_sim_netlist.v"
            generated_output.write_text("module output_fixture; endmodule\n",
                                        encoding="ascii")
            promises.append(generated_output)
            existing = tree / "existing_sim_netlist.v"
            existing.write_text("module fixture; endmodule\n", encoding="ascii")
            retained = [existing, generated / "active_sim_netlist.v",
                        generated / "implementation_sim_netlist.vhdl",
                        generated / "unknown_sim_netlist.v", tree / "other.v"]
            constraint = tree / "constraint_sim_netlist.v"
            before = tree / "before.txt"
            after = tree / "after.txt"
            changed = tree / "changed.txt"
            rows = " ".join(tcl_word(path) for path in promises + retained)
            promise_rows = " ".join(tcl_word(path) for path in promises)
            stubs = """
proc version {args} {return 2025.2}
proc current_project {} {return fixture}
proc get_filesets {name} {return $name}
proc get_files {args} {
    if {[lindex $args end] eq "constrs_1"} {return [list $::constraint]}
    return $::files
}
proc get_runs {args} {return synth_1}
proc get_property {args} {
    set property [lindex $args end-1]
    set object [lindex $args end]
    if {$property eq "IP_CACHE_PERMISSIONS"} {return disable}
    if {$property in {USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION}} {
        if {[info exists ::properties($object,$property)]} {
            return $::properties($object,$property)
        }
        return 0
    }
    return fixture
}
"""
            action = f"""
set files [list {rows}]
set promises [list {promise_rows}]
set constraint {tcl_word(constraint)}
set properties({retained[1]},USED_IN_SYNTHESIS) 1
set properties({retained[2]},USED_IN_IMPLEMENTATION) 1
set properties({retained[3]},USED_IN_SYNTHESIS) {{}}
set properties({promises[0]},USED_IN_IMPLEMENTATION) {{}}
write_identity {tcl_word(before)}
foreach promise $promises {{
    set files [lreplace $files [lsearch -exact $files $promise] \
        [lsearch -exact $files $promise]]
}}
write_identity {tcl_word(after)}
set properties({retained[1]},USED_IN_SYNTHESIS) 0
write_identity {tcl_word(changed)}
"""
            result = subprocess.run(
                ["tclsh", "/dev/stdin"], input=f"{procs}\n{stubs}\n{action}",
                text=True, capture_output=True, cwd=ROOT, timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before.read_bytes(), after.read_bytes())
            registration_rows = [row for row in before.read_text().splitlines()
                                 if row.startswith("file.")]
            self.assertEqual(len(registration_rows), len(retained) + 1)
            for path in retained + [constraint]:
                self.assertTrue(any(f":{path}:" in row for row in registration_rows),
                                f"required descriptor omitted: {path}")
            for path in promises:
                self.assertFalse(any(f":{path}:" in row for row in registration_rows))
            self.assertNotEqual(after.read_bytes(), changed.read_bytes(),
                                "active descriptor changes must alter identity")

    def test_reset_freshness_and_guards_precede_success_marker(self):
        script = BUILDER.read_text(encoding="utf-8")
        start = script.index("set core_runs [get_runs")
        reset_top = script.index("reset_run synth_1", start)
        stage = re.search(
            r"(?m)^[ \t]*set[ \t]+(\w+)[ \t]+\[stage_synth_roms[ \t]+"
            r"\$root[ \t]+\$\w+\][ \t]*$", script)
        self.assertIsNotNone(stage, "capture all staged paths from current run directories")
        launch = script.index("launch_runs synth_1 -jobs $synth_jobs", stage.end())
        self.assertLess(reset_top, stage.start())
        reset_loops = re.finditer(
            r"foreach\s+(\w+)\s+\[get_runs\s+-quiet\s+-filter\s+"
            r"\{NAME\s*=~\s+\*_synth_1\}\]\s+\{([^}]*)\}",
            script[start:stage.start()])
        self.assertTrue(any(re.search(r"\breset_run\s+\$" + match.group(1) + r"\b",
                                      match.group(2)) for match in reset_loops),
                        "reset every registered *_synth_1 before staging")
        self.assertLess(stage.start(), launch)
        manifest_path = script.index("[file join $report_dir inputs.sha256]]", stage.end())
        manifest_write = script.rfind("write_input_manifest", stage.end(), manifest_path)
        self.assertGreater(manifest_write, stage.end(),
                           "final inputs.sha256 must be written after staging")
        self.assertLess(manifest_path, launch)
        self.assertIn("$" + stage.group(1), script[manifest_write:manifest_path],
                      "final manifest must include returned staged paths")
        self.assertEqual(len(re.findall(
            r"(?m)^[ \t]*(?:set[ \t]+\w+[ \t]+\[)?stage_synth_roms\b", script)), 1,
            "route must verify existing staged copies, not restage")
        wait = script.index("wait_on_run synth_1", launch)
        marker = script.index("[file join $report_dir fresh_synth_complete.txt] w", wait)
        route_branch = script.index("} else {", wait)
        common_checks = script.index("require_complete_run synth_1", route_branch)
        self.assertNotIn("reset_run synth_1", script[route_branch:common_checks])
        self.assertNotIn("stage_synth_roms", script[route_branch:common_checks])
        route_verify = script.find("verify_synth_roms", route_branch, common_checks)
        shared_verify = script.find("verify_synth_roms", common_checks, marker)
        self.assertTrue(route_verify >= 0 or shared_verify >= 0,
                        "route must verify existing staged copies")
        for command in ("require_complete_run synth_1",
                        "require_complete_run [get_property NAME [lindex $core_runs 0]]",
                        "verify_synth_roms $root $inputs",
                        "reject_synth_rom_warnings", "verify_inputs $inputs"):
            call = script.index(command, wait)
            self.assertLess(call, marker, command)
        self.assertIn("foreach run [get_runs -quiet -filter {NAME =~ *_synth_1}]",
                      script[wait:marker])

    def test_xci_preparation_precedes_full_input_binding(self):
        script = BUILDER.read_text(encoding="utf-8")
        prepare = script.index("launch_runs synth_1 -jobs $synth_jobs -scripts_only")
        reset = script.index("reset_run synth_1", prepare)
        stage = script.index("set staged_paths [stage_synth_roms", reset)
        bind = script.index("set inputs [write_input_manifest", stage)
        launch = script.index("launch_runs synth_1 -jobs $synth_jobs\n", bind)
        self.assertLess(prepare, reset)
        self.assertLess(reset, stage)
        self.assertLess(stage, bind)
        self.assertLess(bind, launch)
        self.assertIn("require_child_ip_cache_policy 1", script[prepare:reset])
        self.assertIn("close_project\n    open_project $project_file\n"
                      "    require_disabled_ip_cache", script[reset:stage])
        self.assertIn("unset core_runs bd_files\n    close_project", script[reset:stage])
        reopen = script.index("open_project $project_file", reset)
        self.assertIn("set core_runs [get_runs -quiet -filter", script[reopen:stage])
        self.assertIn("Reopened production core OOC synthesis run is missing",
                      script[reopen:stage])
        self.assertIn("verify_inputs $inputs", script[bind:launch])
        self.assertEqual(script.count("-scripts_only"), 1)
        source_proc = script[script.index("proc source_files"):script.index(
            "proc write_input_manifest")]
        self.assertIn("-name *.xci", source_proc)

    def test_full_byte_xci_guard_rejects_semantically_inert_change(self):
        procs = self.builder_procs("hash_file", "write_input_manifest", "verify_inputs")
        with tempfile.TemporaryDirectory(prefix=".xci_freeze_test_", dir=ROOT) as temp:
            tree = Path(temp)
            xci = tree / "core.xci"
            xci.write_text('{"schema":"fixture","checksum":"fixed"}\n',
                           encoding="ascii")
            manifest = tree / "inputs.sha256"
            action = f"""
set copy {tcl_word(xci)}
set inputs [write_input_manifest [list $copy] {tcl_word(manifest)}]
verify_inputs $inputs
set handle [open $copy a]
puts $handle ""
close $handle
if {{![catch {{verify_inputs $inputs}} failure] ||
    $failure ne "Input changed during build: $copy"}} {{
    error "semantically inert full-byte mutation was accepted"
}}
puts FULL_XCI_HASH_REJECTION_PASS
"""
            result = subprocess.run(["tclsh", "/dev/stdin"], input=procs + action,
                                    text=True, capture_output=True, cwd=tree,
                                    timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("FULL_XCI_HASH_REJECTION_PASS", result.stdout)

    def test_bound_path_string_roundtrip_preserves_exact_manifest(self):
        procs = self.builder_procs("hash_file", "write_input_manifest", "verify_inputs")
        binding = procs[procs.index("proc write_input_manifest"):procs.index(
            "proc verify_inputs")]
        self.assertLess(binding.index("encoding convertfrom utf-8"),
                        binding.index("set digest [hash_file $path]"))
        with tempfile.TemporaryDirectory(prefix=".path_binding_test_", dir=ROOT) as temp:
            tree = Path(temp)
            source = tree / "input with spaces_\u03bb.xci"
            source.write_bytes(b"full byte identity\n")
            manifest = tree / "inputs.sha256"
            action = f"""
set source {tcl_word(source)}
set inputs [write_input_manifest [list $source] {tcl_word(manifest)}]
if {{[dict keys $inputs] ne [list $source]}} {{error "bound path changed"}}
verify_inputs $inputs
puts BOUND_PATH_STRING_PASS
"""
            result = subprocess.run(["tclsh", "/dev/stdin"], input=procs + action,
                                    text=True, capture_output=True, cwd=tree,
                                    timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("BOUND_PATH_STRING_PASS", result.stdout)
            self.assertEqual(manifest.read_text(encoding="utf-8"),
                             f"{digest(source)}  {source}\n")


if __name__ == "__main__":
    unittest.main()
