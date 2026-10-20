# These helpers are inserted into the ordinary entry validator, not imported
# as an unmanifested runtime dependency. Raw native facts are never rewritten.
def validate_address_state(z, own_q, other_q, original_names, require):
    raw=words(z.get('D_startpoints',''))
    cone=set(words(z.get('D_full_fanin','')))
    only=words(z.get('D_startpoint_cells',''));onlyrefs=words(z.get('D_startpoint_cell_refs',''))
    try:facts=json.loads(z.get('D_source_facts',''))
    except (ValueError,TypeError):facts=[];require(False,'address D actual source evidence invalid')
    require(isinstance(facts,list),'address D actual source evidence is not rows')
    if not isinstance(facts,list):facts=[]
    require(bool(raw) and len(raw)==len(set(raw)) and [r.get('raw_name') for r in facts]==raw,'address D own state raw startpoints incomplete')
    require(len(only)==len(onlyrefs) and len(only)==len(set(only)),'address D only_cells inventory invalid')
    owners={};proven=set()
    for f in facts:
        name=f.get('raw_name','');kind=f.get('class','').lower()
        require(name in cone,'address D raw source absent from full fanin')
        ns=words(f.get('owner_names',''));refs=words(f.get('owner_refs',''))
        qs=words(f.get('owner_Q_pins',''));members=words(f.get('owner_Q_in_full_fanin',''))
        if kind=='port':
            require(not ns and not refs and not qs and not members,'address D primary-port owner fabricated')
            continue
        require(kind=='pin' and len(ns)==len(refs)==1,'address D source owner unresolved')
        if len(ns)!=1 or len(refs)!=1:continue
        require(name.rsplit('/',1)[0]==ns[0],'address D raw source owner identity changed')
        require(isff(refs[0]),'address D unknown state source primitive')
        require(len(qs)==len(members)==1 and qs==[ns[0]+'/Q'] and members==['1'] and qs[0] in cone,'address D actual owner Q not in full fanin')
        owners[ns[0]]=refs[0]
        if len(qs)==1 and members==['1'] and qs[0] in cone:proven.add(qs[0])
    require(owners==dict(zip(only,onlyrefs)),'address D only_cells and actual owners disagree')
    require(z.get('NAME','')+'/Q' in proven and bool(proven&own_q),'address D does not use own state')
    require(not(proven&other_q) and not(set(owners)&original_names),'address D takes other/core address state')
    require(not (cone&other_q) and not any(n.rsplit('/',1)[0] in original_names for n in cone),'address D full fanin takes other/core address state')


def selected_uram_terminals():
    pins={'CLK','EN_A','EN_B','RDB_WR_A','RDB_WR_B'}
    for port in ('A','B'):
        for prefix,width in [('ADDR',23),('CAS_IN_ADDR',23),('BWE',9),('CAS_IN_BWE',9),('CAS_IN_DIN',72),('CAS_IN_DOUT',72)]:
            pins.update(f'{prefix}_{port}[{bit}]' for bit in range(width))
        pins.update(f'CAS_IN_{signal}_{port}' for signal in ('DBITERR','EN','RDACCESS','RDB_WR','SBITERR'))
    return pins


