# Attention baseline provenance

新实验从以下已签核基线分支建立：

```text
repository commit = e3cbfa9900417782818ae7da1816fb99c30bb8c2
board format       = 0x48384103
ABI version        = 0x00010001
core clock         = 150 MHz
active array       = 8 rows x 16 columns, group32, II=2
useful peak        = 614.4 GOPS
bitstream SHA256   = cb7452b519c7757b2d96afa9934a6651b57a3e1df05428cd95c5641b1548ed26
post-route WNS/WHS = +0.019 ns / +0.005 ns
```

复制到 `rtl/attention/` 的文件只作为新综合树中的 baseline。父目录 `HAP_new` 保持可回退，
Attention+MLP 实验不得覆盖原 bitstream、DCP、report 或 board runtime。

