#!/usr/bin/env python3
"""Inspect an acquired XDMA source, or patch a verified independent copy.

Does not download, compile, sign, install, access hardware, or alter trust.
The observed base is not a verified public AMD archive identity; see README.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

HERE=Path(__file__).resolve().parent


def digest(data):return hashlib.sha256(data).hexdigest()


def normalized(path):
    value=path.read_bytes().replace(b'\r\n',b'\n')
    if path.name=='XDMA.inx':
        # Explicit known adaptation already present in the measured base.
        value,n=re.subn(rb'("POLL_MODE",0x00010001,)0(?=\s*;)',rb'\g<1>1',value)
        if n>1:raise ValueError('Ambiguous POLL_MODE records')
    return value


def inspect(source):
    expected=json.loads((HERE/'observed_base_hashes.json').read_text())
    checks={}
    for rel,want in expected['files'].items():
        path=source/rel
        checks[rel]={'exists':path.is_file(),'match':path.is_file() and digest(normalized(path))==want['lf_sha256']}
    return {'verdict':'OBSERVED_BASE_MATCH' if all(x['match'] for x in checks.values()) else 'SOURCE_REVIEW_REQUIRED','official_archive_identity':'UNVERIFIED','files':checks,'normalization':'CRLF→LF; explicit INX POLL_MODE0→1 only'}


def apply_unified(root,patch):
    lines=patch.splitlines(keepends=True);i=0
    while i<len(lines):
        if not lines[i].startswith('--- a/'):raise ValueError('Invalid patch file header')
        rel=lines[i][6:].strip();i+=1
        if not lines[i].startswith('+++ b/') or lines[i][6:].strip()!=rel:raise ValueError('Mismatched patch paths')
        i+=1;path=(root/rel).resolve();path.relative_to(root.resolve())
        original=path.read_text().splitlines(keepends=True) if path.exists() else [];result=[];position=0
        while i<len(lines) and lines[i].startswith('@@ '):
            match=re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n?',lines[i])
            if not match:raise ValueError('Invalid hunk header')
            start=int(match[1]);old_count=int(match[2] or 1);new_count=int(match[4] or 1);target=max(start-1,0)
            if target<position:raise ValueError('Overlapping patch hunks')
            result+=original[position:target];position=target;i+=1;removed=added=0
            while i<len(lines) and not lines[i].startswith(('@@ ','--- a/')):
                line=lines[i];i+=1
                if not line or line[0] not in ' +-':raise ValueError('Unsupported patch line')
                if line[0] in ' -':
                    if position>=len(original) or original[position]!=line[1:]:raise ValueError('Patch context mismatch: '+rel)
                    position+=1;removed+=1
                if line[0] in ' +':result.append(line[1:]);added+=1
            if (removed,added)!=(old_count,new_count):raise ValueError('Patch count mismatch: '+rel)
        result+=original[position:];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(''.join(result),newline='\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('inspect','prepare'));p.add_argument('--source',required=True,type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    source=a.source.resolve();report=inspect(source)
    if a.action=='prepare':
        if report['verdict']!='OBSERVED_BASE_MATCH':raise ValueError('Unknown base: review exact differences; no patch applied')
        if not a.output or a.output.exists():raise ValueError('A new --output directory required')
        output=a.output.resolve()
        if output.is_relative_to(source):raise ValueError('Output must be outside source')
        # Copy only the measured driver/library source and required build inputs.
        manifest=json.loads((HERE/'observed_base_hashes.json').read_text())
        for rel in manifest['files']:
            target=output/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(normalized(source/rel))
        apply_unified(output,(HERE/'user_irq_polling.patch').read_text())
        report.update(output=str(output),patch_sha256=digest((HERE/'user_irq_polling.patch').read_bytes()),modified_files={p.relative_to(output).as_posix():digest(p.read_bytes()) for p in output.rglob('*') if p.is_file()},kernel_loaded=False)
        (output/'source_preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
