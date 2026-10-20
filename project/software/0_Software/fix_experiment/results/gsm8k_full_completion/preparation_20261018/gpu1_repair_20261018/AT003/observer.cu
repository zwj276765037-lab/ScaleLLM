extern "C" __global__ void count_bytes(const unsigned char* data, unsigned long long size, unsigned int expected, unsigned long long* out) {
    unsigned long long count=0, first=~0ULL, set_bytes=0, clear_bytes=0;
    const unsigned char e=(unsigned char)expected;
    const unsigned long long stride=(unsigned long long)gridDim.x*blockDim.x;
    for (unsigned long long i=(unsigned long long)blockIdx.x*blockDim.x+threadIdx.x; i<size; i+=stride) {
        const unsigned char b=data[i];
        if (b!=e) { ++count; if(i<first)first=i; if((b&(~e))!=0)++set_bytes; if((e&(~b))!=0)++clear_bytes; }
    }
    if (count) { atomicAdd(out,count); atomicMin(out+1,first); atomicAdd(out+2,set_bytes); atomicAdd(out+3,clear_bytes); }
}
extern "C" __global__ void fetch_first(const unsigned char* data, unsigned long long* out) {
    if(threadIdx.x==0 && blockIdx.x==0) out[4]=out[0] ? (unsigned long long)data[out[1]] : ~0ULL;
}
