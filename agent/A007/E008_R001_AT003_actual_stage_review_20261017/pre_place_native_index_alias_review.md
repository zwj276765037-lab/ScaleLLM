# AT003 pre-place：原生端口索引与 alias 日志审核

接受完整端口索引子步骤。使用本次归档的实际 validator 重放全部端口全集、逐端口邻接、完整别名及全部 group 的原生 reciprocal 资格校验：269 个端口、269 个 group、2772 个别名、2170 次原生调用；方向 IN23／OUT70／INOUT176，无 disconnected、多 group 或未知方向。

闭合点／epoch、collector／validator、原始账本身份及输入绑定均独立复核。为遵守审核边界，调用 `validate(..., require_closed=False)`，再逐项补核所有非 DCP 的闭合条件；DCP 内容哈希归属工程，本次没有读取／哈希 DCP。[机器审核](pre_place_native_index_alias_review.json)。

闭合 buffered alias 文件的 167160 条事件序号连续、时间不逆行，每个 BEGIN/END 的操作和 detail 完整配对；mapping code=0、final flush=1。未由日志间隔推定整体性能。

该结论只接受 index／闭合 alias 子步骤，完整有向 cut、时序、全局 pre-place 保护及物理实现仍待后续真实结果。实现继续，无新增门。
