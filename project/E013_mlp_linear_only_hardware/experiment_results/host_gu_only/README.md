# GU-only Host Down与v7后端CPU证据

执行范围：A023独立Host工程，未运行EDA/GPU/板卡；原权重字节、旧Host/runtime/artifact模块和R005冻结输入未改。runtime v7/schema SHA `318cf64064354aed52943fd21909aa8b67f11ca8fb565a37c65441d522d4938a`；生成`scalellm_mlp_gu_only_abi.py`归A022，本交付只读。

## API与实际入口

- `host.scalellm_mlp_gu_only.DownWeights.from_records(c0,c1,meta,layer_id=...)`：原group/tile/half次序、W4有符号nibble、32B metadata低128bit code/高96bit shift/4B零padding，严格大小与只读数组。`from_artifact_records`先按原ArtifactRecord校验实际大小/SHA。
- `down_scalar_oracle(q,meta,weights,rows=...,columns=...)`：独立Python任意精度、每个坐标完整448组×32lane；最多256坐标，避免全shape标量回归。`down_blocked_int64`默认严格16×4096生产输出，blocked matmul后逐group对齐再累加；`prepare_and_run_down`接收实际GU S24字节，经已有冻结SiLU、S32乘Up、H32/S35/A8后执行Down，不重复RMSNorm。D>4,269,834,239拒绝。
- `GuOnlyArtifactManifest.load(path,verify_hashes=True)`：保留原schema2/v5权重ABI及schema3/W4F5布局/身份检查，runtime v7与原工件ABI分离；`down_weights(layer)`实际读文件时再次校验SHA。`verify_hashes=False`仅跳过加载时全目录哈希，不绕过Down读取校验。
- `GuOnlyPipeline(backend,artifacts.down_weights,after_down)`：两cohort/32层任务和不可变Host Down租约；复制GU→匹配ACK→真实backend quiescence→释放FPGA epoch。CPU Down和残差消费者完成后释放Host租约；下一层依赖保持。无硬件Down命令或虚构Down completion。
- `GuOnlyXdmaBackend(session,artifacts,attention_callback=...)`：可执行的真实CSR/XDMA方法绑定。直接调用原`XdmaSession.read32/write32/h2c_write_local/c2h_read_local`，初始化真实身份/Attention ABI/SHARED；仅staging GU两个half和GU metadata，LOAD/COMMIT→epoch→544bit descriptor→START→DONE校验→C2H复制→身份ACK。CSR访问使用控制BAR寄存器偏移；DMA及descriptor中的数据地址使用DDR1 local；原session只加一次`0x80000000`Host aperture。opcode为完整U32的1，reserved Down bases为0。任何已接受操作失败保留租约、pending和只读诊断，禁止继续提交；不自动清错/重置硬件。

应用使用顺序：以原`XdmaSession`上下文打开已有会话；加载严格`GuOnlyArtifactManifest`；提供实际Attention/残差/RMSNorm回调及Down后残差消费者；构造`GuOnlyXdmaBackend`和`GuOnlyPipeline`后调用`run`。本交付不代替应用预装Attention权重、KV/输入/边界数据及Attention回调实现；缺失回调明确拒绝，回调前仍核真实Attention format/ABI。`weight_layout`是已校验工件身份，不伪称存在硬件可读寄存器。

## 实际测试与独立期望

1. [AT_20261024T153221518972Z](AT_20261024T153221518972Z/manifest.json)：26 tests PASS，8.697s，native0。12数值+4原exporter/manifest+8任务租约+2实际GU准备链。原exporter `_write_mlp_tile/pack_w4/pack_mlp_meta`实际生成448组×32列，再独立decode比对；完整16×4096合成shape全部65,536值对独立group-major einsum/floor_divide参考，另224有界坐标用纯Python fullK参考。原exporter和原数学函数源码均在manifest绑定。
2. [AT_20261024T154353319434Z](AT_20261024T154353319434Z/manifest.json)：新增16 backend tests PASS，7.390s，native0。脚本传输的实际寄存器/方法/顺序证据见[trace](AT_20261024T154353319434Z/backend_transport_trace.json)。覆盖v7/Attention身份拒绝、GU-only staging、metadata实际文件hash/size/padding先验校验、两cohort同epoch、U32 opcode/零reserved、ordered admission读、全部DONE身份/计数/错误、复制后ACK、epoch不复用、短H2C/C2H、START SLVERR/无接受证明、timeout/reset_required保留失败owner、Host预取不可变payload；另直接调用原XdmaSession并mock系统pread/pwrite证明4B CSR写和aperture恰加一次。Pipeline→真实新adapter→fake transport组合也已执行，Attention/CPU Down用显式调度fixture。

总计42项CPU tests，分两次上述独立attempt；没有声称42项为同一次运行。旧26项未因backend新增而无故重跑。每次保留命令、退出码、Python3.12.3/NumPy1.26.4、所有源/输入SHA、原始日志和源码快照，输入未变，stop_reason=null。源码当前身份见[delivery_sources.json](delivery_sources.json)。

后端测试后仅修正模块docstring的地址说明（CSR为控制BAR偏移，DMA/descriptor数据地址为DDR1 local），功能代码未变；新源码身份与attempt测试快照的区别已在delivery_sources.json说明，无数学或传输重跑。

完整合成Down939,524,096MAC：strict decode0.303939s，blocked计算1.735678s，独立向量参考1.218973s，224坐标scalar1.689962s；单次无warmup，计算时间不含decode/GU准备/模型I/O。峰值RSS964,664KiB；后端测试113,248KiB。CPU affinity0–7，BLAS/OMP/MKL均1，RSS/地址空间8GiB保护、available底线64GiB；全shape中间数界：|dot|≤65,280、|raw|≤4,244,832,000、|guard|≤17,386,831,872,000、448组和≤7,789,300,678,656,000<2^53，均安全int64。逐group算术右移先于累加，末端half-away>>8并饱和S32。完整输出S32 bytes SHA `eb985d6fa74a10fb7623034cbde4c1798bb80d26f048aff18e2b77b4dcfb4514`。

运行入口（新attempt自动保留）：

```sh
python3 -B project/E013_mlp_linear_only_hardware/experiment_results/host_gu_only/run_cpu_tests.py --pattern 'test_scalellm_mlp_gu_only*.py'
```

## 适用范围

CPU测试的数值与producer均为确定性合成工件。默认exporter位置和已知artifact目录中未发现真实32层W4F5导出，详见[artifact_discovery.json](artifact_discovery.json)；没有整主机穷举或真实模型通过的声明。32层任务测试证明调度/命令数/租约，不能证明真实32层数值或吞吐。fake transport只验证Host方法/地址/顺序/错误策略，不能证明RTL、PCIe设备、真实AXI响应、SHARED并发、板级或PPL/ACC。真实硬件测试仍由A022独立执行，Host完整系统不阻塞硬件验收。
