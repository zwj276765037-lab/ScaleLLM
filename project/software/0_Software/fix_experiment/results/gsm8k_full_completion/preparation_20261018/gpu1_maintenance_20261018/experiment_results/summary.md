# GPU1维护helper验证

当前作者[22项CPU/mock](../mock_results.json)全过；旧2249版[A010独立审核](../../protocol/gpu1_maintenance_independent_review_AT001.json)重跑21项并通过额外25项CPU检查。已覆盖默认无动作、外部GPU0计算拒绝、锁/会话/显示别名/保护进程拒绝、stop或reset失败恢复、单次GPU1目标。

实际reset/service/system调用0；没有真实维护结果，也未产生模型或GSM8K资格。代码验证与设备修复验收分开。

新版仅loginctl参数适配；真实非root查询session115取得Scope=session-115.scope，原始stdout/exit/time见[回执](../validation/loginctl_fields_AT001/receipt.json)，没有GPU/service动作。当前源码[新版独立适配复核已签发通过](../../protocol/gpu1_maintenance_loginctl_revision_review_AT001.json)，只覆盖loginctl-only差异及其新证据，不表示真实reset/恢复已验证。
