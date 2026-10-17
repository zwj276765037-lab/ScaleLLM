# E006 R005：候选完整有向边界源码准备

本入口适用 `candidate_directed_cut_v1`。仅用于同一 E005 physopt DCP 的 C01/C02 定向边界与 cap16 max/min 比较，资源、热点及失败样本按已闭合原始身份复用。旧 R004 固定源码/产物和 E008 b59 包保持。

源码准备、CPU mock 或 manifest 冻结均不代表原生资格、新运行启动、候选选定、时序收敛或完成 implementation。E008 新入口另存于 `E008_entry/`，拥有独立后续准备清单，本 R005 包先独立交付。

## 覆盖与原生资格

- 每图重新取得实际 RAW/S/P、本地 native leaf owners/pins，保留 DSP children、root 外实际 P copy、RAW-only 常量、nonleaf 与 disconnected。
- 本地 pin→native net→全部 segments/aliases 首先闭合；原生 pin class DIRECTION/IS_LEAF schema 不获资格时自然失败，不自动请求百万 leaf 回退。
- 原生全 segments 的非 IN 角色库存及全部 top ports 证明唯一外部 driver 后，保留全部候选/RAW关联 leaf、driver/top，省略组外普通 peer IN leaf。
- 其他分支完整枚举全部 native leaf；回退失败不形成通过结论。
- 缩减网明确写 `outside_peer_leaf_loads=NOT_ENUMERATED`、`full_native_leaf_count=NOT_MEASURED` 和 `full_net_endpoint_coverage=false`。有向完整、本地覆盖、角色资格、整网覆盖分开核验。
- 保留本地所有连接、角色查询完整命令/响应、真实 alias 参数、actual owner REF/physical mapping、保留端点和完整方向时序预期集合。
- 时序在完整未改图上查询，max/min 各 cap16/nworst1；全局时序签核及全热点 UNION 整网恢复不属于本次诊断结果。

## 运行与前置收尾

`launch_detached.py` 与 `run_directed_attribution.py` 均要求真实 `--attempt`、`--report`、`--authorization`。不自动排队，也不自动终止旧任务。实际 EDA 启动必须满足：

1. 最终 `prepared_source_manifest.json` 中源/CPU/外部身份实际一致。
2. Root 保存真实执行 binding：`execution_authorized=true`、`decision=readonly_two_candidate_directed_cut`、实际 `scope_revision`、实际 `prepared_source_manifest`、R004 的 `prior_terminal_status` 与 `prior_terminal_facts` 身份。
3. 原 R004 自然终态，或另一次新用户明确停止例外且实际 supervisor/PID/start、144 输入、DCP、固定源码和锁全部收尾。受控停止时另绑定 `controlled_stop_evidence`。历史 R001 许可不得复用。
4. 单 EDA 非阻塞锁、CPU0–7/nice5/max8、树 RSS192 GiB、可用内存48 GiB持续30秒、磁盘30 GiB保护。正常进程无墙钟/无输出强停。

`controlled_stop_R004.py --authorization <实际新停止binding>` 默认仅只读预检；只有附加 `--execute` 且所有绑定有效才使用 pidfd 向精确现有 supervisor 1253852/start930758582 发送一次 SIGTERM。旧 supervisor 自有 handler 负责进程树收尾、输入核查和释放锁；此入口不直接向 Vivado 发信号。停止 binding 必须包含：

- `execution_authorized=true`
- `approval_kind=user_explicit_controlled_stop`
- `authorized_stop_attempt=<当前R004绝对attempt路径>`
- `decision_evidence=<实际本次用户决定文件identity>`
- `scope_revision=<实际范围修订identity>`
- `prepared_source_manifest=<实际最终manifest identity>`

这里只准备可核查机制，没有生成用户授权、没有发送信号。停止后运行现有 `agent/A006/E006_exact_candidates_capture/capture_terminal.py` 做真实闭合审计，再按实际授权启动新尝试。
