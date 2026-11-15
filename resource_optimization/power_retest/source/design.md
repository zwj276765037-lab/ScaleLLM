# 全DSP版本七轨功耗重测合同

## 目标和来源

本阶段依据用户2026-11-15授权，重测已发布全DSP VCU118 80 MHz版本。目标bit SHA256为5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7。阶段由本工程角色唯一操作Dell板卡，根代理负责发布文档和GitHub。独立审核者维护source/independent，其余本目录由本工程角色维护。

沿用main 2026-11-02七轨合同和实际main_004源。封存父源码保存在source/legacy_main_004，原始来源SHA保存在parent_source_identity.json。测量VCCINT、VCC1V8、VADJ、VCCINTIO_BRAM、VCC1V2、MGTAVCC、MGTAVTT七条稳压器输出，保留原PMBus寄存器码、QPC、轮转扫描、校准只读值、负电流码和未知传感器时间窗口限制。

## 工作负载和独立参考

采用16个原请求的固定KV128/position127状态，固定三组次序依次为idle/attention/mlp/full、idle/mlp/full/attention、idle/full/attention/mlp。idle、Attention五层L0/8/16/24/31轮转回放和MLP L0各120秒，完整步包含32层A/M、CPU Down、LM head及16槽token原子提交。

参考96df1a5c版本的128轮运行和六条完整捕获作为旧参考身份。新板身份单独绑定5d78519a位流。当前DDR只有此前50轮运行，必须从旧封存256MiB快照实际恢复32层并完整回读。快照来源为Dell旧readonly_inspection_002/kv_snapshot.bin，SHA256 fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8。恢复后重新建立16槽prompt/generated/epoch1/position127状态并执行新bit64命令资格验证，比较16输出token、完整槽位提交、六条选中输入/整段输出和全快照确定性。保留五层有独立历史KV字节、另外27层缺独立历史oracle的原限制。

## 采集和离线验收

先新采60秒只读pilot，按D=max(100ms,1.25*p95)向上10ms取整，G=3D。旧140ms/420ms作为比较基准，实际D/G须记录并在正式前通知主控。共同覆盖、段间gap、负码、窗口边界和时间加权积分规则沿用原合同。缺失BUSY观测仅使相关BUSY覆盖指标为空，完成描述符、字节长度、DONE错误、输出数值和ACK身份断言必须保留。全窗均值只在实际共同覆盖完整时给值。

## 环境、资源及终止

Dell DESKTOP-D3，通过hap-dell连接。本次独立目录D:/ScaleLLM_final_model/dsp_all_power_20261115_001。已有官方PowerTool 2.32.27运行库仅在Dell只读使用，32位PowerShell采集。Windows XDMA Python3.12，数学库各1线程，至多8个现有允许CPU。独占已有.board.lock，任务RSS不超过8GiB，系统可用内存至少2GiB，D盘至少40GiB。监护只管理精确PID和出生时间匹配的本任务进程。

整个阶段、正式workload与正式sampler不设置累计固定墙钟强停。60秒pilot和120秒测量窗口保留为采集设计。保留XDMA单操作5000ms、硬件命令120秒和sampler准备/通信故障超时。配置Flash、主机重启和驱动修改不在本阶段操作中。需要新镜像身份时，只在独占和唯一JTAG目标核验后对确切候选做SRAM编程。

## 交付和收尾

大raw保存在outputs/resource_optimization_power，本目录只保存公开脚本、合同、小型结果、回执和下载索引。KV快照和vendor库不加入Git。完成后真实等待workload和sampler原生退出并记录exitcode，最终核对板卡空闲、句柄关闭、自有进程退出及租约释放。原始证据均生成size/SHA清单并回传，本阶段保留全部失败尝试。
