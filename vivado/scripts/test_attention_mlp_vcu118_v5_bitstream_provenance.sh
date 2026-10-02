#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_vcu118_v5_bitstream.sh"
BUILD_TCL="$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl"
PROVENANCE="$ROOT/vivado/scripts/v5_board_build_provenance.sh"
source "$PROVENANCE"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() {
    printf 'V5_BOARD_BITSTREAM_PROVENANCE_TEST_FAIL: %s\n' "$*" >&2
    exit 1
}

check_dynamic_archive() {
    local dir="$1" index
    local -a expected=() manifested=()
    (cd / && sha256sum -c --strict "$dir/OUTPUT_SHA256SUMS" \
        >/dev/null) || fail "output hashes do not verify: $dir"
    mapfile -d '' expected < <(find "$dir" -maxdepth 1 -type f \
        -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    mapfile -t manifested < <(awk \
        '{sub(/^[0-9a-f]{64}[[:space:]]+\*?/, ""); print}' \
        "$dir/OUTPUT_SHA256SUMS" | sort)
    [[ "${#expected[@]}" -eq "${#manifested[@]}" ]] ||
        fail "dynamic output cardinality mismatch: $dir"
    for index in "${!expected[@]}"; do
        [[ "${expected[$index]}" == "${manifested[$index]}" ]] ||
            fail "dynamic output path mismatch: $dir"
    done
}

# Exercise the Tcl trust boundary without Vivado.  A payload plus manifest
# rewrite still fails because the launcher-frozen manifest-self SHA is the
# root of trust.  Rejection must occur before open_project.
TCL_FIXTURE="$TMP/tcl_manifest_self"
mkdir -p "$TCL_FIXTURE/route" "$TCL_FIXTURE/out"
printf 'mutable project fixture\n' > "$TCL_FIXTURE/project.xpr"
inputs=("$TCL_FIXTURE/project.xpr")
for index in $(seq -w 1 133); do
    printf 'immutable fixture %s\n' "$index" > "$TCL_FIXTURE/input_$index"
    inputs+=("$TCL_FIXTURE/input_$index")
done
printf '%s\n' "${inputs[@]}" > "$TCL_FIXTURE/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$TCL_FIXTURE/INPUT_SHA256SUMS"
immutable=("${inputs[@]:1}")
printf '%s\n' "${immutable[@]}" > "$TCL_FIXTURE/IMMUTABLE_INPUT_FILES"
sha256sum -- "${immutable[@]}" > \
    "$TCL_FIXTURE/IMMUTABLE_INPUT_SHA256SUMS"
complete_manifest_sha="$(sha256sum -- \
    "$TCL_FIXTURE/INPUT_SHA256SUMS" | awk '{print $1}')"
immutable_manifest_sha="$(sha256sum -- \
    "$TCL_FIXTURE/IMMUTABLE_INPUT_SHA256SUMS" | awk '{print $1}')"

# Mutate one immutable payload and rewrite both content manifests so their
# rows are internally consistent.  Their externally frozen self hashes must
# nevertheless reject the forgery.
target="$TCL_FIXTURE/input_001"
printf 'synchronized payload mutation\n' >> "$target"
new_hash="$(sha256sum -- "$target" | awk '{print $1}')"
for manifest in "$TCL_FIXTURE/INPUT_SHA256SUMS" \
        "$TCL_FIXTURE/IMMUTABLE_INPUT_SHA256SUMS"; do
    awk -v path="$target" -v digest="$new_hash" '
        {
            row_path=$2
            sub(/^\*/, "", row_path)
            if (row_path == path) print digest "  " path
            else print
        }' "$manifest" > "$manifest.tmp"
    mv "$manifest.tmp" "$manifest"
done

cat > "$TCL_FIXTURE/runner.tcl" <<'TCL'
proc version {args} {return 2025.2}
proc set_param {name value} {
    if {$name ne "general.maxThreads" || $value != 32} {
        error "unexpected thread contract: $name=$value"
    }
}
proc open_project {args} {
    set fp [open $::env(HAP_OPEN_MARKER) w]
    puts $fp invoked
    close $fp
    error "open_project must not be reached"
}
if {![catch {source $::env(HAP_BUILD_TCL)} message]} {
    puts stderr "build Tcl unexpectedly accepted forged inputs"
    exit 1
}
if {[file exists $::env(HAP_OPEN_MARKER)]} {
    puts stderr "open_project was reached before manifest rejection"
    exit 2
}
if {[string first "complete INPUT_SHA256SUMS self-SHA256 mismatch" \
        $message] < 0} {
    puts stderr "unexpected build-Tcl rejection: $message"
    exit 3
}
TCL
HAP_PROJECT_FILE="$TCL_FIXTURE/project.xpr" \
HAP_REPORT_DIR="$TCL_FIXTURE/out" \
HAP_XDC_INVENTORY="$TCL_FIXTURE/input_002" \
HAP_OOC_ROUTE_DIR="$TCL_FIXTURE/route" \
HAP_INPUT_SHA_MANIFEST="$TCL_FIXTURE/INPUT_SHA256SUMS" \
HAP_INPUT_FILES="$TCL_FIXTURE/INPUT_FILES" \
HAP_INPUT_MANIFEST_SHA256="$complete_manifest_sha" \
HAP_IMMUTABLE_INPUT_SHA_MANIFEST=\
"$TCL_FIXTURE/IMMUTABLE_INPUT_SHA256SUMS" \
HAP_IMMUTABLE_INPUT_FILES="$TCL_FIXTURE/IMMUTABLE_INPUT_FILES" \
HAP_IMMUTABLE_INPUT_MANIFEST_SHA256="$immutable_manifest_sha" \
HAP_RECURSIVE_SOURCE_MANIFEST_SHA256="${complete_manifest_sha}" \
HAP_OOC_ROUTE_AUTHORIZATION_MANIFEST_SHA256="${complete_manifest_sha}" \
HAP_RECURSIVE_SOURCE_SHA_MANIFEST="$TCL_FIXTURE/input_003" \
HAP_OOC_ROUTE_AUTHORIZATION_SHA_MANIFEST="$TCL_FIXTURE/input_004" \
HAP_BUILD_TCL="$BUILD_TCL" HAP_OPEN_MARKER="$TCL_FIXTURE/open.marker" \
    tclsh "$TCL_FIXTURE/runner.tcl"

# A complete P14 route fixture and exact 134-file board input closure must pass
# both duplicated Tcl provenance gates and reach, but never execute beyond, a
# mocked open_project boundary.
P6_TCL_FIXTURE="$TMP/tcl_p6_route"
P6_ROUTE_FIXTURE="$P6_TCL_FIXTURE/route_parent/route"
P6_OUT="$P6_TCL_FIXTURE/out"
mkdir -p "$P6_OUT"
hap_v5_make_ooc_route_fixture "$P6_ROUTE_FIXTURE"
printf 'mutable project fixture\n' > "$P6_TCL_FIXTURE/project.xpr"
printf 'source XDC inventory fixture\n' > "$P6_TCL_FIXTURE/xdc_inventory.txt"

BOARD_SOURCE_MANIFEST="$ROOT/vivado/manifests/attention_mlp_board_core_v5_sources.list"
hap_v5_expand_source_manifest "$ROOT" "$BOARD_SOURCE_MANIFEST" \
    P6_SOURCE_MANIFESTS P6_RTL_SOURCES P6_SOURCE_CLOSURE
printf '%s\n' "${P6_SOURCE_MANIFESTS[@]}" > \
    "$P6_OUT/RECURSIVE_SOURCE_MANIFEST_FILES"
printf '%s\n' "${P6_RTL_SOURCES[@]}" > \
    "$P6_OUT/RECURSIVE_RTL_SOURCE_FILES"
printf '%s\n' "${P6_SOURCE_CLOSURE[@]}" > \
    "$P6_OUT/RECURSIVE_SOURCE_CLOSURE_FILES"
sha256sum "${P6_SOURCE_CLOSURE[@]}" > \
    "$P6_OUT/RECURSIVE_SOURCE_SHA256SUMS"

P6_ROUTE_AUTH=(
    "$P6_ROUTE_FIXTURE/summary.txt"
    "$P6_ROUTE_FIXTURE/selectors_post_route.txt"
    "$P6_ROUTE_FIXTURE/attention_geometry_post_route.txt"
    "$P6_ROUTE_FIXTURE/attention_geometry_placement_post_route.txt"
    "$P6_ROUTE_FIXTURE/base_pblocks_post_route.txt"
    "$P6_ROUTE_FIXTURE/p5_input_plan_post_route.txt"
    "$P6_ROUTE_FIXTURE/p5_input_pblocks_post_route.txt"
    "$P6_ROUTE_FIXTURE/p9_postprocess_plan_post_route.txt"
    "$P6_ROUTE_FIXTURE/p9_postprocess_pblocks_post_route.txt"
    "$P6_ROUTE_FIXTURE/p9_quantizer3_plan_post_route.txt"
    "$P6_ROUTE_FIXTURE/p9_quantizer3_pblock_post_route.txt"
    "$P6_ROUTE_FIXTURE/p14_region2_relief_plan_post_route.txt"
    "$P6_ROUTE_FIXTURE/p14_region2_relief_pblock_post_route.txt"
    "$P6_ROUTE_FIXTURE/p8_parent_ingress_boundary_input.txt"
    "$P6_ROUTE_FIXTURE/p8_parent_ingress_boundary_post_route.txt"
    "$P6_ROUTE_FIXTURE/architecture_boundaries_input.txt"
    "$P6_ROUTE_FIXTURE/architecture_boundaries_post_route.txt"
    "$P6_ROUTE_FIXTURE/launcher_status.txt"
    "$P6_ROUTE_FIXTURE/INPUT_FILES"
    "$P6_ROUTE_FIXTURE/INPUT_SHA256SUMS"
    "$P6_ROUTE_FIXTURE/OUTPUT_SHA256SUMS"
    "$P6_ROUTE_FIXTURE/post_route.dcp"
)
printf '%s\n' "${P6_ROUTE_AUTH[@]}" > \
    "$P6_OUT/OOC_ROUTE_AUTHORIZATION_FILES"
sha256sum "${P6_ROUTE_AUTH[@]}" > \
    "$P6_OUT/OOC_ROUTE_AUTHORIZATION_SHA256SUMS"

P6_INPUTS=(
    "$P6_TCL_FIXTURE/project.xpr"
    "$P6_TCL_FIXTURE/xdc_inventory.txt"
    "$ROOT/vivado/constraints/attention_mlp_vcu118_board_v5.xdc"
    "$BUILD_TCL"
    "$LAUNCHER"
    "$ROOT/vivado/scripts/attention_mlp_vcu118_v5_post_route_gate.tcl"
    "$ROOT/vivado/scripts/write_attention_mlp_vcu118_v5_xdc_inventory.tcl"
    "$ROOT/vivado/scripts/apply_attention_mlp_vcu118_v5_floorplan.tcl"
    "$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
    "$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
    "$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
    "$ROOT/vivado/scripts/v5_production_p9_postprocess_partition_floorplan.tcl"
    "$ROOT/vivado/scripts/v5_production_p9_quantizer3_locality_floorplan.tcl"
    "$ROOT/vivado/scripts/v5_production_p14_region2_x2_relief_floorplan.tcl"
    "$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"
    "$PROVENANCE"
    "$P6_OUT/RECURSIVE_SOURCE_MANIFEST_FILES"
    "$P6_OUT/RECURSIVE_RTL_SOURCE_FILES"
    "$P6_OUT/RECURSIVE_SOURCE_CLOSURE_FILES"
    "$P6_OUT/RECURSIVE_SOURCE_SHA256SUMS"
    "$P6_OUT/OOC_ROUTE_AUTHORIZATION_FILES"
    "$P6_OUT/OOC_ROUTE_AUTHORIZATION_SHA256SUMS"
    "${P6_SOURCE_CLOSURE[@]}"
    "${P6_ROUTE_AUTH[@]}"
)
[[ "${#P6_INPUTS[@]}" -eq 134 ]]
printf '%s\n' "${P6_INPUTS[@]}" > "$P6_OUT/INPUT_FILES"
sha256sum "${P6_INPUTS[@]}" > "$P6_OUT/INPUT_SHA256SUMS"
P6_IMMUTABLE=("${P6_INPUTS[@]:1}")
printf '%s\n' "${P6_IMMUTABLE[@]}" > "$P6_OUT/IMMUTABLE_INPUT_FILES"
sha256sum "${P6_IMMUTABLE[@]}" > "$P6_OUT/IMMUTABLE_INPUT_SHA256SUMS"

cat > "$P6_TCL_FIXTURE/runner.tcl" <<'TCL'
proc version {args} {return 2025.2}
proc set_param {name value} {
    if {$name ne "general.maxThreads" || $value != 32} {
        error "unexpected thread contract: $name=$value"
    }
}
proc open_project {args} {
    set fp [open $::env(HAP_OPEN_MARKER) w]
    puts $fp reached
    close $fp
    error P14_PROVENANCE_REACHED_OPEN_PROJECT
}
if {![catch {source $::env(HAP_BUILD_TCL)} message]} {
    puts stderr "build Tcl unexpectedly ran past mock open_project"
    exit 1
}
if {![file exists $::env(HAP_OPEN_MARKER)] ||
    [string first P14_PROVENANCE_REACHED_OPEN_PROJECT $message] < 0} {
    puts stderr "P14 provenance did not reach open_project: $message"
    exit 2
}
TCL
HAP_PROJECT_FILE="$P6_TCL_FIXTURE/project.xpr" \
HAP_REPORT_DIR="$P6_OUT" \
HAP_XDC_INVENTORY="$P6_TCL_FIXTURE/xdc_inventory.txt" \
HAP_OOC_ROUTE_DIR="$P6_ROUTE_FIXTURE" \
HAP_INPUT_SHA_MANIFEST="$P6_OUT/INPUT_SHA256SUMS" \
HAP_INPUT_FILES="$P6_OUT/INPUT_FILES" \
HAP_INPUT_MANIFEST_SHA256="$(sha256sum "$P6_OUT/INPUT_SHA256SUMS" | awk '{print $1}')" \
HAP_IMMUTABLE_INPUT_SHA_MANIFEST="$P6_OUT/IMMUTABLE_INPUT_SHA256SUMS" \
HAP_IMMUTABLE_INPUT_FILES="$P6_OUT/IMMUTABLE_INPUT_FILES" \
HAP_IMMUTABLE_INPUT_MANIFEST_SHA256="$(sha256sum "$P6_OUT/IMMUTABLE_INPUT_SHA256SUMS" | awk '{print $1}')" \
HAP_RECURSIVE_SOURCE_MANIFEST_SHA256="$(sha256sum "$P6_OUT/RECURSIVE_SOURCE_SHA256SUMS" | awk '{print $1}')" \
HAP_OOC_ROUTE_AUTHORIZATION_MANIFEST_SHA256="$(sha256sum "$P6_OUT/OOC_ROUTE_AUTHORIZATION_SHA256SUMS" | awk '{print $1}')" \
HAP_RECURSIVE_SOURCE_SHA_MANIFEST="$P6_OUT/RECURSIVE_SOURCE_SHA256SUMS" \
HAP_OOC_ROUTE_AUTHORIZATION_SHA_MANIFEST="$P6_OUT/OOC_ROUTE_AUTHORIZATION_SHA256SUMS" \
HAP_BOARD_INPUT_COUNT=134 HAP_BOARD_IMMUTABLE_INPUT_COUNT=133 \
HAP_BOARD_SOURCE_MANIFEST_COUNT=3 HAP_BOARD_RTL_SOURCE_COUNT=87 \
HAP_BOARD_SOURCE_CLOSURE_COUNT=90 HAP_JOBS=32 \
HAP_BUILD_TCL="$BUILD_TCL" HAP_OPEN_MARKER="$P6_TCL_FIXTURE/open.marker" \
    tclsh "$P6_TCL_FIXTURE/runner.tcl"

# Exercise the full launcher with a mock tool.  The mock changes an immutable
# generated input during the tool run and returns success.  The shell must
# convert that to a provenance failure, preserve the original tool status,
# and archive every diagnostic including the journal.
ROUTE_FIXTURE="$TMP/route_fixture/route"
hap_v5_make_ooc_route_fixture "$ROUTE_FIXTURE"
printf 'project fixture\n' > "$TMP/project.xpr"
mkdir -p "$TMP/mockbin"
cat > "$TMP/mockbin/pgrep" <<'MOCK'
#!/usr/bin/env bash
exit 1
MOCK
cat > "$TMP/mockbin/vivado" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
log="" journal=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -log) log="$2"; shift 2 ;;
        -journal) journal="$2"; shift 2 ;;
        *) shift ;;
    esac
