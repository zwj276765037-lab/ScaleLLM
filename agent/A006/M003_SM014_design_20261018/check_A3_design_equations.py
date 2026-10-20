#!/usr/bin/env python3
"""Offline state-equation check, NOT RTL simulation or URAM implementation evidence."""
import datetime,hashlib,itertools,json,os,random
from pathlib import Path
HERE=Path(__file__).resolve().parent
def old_next(a,s,l,r):
 if s:return 0
 n=a
 if l:n=0
 if r:n=(a+1)&131071
 return n
def local_next(a,s,l,r):
 ce=s or l or r
 d=((a+1)&131071) if r and not s else 0
 return d if ce else a
def invalid_format(v):
 return any(((v>>(16*c+14))&3)!=0 or (((v>>(16*c))&255)==0 and ((v>>(16*c+8))&63)!=0) for c in range(16))
def initword(a):return ((a+1)*0x9e3779b97f4a7c156a09e667f3bcc909d41d8cd98f00b204e9800998ecf84221)&((1<<256)-1)
def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 out=HERE/'F2_A3_offline_equation_check.json';assert not out.exists()
 total=0
 for s,l,r in itertools.product((False,True),repeat=3):
  for a in range(131072):
   assert old_next(a,s,l,r)==local_next(a,s,l,r),(a,s,l,r)
   total+=1
 assert old_next(1234,False,False,False)==1234 # abort-only is not S
 assert local_next(1234,False,True,True)==1235 # R trailing NBA wins L
 rng=random.Random(20261018);memory={};slices=({},{});mask=(1<<128)-1
 response=0;split_response=[0,0];token=True;valid=False
 counts={'write':0,'read':0,'format':0,'error':False}
 n=30000;collisions=stalls=clears=invalids=0
 for cycle in range(n):
  rst=cycle not in (0,17001);clear=(cycle%997)==0
  wr_valid=rng.randrange(2)==1;rd_valid=rng.randrange(2)==1;rsp_ready=rng.randrange(3)!=0
  candidates=[0,1,81919,81920,131071,rng.randrange(81920)]
  wa=rng.choice(candidates);ra=wa if cycle%5==0 else rng.choice(candidates)
  wd=rng.getrandbits(256)
  wf=rst and not clear and wa<81920 and wr_valid
  rf=rst and not clear and token and ra<81920 and rd_valid
  sf=rst and not clear and valid and rsp_ready
  prior_response=response;prior_split=tuple(split_response)
  if rf:
   response=memory.get(ra,initword(ra))
   split_response=[slices[j].get(ra,(initword(ra)>>(j*128))&mask) for j in range(2)]
   assert response==(split_response[0]|(split_response[1]<<128))
  if wf:
   memory[wa]=wd
   for j in range(2):slices[j][wa]=(wd>>(j*128))&mask
  if wf and rf and wa==ra:collisions+=1
  if valid and not rsp_ready:
   stalls+=1
   if not rf:assert response==prior_response and tuple(split_response)==prior_split
  if not rst or clear:
   token=True;valid=False;counts={'write':0,'read':0,'format':0,'error':False};clears+=1
  else:
   if rf:token=False
   elif sf:token=True
   if sf:valid=False
   if rf:valid=True
   if wf:
    counts['write']=(counts['write']+1)&0xffffffff
    if invalid_format(wd):counts['format']=(counts['format']+1)&0xffffffff;counts['error']=True
   if sf:counts['read']=(counts['read']+1)&0xffffffff
   if wr_valid and wa>=81920 or rd_valid and ra>=81920:counts['error']=True;invalids+=1
  assert response==(split_response[0]|(split_response[1]<<128))
  if cycle%1000==0:
   for a,v in memory.items():assert v==(slices[0][a]|(slices[1][a]<<128))
 result=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),execution='completed',verdict='DESIGN_EQUATIONS_PASS_NOT_RTL_OR_URAM_PROOF',all_17bit_address_S_L_R_cases=total,async_reset_invariant='all copies zero by design; checked recurrence induction requires equal prestate',split_storage_cycles=n,same_address_write_read_old_value_cases=collisions,stall_cycles=stalls,reset_clear_cycles=clears,invalid_address_event_cycles=invalids,seed=20261018,limitations=['No production RTL changed or simulated','No new EDA or native URAM RDW proof','One common controller modeled; does not independently prove future RTL controller is singular'],producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
