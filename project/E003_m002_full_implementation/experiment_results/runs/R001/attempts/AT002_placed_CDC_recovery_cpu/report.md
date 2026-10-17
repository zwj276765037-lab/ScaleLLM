# R001/AT002：closed-place恢复准备与CPU核验

execution_state: completed；verdict: PASS（CPU/来源/恢复入口范围）。

最终实际运行150项检查全部通过（129原回归+21新增，30.997s），见[cpu_tests_final.log](cpu_tests_final.log)。新增范围含真实两条DDR1 AUX代表源、精确8行/双源/四级链、错clock/type/target/stage及额外同cone代表拒绝；跨PYTHONHASHSEED1/2/3输出一致；native place非0/不符失败/变DCP或活进程声明拒绝；fresh live guard→完整新place POST→仅独立physopt顺序、历史OPT/debug/place回执分离；旧/新同名archive隔离、旧source篡改拒绝；place/route两次真实隔离CPU子进程自然退出与资源回执（native7和0），均没有wall/no-output停止。原6项owned-process保护回归复用同次实测。

真实AT001完整source资格PASS，[CPU父链](recovery_parent.json)明确physical_post_complete=false。实际worker入口准备在原339输入/45 DCP来源上完成，197新输入、112项旧闭合source独立核验，见[actual_worker_entry_preflight.json](actual_worker_entry_preflight.json)；在原生Vivado调用前明确阻断，未发EDA。新/旧归档不会按同名误换版本。

修复仅窄化报告代表源识别与补缺阶段，不改RTL/XDC/时钟/策略。原AT001错误、原place回执和DCP保持原路径。生产5文件在独占空闲lane锁下安装，源/前版/安装hash见[installation.json](installation.json)，最终源码冻结[validated_sources.sha256](validated_sources.sha256)。初次测试导入配置错误、初次候选fanout模型列表无语义顺序错误日志保留；最终版本已全部回归。

新启动器run_m002_no_wall.py验证补充指令SHA17acf…，不调用budget，不含固定wall/global/no-output终止；保留单lane、CPU0–7/nice5、192GiB tree RSS、48GiB MemAvailable连续30s、30GiB disk。原E002运行器和profile默认保留。

实际后继：[R002/AT002](../../../R002/attempts/AT002_closed_place_POST_physopt/started.json)。本CPU结果不代表新POST、物理完成、时序通过、正式reset/CDC安全或用户最终验收。全链driver [continue_full_implementation.py](continue_full_implementation.py)仅在新physopt真实成功父链通过后自动启动同no-wall R003 route。
