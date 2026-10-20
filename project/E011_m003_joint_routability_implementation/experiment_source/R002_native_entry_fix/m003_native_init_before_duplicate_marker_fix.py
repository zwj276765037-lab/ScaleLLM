#!/usr/bin/env python3
"""Bind a complete INIT-only prefix from the current native generated driver."""
from pathlib import Path
import argparse, hashlib, json, re, shutil


def identity(path):
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def init_prefix(text):
    boundary = '\nOPTRACE "Phase: Opt Design" START { ROLLUP_AUTO }\n'
    if text.count(boundary) != 1:
        raise ValueError('native driver lacks one exact INIT/OPT phase boundary')
    prefix = text.split(boundary, 1)[0]+'\n'
    for marker in ('\nstart_step init_design\n', '\n  end_step init_design\n',
                   '\nOPTRACE "Phase: Init Design" END { }\n'):
        if prefix.count(marker) != 1:
            raise ValueError('native INIT prefix lacks unique complete stage marker')
    if not re.search(r'^\s*link_design\s', prefix, re.M):
        raise ValueError('native INIT has no link_design')
    if re.search(r'^\s*(?:opt_design|place_design|phys_opt_design|route_design|write_bitstream|start_step opt_design)\b', prefix, re.M):
        raise ValueError('native INIT prefix contains a later implementation command')
    if not prefix.rstrip().endswith('OPTRACE "Phase: Init Design" END { }'):
        raise ValueError('native INIT prefix must end after the complete INIT phase')
    return prefix


def prepare(driver, output):
    preserved = output.with_name(output.stem+'_full_generated_driver.tcl')
    if output.exists() or output.with_suffix('.json').exists() or preserved.exists():
        raise ValueError('native INIT derived evidence already exists')
    original = driver.read_text()
    prefix = init_prefix(original)
    shutil.copyfile(driver, preserved)
    if preserved.read_bytes() != driver.read_bytes():
        raise ValueError('native generated driver changed while preserving')
    output.write_text(prefix)
    hooks=[]
    for line in prefix.splitlines():
        if not re.match(r'^\s*source\b', line):
            continue
        match=re.fullmatch(r'\s*source(?:\s+-notrace)?\s+(?:\{([^}]+)\}|"([^"]+)"|([^\s;]+))\s*',line)
        if not match:
            raise ValueError('native INIT has an unresolved source hook')
        path=Path(next(v for v in match.groups() if v is not None))
        if not path.is_absolute() or not path.is_file():
            raise ValueError('native INIT hook must be an existing absolute source')
        hooks.append(identity(path))
    value = dict(schema='M003_current_native_INIT_prefix_v2', driver=identity(driver),
                 preserved_driver=identity(preserved),
                 source_hooks=hooks,
                 prefix=identity(output), prefix_lines=len(prefix.splitlines()),
                 boundary='complete native INIT end before native OPT phase start',
                 original_unchanged=True, later_commands_in_prefix=False,
                 native_execution_and_checkpoint_still_required=True)
    output.with_suffix('.json').write_text(json.dumps(value, indent=2)+'\n')
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--driver', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.driver, a.output)))
