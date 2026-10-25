"""One I/O owner, counters and timing; CPU workers never receive this object."""
import threading
import time


class MeasuredSession:
    def __init__(self,raw,evidence):
        self.raw,self.evidence=raw,evidence;self.owner=threading.get_ident();self.phase='startup';self.events=[];self.totals={}
    def __getattr__(self,name):return getattr(self.raw,name)
    def call(self,kind,fn,details,byte_count):
        if threading.get_ident()!=self.owner:raise RuntimeError('Only the single I/O owner may access FPGA')
        started=time.perf_counter()
        try:result=fn()
        except BaseException as error:
            self.events.append(dict(kind=kind,phase=self.phase,started_s=started,finished_s=time.perf_counter(),error=repr(error),**details));self.save();raise
        end=time.perf_counter();key=self.phase+'/'+kind
        total=self.totals.setdefault(key,{'calls':0,'bytes':0,'seconds':0.0});total['calls']+=1;total['bytes']+=byte_count;total['seconds']+=end-started
        if kind in ('h2c','c2h'):self.events.append(dict(kind=kind,phase=self.phase,started_s=started,finished_s=end,bytes=byte_count,**details))
        return result
    def read32(self,address):return self.call('csr_read',lambda:self.raw.read32(address),{'address':address},4)
    def write32(self,address,value):return self.call('csr_write',lambda:self.raw.write32(address,value),{'address':address,'value':value},4)
    def h2c_write_local(self,channel,data,address,chunk):return self.call('h2c',lambda:self.raw.h2c_write_local(channel,data,address,chunk),{'channel':channel,'local_address':address},len(data))
    def c2h_read_local(self,channel,size,address,chunk):return self.call('c2h',lambda:self.raw.c2h_read_local(channel,size,address,chunk),{'channel':channel,'local_address':address},size)
    def save(self):self.evidence.replace_json('transfer_metrics.json',{'totals':self.totals,'dma_events':self.events,'single_io_owner':True,'transport_lock':'original synchronous per operation; no claim of simultaneous PCIe calls'})
