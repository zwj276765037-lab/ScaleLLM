# 修复验证结果

原错误可确定复现。新增4项测试在旧版上产生2个失败和2个错误；修复后26/26通过。除public()外helper AST完全一致。原真实运行stop_attempted=false、reset_attempts=0。

[机器结果](../mock_results.json) · [新测试输出](../mock_stdout.log) · [旧版回归输出](../old_regression_stdout.log)。结果仅证明此软件缺陷修复和模拟保护逻辑通过，不代表管理员维护或GPU硬件恢复成功。
