#!/usr/bin/env bash
set -uo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
cd "$ROOT" || exit 2

command -v jq >/dev/null 2>&1 || {
    printf 'ERROR: jq is required\n' >&2
    exit 2
}

candidate_count=0
running_count=0
invalid_count=0
total_count=0

printf 'classification\tkind\tstatus\texit\tdir_hash\tinput_hash\tooc_gate\tpath\n'

while IFS= read -r -d '' status_file; do
    directory=${status_file%/STATUS}
    total_count=$((total_count + 1))

    kind=other
    case "$directory" in
        */xsim/*) kind=xsim ;;
        */ooc/*) kind=ooc ;;
    esac

    status=$(tr -d '[:space:]' < "$status_file")

    exit_gate=MISSING
    if [[ -f "$directory/exit_status.txt" ]]; then
        exit_value=$(tr -d '[:space:]' < "$directory/exit_status.txt")
        if [[ "$exit_value" == 0 ]]; then
            exit_gate=PASS
        else
            exit_gate=FAIL
        fi
    fi

    dir_hash=MISSING
    if [[ -f "$directory/SHA256SUMS" ]]; then
        if (cd "$ROOT/$directory" && sha256sum -c SHA256SUMS >/dev/null 2>&1); then
            dir_hash=PASS
        else
            dir_hash=FAIL
        fi
    fi

    input_hash=MISSING
    if [[ -f "$directory/INPUT_SHA256SUMS" ]]; then
        if (cd "$ROOT/$directory" &&
                sha256sum -c INPUT_SHA256SUMS >/dev/null 2>&1); then
            input_hash=PASS
        else
            input_hash=FAIL
        fi
    fi

    ooc_gate=NA
    if [[ "$kind" == ooc ]]; then
        ooc_gate=MISSING
        if [[ -f "$directory/summary.json" ]]; then
            if jq -e '
                (.tool == 2025.2) and
                (.part == "xcvu9p-flga2104-2L-e") and
                (.clock_mhz == 100 or .clock_mhz == 100.0) and
                (.clock_period_ns == 10 or .clock_period_ns == 10.0) and
                (.clock_source_site == "BUFGCE_X0Y0") and
                (.setup_uncertainty_ns >= 0.149999 and
                    .setup_uncertainty_ns <= 0.150001) and
                (.hold_uncertainty_ns == 0) and
                (.wns_ns >= 0) and (.whs_ns >= 0) and
                (.drc_errors == 0) and
                ((.unrouted_nets // .unrouted // -1) == 0) and
                (.valid == 1)
            ' "$directory/summary.json" >/dev/null 2>&1; then
                ooc_gate=PASS
            else
                ooc_gate=FAIL
            fi
        fi
    fi

    classification=INVALID_OR_DIAGNOSTIC
    if [[ "$status" == RUNNING ]]; then
        classification=RUNNING
        running_count=$((running_count + 1))
    elif [[ "$status" == PASS && "$exit_gate" == PASS &&
            "$dir_hash" == PASS && "$input_hash" == PASS &&
            ("$kind" != ooc || "$ooc_gate" == PASS) ]]; then
        classification=VALID_CANDIDATE
        candidate_count=$((candidate_count + 1))
    else
        invalid_count=$((invalid_count + 1))
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$classification" "$kind" "$status" "$exit_gate" "$dir_hash" \
        "$input_hash" "$ooc_gate" "$directory"
done < <(find result -type f -name STATUS -print0 | sort -z)

printf 'AUDIT_COUNTS total=%d valid_candidates=%d running=%d invalid_or_diagnostic=%d\n' \
    "$total_count" "$candidate_count" "$running_count" "$invalid_count" >&2
