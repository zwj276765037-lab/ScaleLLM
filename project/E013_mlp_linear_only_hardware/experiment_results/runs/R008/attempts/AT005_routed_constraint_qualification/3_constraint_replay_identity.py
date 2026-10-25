#!/usr/bin/env python3
"""Compare executable exported constraints plus effective hierarchical scope.

Tool headers, source-file comments, and redundant current_instance switches are
not constraints. Every actual constraint command keeps its order and contents.
No Tcl design command is evaluated here.
"""
import argparse,hashlib,json,re,tkinter
from pathlib import Path

def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def records(path):
 t=tkinter.Tcl();scope='';pending='';result=[]
 for line in path.read_text().splitlines(keepends=True):
  if not pending and (not line.strip() or line.lstrip().startswith('#')):continue
  pending+=line
  if not t.call('info','complete',pending):continue
  command=re.sub(r'\\\n[ \t]*',' ',pending).strip();pending=''
  if command.startswith('current_instance'):
   words=list(t.splitlist(command))
   if not words or words.pop(0)!='current_instance':raise ValueError('invalid scope command')
   words=[word for word in words if word!='-quiet']
   if len(words)>1 or (words and words[0] in ('.','..')):raise ValueError('unsupported relative scope command')
   scope=words[0] if words else ''
   continue
  result.append({'scope':scope,'command':command})
 if pending.strip():raise ValueError('incomplete exported Tcl constraint')
 if not result:raise ValueError('no executable constraints')
 return {'constraints':result,'final_scope':scope}

def compare(reference,replay):
 reference_identity,replay_identity=records(reference),records(replay)
 before,after=reference_identity['constraints'],replay_identity['constraints']
 if reference_identity!=replay_identity:
  diffs=[]
  for index in range(max(len(before),len(after))):
   a=before[index] if index<len(before) else None;b=after[index] if index<len(after) else None
   if a!=b:diffs.append({'index':index,'reference':a,'replay':b})
   if len(diffs)>=10:break
  raise ValueError({'executable_constraint_or_scope_difference':diffs,'reference_count':len(before),'replay_count':len(after),'reference_final_scope':reference_identity['final_scope'],'replay_final_scope':replay_identity['final_scope']})
 canonical=json.dumps(reference_identity,sort_keys=True,separators=(',',':')).encode()
 return {'status':'IDENTICAL_ORDERED_EXECUTABLE_CONSTRAINTS_AND_EFFECTIVE_SCOPES','constraint_commands':len(before),'effective_scopes':len({row['scope'] for row in before}),'final_scope':reference_identity['final_scope'],'canonical_sha256':hashlib.sha256(canonical).hexdigest(),'reference_raw_sha256':sha(reference),'replay_raw_sha256':sha(replay),'scope':'comments_and_redundant_scope_switches_excluded; actual_constraint_command_bytes_and_order_preserved'}

def main():
 p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('replay',type=Path);a=p.parse_args();print(json.dumps(compare(a.reference,a.replay),sort_keys=True))
if __name__=='__main__':main()
