# Attention baseline RTL

本目录保存从 HAP Attention v3.1 签核 commit 复制的 RTL。新增 MLP 实验不得直接修改这里的
数值行为；需要改造共享 projection array 时，先建立 bit-exact 对照和独立 run 记录。

