# GPU1维护helper源码

Owner A012，M004/SM020，唯一写入此新目录。用户已授权物理greeter退出、仅GPU1 reset及复测，不含重启主机/系统驱动。父因sudo需要密码而委托可审核管理员helper。

[gpu1_maintenance.py](../gpu1_maintenance.py) SHA256 `3d12ec648dd587bc1dc160c04f102abe49b1a679e3fcbcb81c456a48b21f23fa`；固定GPU1 UUID、内核/NVML/executable哈希、双卡原锁、客户端及LightDM/session/cgroup保护；默认check，--execute才允许单次目标reset，finally恢复原active LightDM。[README](../README.md)含准确命令及停止边界。

本机loginctl适配：仅由原逗号字段改为每字段独立--property。旧2249版保全versions/2249afac，不覆盖旧失败check。