done
printf 'mock board build log\n' > "$log"
printf 'mock board build journal\n' > "$journal"
printf 'mock extra diagnostic\n' > "$HAP_REPORT_DIR/mock_diagnostic.txt"
printf 'mutated during mock tool run\n' >> \
    "$HAP_REPORT_DIR/XDC_SOURCE_INVENTORY"
exit 0
MOCK
chmod +x "$TMP/mockbin/pgrep" "$TMP/mockbin/vivado"

set +e
PATH="$TMP/mockbin:$PATH" VIVADO="$TMP/mockbin/vivado" \
HAP_PROJECT_FILE="$TMP/project.xpr" HAP_REPORT_DIR="$TMP/board_failure" \
    "$LAUNCHER" "$ROUTE_FIXTURE" >"$TMP/launcher.stdout" \
    2>"$TMP/launcher.stderr"
launcher_rc=$?
set -e
if [[ "$launcher_rc" -ne 95 ]]; then
    sed -n '1,160p' "$TMP/launcher.stderr" >&2
    fail "immutable postcheck failure code was not preserved: $launcher_rc"
fi
for exact in status=FAIL final_exit_code=95 vivado_exit_code=0 \
        vivado_invoked=1 complete_input_manifest_sha_match=1 \
        immutable_input_count=133 immutable_input_manifest_sha_match=1 \
        immutable_input_postcheck=0 project_file_postcheck_exempt=1 \
        bitstream_generated=0; do
    grep -Fqx -- "$exact" "$TMP/board_failure/launcher_status.txt" ||
        fail "board failure status is missing: $exact"
