# E011当前实测结果

AT023已自然native0/nullstop/归属空/监督退出/锁释放：80/80真实clock endpoint、1个实际连通组、12062唯一网段，实际direct alias1；canonical/primary core_clk IN、leaf空。采集3755ms；含网表载入全程318.177695s（5分18秒）。完整segments1/219ms、leaf1/474ms、canonical1/198ms、ports1/113ms；direct80/4ms，batchNAME/CLASS2/149ms。full segments与canonical各1，合计2条带-segments调用，不混报。旧已审首CLK的nets/leaf/primary/direction四字段与新组逐字段完全相同。该3.755s只指时钟采集，不是完整G4/implementation时长。

优化及v2已于01:06:27Z真实应用，48源manifest16f9523c。实际受影响ordinary回归95+33=128 PASS（38.021s/7.737s），另精确8项group/stream CPU9.726s通过复用、A007独立13 decoder/11 v2 AST/闭包及应用/回归核验接受；原测试脚手架失败来源和后续定向replay分别标明，未冒作原日志。

AT024于01:10:47.982557Z实际启动：监督157933/start6185410、leader157934/start6185432、native158026/start6185635，独立SID/PPID1、唯一EDA锁inode169247080由157933持。194 archived inputs内48 runtime全部逐SHA核，原资源阈值/CPU0–7/nice5保持。当前无本次selected graph/snapshot/budget/native终态/G4/place/route或时序成功；TOP01−2.896ns和22049差仍OPEN。


---
Published: 2026-10-19T01:13:21.301851+00:00
Publication: P1b7d6c830d72416a8c7bc18baeda98d8
