# E011当前实测结果

AT023已自然native0/nullstop/归属空/监督退出/锁释放：80/80真实clock endpoint、1个实际连通组、12062唯一网段，实际direct alias1；canonical/primary core_clk IN、leaf空。采集3755ms；含网表载入全程318.177695s（5分18秒）。完整segments1/219ms、leaf1/474ms、canonical1/198ms、ports1/113ms；direct80/4ms，batchNAME/CLASS2/149ms。full segments与canonical各1，合计2条带-segments调用，不混报。旧已审首CLK的nets/leaf/primary/direction四字段与新组逐字段完全相同。该3.755s只指时钟采集，不是完整G4/implementation时长。

优化及v2已于01:06:27Z真实应用，48源manifest16f9523c。实际受影响ordinary回归95+33=128 PASS（38.021s/7.737s），另精确8项group/stream CPU9.726s通过复用、A007独立13 decoder/11 v2 AST/闭包及应用/回归核验接受；原测试脚手架失败来源和后续定向replay分别标明，未冒作原日志。

AT024于01:10:47.982557Z实际启动：监督157933/start6185410、leader157934/start6185432、native158026/start6185635，独立SID/PPID1、唯一EDA锁inode169247080由157933持。194 archived inputs内48 runtime全部逐SHA核，原资源阈值/CPU0–7/nice5保持。当前无本次selected graph/snapshot/budget/native终态/G4/place/route或时序成功；TOP01−2.896ns和22049差仍OPEN。

01:21Z本次22唯一原生Reading checkpoint cell/path与原consumed22已独立逐项闭合，23当前metadata=Complete!/100%/refresh0；仅接受读取记录/原生产内容资格，不代表open_run/全图完成。nativeCPU128999ticks、树RSS15.168GiB、available476.56GiB/disk447.09GiB正常；日志已到设置XDC timing约束完成，尚无新snapshot/预算/native终态。

01:55Z实际首overlay apply成功（240B/62c60cb3），绑定native158026/manifest16f/overlay9124；open_run已返回，日志elapsed44:36/CPU1:01:20并实际记录REAL_CLOCK_FAMILIES。当前trace已进入第二次explicit apply，attempt1/2均restore0，第二次尚未成功；没有snapshot/预算/native0/G4。01:56:55资源树RSS20.224GiB/available468.62GiB/disk447.11GiB、nativeCPU412859继续增长。


---
Published: 2026-10-19T01:58:56.661591+00:00
Publication: Paa7c020dd33d483e9036b18871042994