done
for required in vivado.log vivado.jou mock_diagnostic.txt INPUT_FILES \
        INPUT_SHA256SUMS IMMUTABLE_INPUT_FILES \
        IMMUTABLE_INPUT_SHA256SUMS launcher_status.txt; do
    grep -Fq -- "$TMP/board_failure/$required" \
        "$TMP/board_failure/OUTPUT_SHA256SUMS" ||
        fail "board failure archive omitted $required"
done
check_dynamic_archive "$TMP/board_failure"

normalized="$(sed -zE 's/\\[[:space:]]+/ /g; s/[[:space:]]+/ /g' \
    "$BUILD_TCL")"
case "$normalized" in
    *'set complete_inputs [hap_board_verify_sha_manifest'*\
'source [file join $script_dir attention_mlp_vcu118_v5_post_route_gate.tcl]'*\
'open_project $project_file'*) ;;
    *) fail 'manifest/source/open_project order is not fail-closed' ;;
esac

printf 'V5_BOARD_BITSTREAM_PROVENANCE_TEST_PASS\n'
printf 'manifest_self_synchronized_mutation_negative=PASS\n'
printf 'p14_route_to_open_project_positive=PASS\n'
printf 'immutable_post_tool_mutation_negative=PASS\n'
printf 'failure_dynamic_archive=PASS\n'
