"""Expand only proven same-call clock groups into existing qualification fields."""
import copy
SCHEMA='M003_native_grouped_stream_v1'
def decode(snapshot):
 if snapshot.get('schema')!=SCHEMA:raise ValueError('Unknown grouped native snapshot schema')
 if snapshot.get('meta',{}).get('kind')!='native':raise ValueError('Grouped evidence must be native')
 groups=snapshot.get('connection_groups');endpoints=snapshot.get('connection_endpoints');counts=snapshot.get('connection_counts',{})
 if not isinstance(groups,list) or not isinstance(endpoints,list):raise ValueError('Missing group/member tables')
 by={};aliases={}
 def strings(value,label,nonempty=False):
  if not isinstance(value,list) or any(not isinstance(x,str) or not x for x in value) or len(set(value))!=len(value) or (nonempty and not value):raise ValueError('Invalid '+label)
  if len(value)>131072:raise ValueError('Collection exceeds bound: '+label)
  return value
 for g in groups:
  if not isinstance(g,dict) or not isinstance(g.get('id'),str) or not g['id'] or g['id'] in by:raise ValueError('Duplicate/invalid group')
  gid=g['id'];nets=strings(g.get('nets'),'nets',True)
  if any(n in aliases for n in nets):raise ValueError('Overlapping groups')
  aliases.update({n:gid for n in nets})
  if g.get('canonical_top_net') not in nets:raise ValueError('Canonical top missing from group')
  drivers=strings(g.get('leaf_drivers'),'drivers');owners=g.get('driver_cells');refs=g.get('driver_refs');ports=strings(g.get('primary_ports'),'ports');dirs=g.get('primary_port_directions')
  if not isinstance(owners,list) or not isinstance(refs,list) or not isinstance(dirs,list) or not len(drivers)==len(owners)==len(refs) or any(not isinstance(x,str) or not x for x in owners+refs):raise ValueError('Driver owner/ref/port shape')
  if any(d.rsplit('/',1)[0]!=o for d,o in zip(drivers,owners)):raise ValueError('Driver owner identity')
  if not ((len(drivers)==1 and not ports and not dirs) or (not drivers and len(ports)==1 and dirs==['IN'])):raise ValueError('Nonexclusive clock source')
  by[gid]=dict(nets=' '.join(nets),drivers=' '.join(drivers),driver_cells=' '.join(owners),driver_refs=' '.join(refs),primary_ports=' '.join(ports),primary_port_directions=' '.join(dirs))
 bound={}
 for e in endpoints:
  if not isinstance(e,dict) or not isinstance(e.get('pin'),str) or not e['pin'] or e['pin'] in bound or e.get('group') not in by:raise ValueError('Unknown/duplicate endpoint')
  direct=strings(e.get('direct_nets'),'direct nets',True)
  if len(direct)!=1 or aliases.get(direct[0])!=e['group']:raise ValueError('Direct-net membership missing')
  bound[e['pin']]=e['group']
 if counts!={'endpoints':len(bound),'groups':len(by)}:raise ValueError('Connection count mismatch')
 # Copy rows only; immutable large joined group strings are reused per reference.
 result={k:v for k,v in snapshot.items() if k not in {'schema','connection_groups','connection_endpoints','connection_counts','connection_api_counts'}};used={};used_groups=set()
 def require(pin,gid,kind):
  if not isinstance(pin,str) or not isinstance(gid,str) or bound.get(pin)!=gid:raise ValueError('Unproven group reference')
  if pin in used and not (kind=='helper_C' and used[pin]=={'cell_C'}):raise ValueError('Duplicate group reference')
  used.setdefault(pin,set()).add(kind);used_groups.add(gid);return by[gid]
 result['cells']=[]
 for row in snapshot.get('cells',[]):
  row=dict(row)
  if 'C_nets_group' in row:
   if 'C_nets' in row:raise ValueError('Conflicting cell clock fields')
   row['C_nets']=require(row.get('NAME','')+'/C',row.pop('C_nets_group'),'cell_C')['nets']
  result['cells'].append(row)
 result['memory_pins']=[]
 for row in snapshot.get('memory_pins',[]):
  row=dict(row)
  if row.get('pin')=='CLK':
   fields={'nets','drivers','driver_cells','driver_refs','primary_ports','primary_port_directions'}
   if fields.intersection(row) or 'connection_group' not in row:raise ValueError('Missing/conflicting memory clock group')
   row.update(require(row.get('cell','')+'/CLK',row.pop('connection_group'),'memory_CLK'))
  elif 'connection_group' in row:raise ValueError('Group optimization outside clock scope')
  result['memory_pins'].append(row)
 result['helper_pins']=[]
 address_cells={r.get('NAME') for r in result['cells'] if r.get('role')=='address'}
 for row in snapshot.get('helper_pins',[]):
  row=dict(row)
  if 'clock_connection_group' in row:
   if row.get('pin')!='C' or row.get('cell') not in address_cells or {'nets','drivers'}.intersection(row):raise ValueError('Invalid helper clock group reference')
   g=require(row['cell']+'/C',row.pop('clock_connection_group'),'helper_C')
   row.update(nets=g['nets'],drivers=g['drivers'])
  result['helper_pins'].append(row)
 cs=dict(snapshot.get('control_sources',{}))
 if 'clock_group' not in cs or 'clock_pin' not in cs or 'clock' in cs:raise ValueError('Selected clock membership witness missing/conflicting')
 cs['clock']=require(cs.pop('clock_pin'),cs.pop('clock_group'),'boundary_clock')['nets'];result['control_sources']=cs
 if set(used)!=set(bound) or used_groups!=set(by):raise ValueError('Unused member/group evidence')
 return result
