"""Reviewed DDR-local layout; GU weight addresses remain RTL canonical."""
from dataclasses import dataclass

APERTURE=0x80000000
ATTENTION_HALF=0x01400000
ATTENTION_META=0x00280000
GU_HALF=0x01c00000
GU_META=0x00700000


@dataclass(frozen=True)
class Span:
    name:str
    channel:int
    address:int
    size:int
    alignment:int=32
    def __post_init__(self):
        if self.channel not in (0,1) or min(self.address,self.size)<0 or self.size==0 or self.address+self.size>APERTURE or self.address%self.alignment:raise ValueError('Invalid resident span: '+repr(self))


def layer_spans(layer):
    if type(layer)is not int or not 0<=layer<32:raise ValueError('Layer must be0..31')
    return {
        'attention_c0':Span('attention_c0',0,layer*0x02800000,ATTENTION_HALF,1024),
        'attention_c1':Span('attention_c1',0,layer*0x02800000+ATTENTION_HALF,ATTENTION_HALF,1024),
        'attention_meta':Span('attention_meta',0,0x50000000+layer*ATTENTION_META,ATTENTION_META),
        'mlp_gate_meta':Span('mlp_gate_meta',1,0x20000000+layer*GU_META,GU_META),
    }


def static_spans():
    spans=[span for layer in range(32) for span in layer_spans(layer).values()]
    spans += [Span('rope',0,0x57000000,8192),Span('GU canonical c0',1,0,GU_HALF,1024),Span('GU canonical c1',1,GU_HALF,GU_HALF,1024)]
    for slot in range(6):
        spans += [Span('A input%d'%slot,0,0x56000000+slot*0x100000,196608),Span('A output%d'%slot,0,0x56080000+slot*0x100000,196608),Span('GU input%d'%slot,1,0x10000000+slot*0x800000,73728),Span('GU output%d'%slot,1,0x10100000+slot*0x800000,1376256)]
    for i,left in enumerate(spans):
        for right in spans[i+1:]:
            if left.channel==right.channel and max(left.address,right.address)<min(left.address+left.size,right.address+right.size):raise ValueError('Overlapping reviewed spans: '+repr((left,right)))
    return spans


def attention_bases(layer,cohort):
    if cohort not in (0,1):raise ValueError('Two real cohorts required')
    spans=layer_spans(layer);slot=3*cohort
    return {'c0':spans['attention_c0'].address,'c1':spans['attention_c1'].address,'meta':spans['attention_meta'].address,'rope':0x57000000,'input':0x56000000+slot*0x100000,'output':0x56080000+slot*0x100000,'buffer':slot}


static_spans()