def validate_effective_memories(s, memories, addr, original_names, sources, require):
    identity={z['NAME']:i for i,ms in memories.items() for z in ms}
    configs=s.get('uram_configs',[]);cfg={c.get('NAME'):c for c in configs}
    require(len(configs)==len(cfg)==80 and set(cfg)==set(identity),'URAM native configuration inventory incomplete')
    table={};pin_counts=collections.Counter()
    for p in s.get('memory_pins',[]):
        key=(p.get('cell'),p.get('pin'));pin_counts[p.get('cell')]+=1
        require(key not in table,'URAM duplicate native pin evidence');table[key]=p
        require(p.get('cell') in identity and str(p.get('slice'))==str(identity.get(p.get('cell'))),'URAM pin identity/slice mismatch')
        ds=words(p.get('drivers',''));rs=words(p.get('driver_refs',''));os=words(p.get('driver_cells',''))
        require(len(ds)==len(rs)==len(os) and all(d.rsplit('/',1)[0]==o for d,o in zip(ds,os)),'URAM driver owner/reference inventory incomplete')
        if p.get('pin')!='CLK':
            # The only allowed disconnected inputs are unselected direct ADDR
            # on nonFIRST cells; their exact native shape is checked below.
            empty_direct=str(p.get('pin','')).startswith('ADDR_') and cfg.get(p.get('cell'),{}).get('CASCADE_ORDER_A') in ('MIDDLE','LAST')
            require(empty_direct or (bool(words(p.get('nets',''))) and len(ds)==1),'URAM required input net/driver unresolved')
        if str(p.get('pin','')).startswith('CAS_IN'):
            require(all(o not in identity or identity[o]==identity.get(p.get('cell')) for o in os),'URAM cascade crosses selected slice pool')
    expected=selected_uram_terminals()
    for name in identity:
        require(pin_counts[name]==len(expected) and {pin for cell,pin in table if cell==name}==expected,'URAM per-cell native pin coverage incomplete')
    def row(name,pin):return table.get((name,pin),{})
    def constant(p,ref,label):
        require(words(p.get('driver_refs',''))==[ref] and len(words(p.get('drivers','')))==1 and bool(words(p.get('nets',''))),label)
    def edge(name,pin,parent,out):
        p=row(name,pin)
        require(words(p.get('drivers',''))==[parent+'/'+out] and words(p.get('driver_cells',''))==[parent] and words(p.get('driver_refs',''))==['URAM288'] and bool(words(p.get('nets',''))),'URAM cascade predecessor/bit mismatch: '+name+'/'+pin)
    core_scopes={n.rsplit('/',1)[0] for n in original_names}
    require(len(core_scopes)==1,'URAM original core scope unresolved')
    core_scope=next(iter(core_scopes),'UNRESOLVED')
    pred={};roots=[];decode=collections.defaultdict(collections.Counter)
    for name,i in identity.items():
        c=cfg.get(name,{})
        require(str(c.get('slice'))==str(i),'URAM configuration slice changed')
        kind=c.get('CASCADE_ORDER_A');require(kind in ('FIRST','MIDDLE','LAST') and kind==c.get('CASCADE_ORDER_B'),'URAM unknown/mixed cascade input configuration')
        for port in ('A','B'):
            for stem in ('IREG_PRE_','REG_CAS_','OREG_','USE_EXT_CE_'):
                require(c.get(stem+port)=='FALSE','URAM unsupported selected-input register configuration: '+stem+port)
            for stem in ('IS_RDB_WR_','IS_EN_','IS_RST_'):
                require(c.get(stem+port+'_INVERTED')=="1'b0",'URAM unsupported input inversion: '+stem+port)
            require(c.get('SELF_MASK_'+port)=="11'h7E0",'URAM actual high-address mask changed')
            try:
                value=init(c.get('SELF_ADDR_'+port,''))
                require(int(c.get('MEM.PORT'+port+'.ADDRESS_BEGIN',''))==value*4096 and int(c.get('MEM.PORT'+port+'.ADDRESS_END',''))==value*4096+4095,'URAM native decode span changed')
                if port=='A':decode[i][value]+=1
            except (ValueError,TypeError):require(False,'URAM native decode configuration missing')
        require(c.get('SELF_ADDR_A')==c.get('SELF_ADDR_B') and c.get('IS_CLK_INVERTED')=="1'b0",'URAM A/B decode or clock inversion changed')
        if kind=='FIRST':pred[name]=None;roots.append(name)
        else:
            os=words(row(name,'CAS_IN_ADDR_A[0]').get('driver_cells',''))
            parent=os[0] if len(os)==1 else ''
            pred[name]=parent
            require(parent in identity and identity.get(parent)==i and cfg.get(parent,{}).get('CASCADE_ORDER_A') in ('FIRST','MIDDLE'),'URAM invalid cascade predecessor')
        for port in ('A','B'):
            if kind=='FIRST':
                constant(row(name,'RDB_WR_'+port),'GND' if port=='A' else 'VCC','URAM effective read-A/write-B configuration unresolved')
                for signal in ('RDB_WR','EN'):constant(row(name,'CAS_IN_'+signal+'_'+port),'GND','URAM inactive FIRST cascade input not actual GND')
                en=row(name,'EN_'+port)
                require(bool(set(words(en.get('nets','')))&sources.get('read_enable' if port=='A' else 'write_enable',set())),'URAM effective enable boundary source mismatch')
            elif pred.get(name) in identity:
                for signal in ('RDB_WR','EN'):edge(name,'CAS_IN_'+signal+'_'+port,pred[name],'CAS_OUT_'+signal+'_'+port)
                # Preserve the actual unused direct mode values as measured;
                # effective modes above follow CAS inputs from the root.
                constant(row(name,'RDB_WR_'+port),'VCC','URAM unused direct mode observation changed')
            for bit in range(23):
                direct=row(name,f'ADDR_{port}[{bit}]');cascade=row(name,f'CAS_IN_ADDR_{port}[{bit}]')
                if kind=='FIRST':
                    constant(cascade,'GND','URAM inactive root CAS address not actual GND')
                    require(not words(cascade.get('startpoints','')),'URAM root constant CAS raw startpoints changed')
                    if bit<17:
                        ds=words(direct.get('drivers',''));rs=words(direct.get('driver_refs',''))
                        if port=='A':
                            own=addr.get((i,bit),{}).get('NAME','')+'/Q'
                            require(ds==[own],'URAM root unloaded/missing bit or cross-slice own read-Q mapping')
                        else:
                            expected_write=core_scope+f'/artifact_index_r_reg[{bit}]'+('_rep' if bit<9 else '')+'/Q'
                            require(ds==[expected_write],'URAM root write-address bit source changed')
                        require(len(rs)==1 and isff(rs[0]),'URAM root address actual FF source unresolved')
                        # This is a check on separately recorded raw facts,
                        # not a replacement of native C timing startpoints.
                        require(len(ds)==1 and words(direct.get('startpoints',''))==[ds[0].rsplit('/',1)[0]+'/C'],'URAM root raw FF timing startpoint differs')
                        require(not any(d.rsplit('/',1)[0] in original_names for d in ds),'old core address still drives memory')
                    else:
                        constant(direct,'GND','URAM masked high-address input not actual GND')
                        require(not words(direct.get('startpoints','')),'URAM constant high address raw startpoints changed')
                elif kind in ('MIDDLE','LAST'):
                    require(not words(direct.get('nets','')) and not words(direct.get('drivers','')) and not words(direct.get('driver_refs','')) and words(direct.get('startpoints',''))==[name+f'/ADDR_{port}[{bit}]'],'URAM unselected direct address raw evidence changed')
                    if pred.get(name) in identity:edge(name,f'CAS_IN_ADDR_{port}[{bit}]',pred[name],f'CAS_OUT_ADDR_{port}[{bit}]')
        clock=row(name,'CLK')
        require(bool(set(words(clock.get('nets','')))&sources.get('clock',set())),'URAM CLK differs from selected clock boundary')
        clock_drivers=words(clock.get('drivers',''));ports=words(clock.get('primary_ports',''));directions=words(clock.get('primary_port_directions',''))
        require(len(clock_drivers)==1 or (not clock_drivers and len(ports)==len(directions)==1 and directions==['IN']),'URAM CLK source is not one actual leaf driver or primary input')
    children=collections.defaultdict(list)
    for name,parent in pred.items():
        if parent in identity:children[parent].append(name)
    require(all(len(cs)<=1 for cs in children.values()),'URAM address cascade branches')
    covered=set();chains=[]
    for root in roots:
        chain=[];name=root
        while name in identity and name not in chain:
            chain.append(name);covered.add(name)
            cs=children[name];name=cs[0] if len(cs)==1 else None
        require(name is None,'URAM address cascade cycle/branch')
        require(cfg.get(chain[-1],{}).get('CASCADE_ORDER_A')=='LAST','URAM cascade tail is not LAST')
        require(all(cfg.get(n,{}).get('CASCADE_ORDER_A')=='MIDDLE' for n in chain[1:-1]),'URAM cascade interior is not MIDDLE')
        chains.append(chain)
        for member in chain[1:]:
            for port in ('A','B'):
                for bit in range(23):
                    want=words(row(root,f'ADDR_{port}[{bit}]').get('startpoints','')) if bit<17 else [root+f'/CAS_OUT_ADDR_{port}[{bit}]']
                    require(words(row(member,f'CAS_IN_ADDR_{port}[{bit}]').get('startpoints',''))==want,'URAM cascade raw address ancestry changed')
    require(covered==set(identity),'URAM cascade missing/rootless/cyclic coverage')
    for i in (0,1):
        require(decode[i]==collections.Counter({n:2 for n in range(20)}),'URAM native decode coverage changed')
        require(sorted(len(c) for c in chains if identity[c[0]]==i)==[4,4,8,8,8,8],'URAM actual chain inventory changed')
    return {str(i):sum(identity[r]==i for r in roots) for i in (0,1)}
