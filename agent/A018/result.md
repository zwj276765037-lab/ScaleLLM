# A018 本轮实际交付

AT027自然native0终态、194 current/archive、48运行源、13个PID/start退出和EDA锁释放已闭合；已审最终导出checker PASS，恢复综合包已freeze（22依赖实际消费）。[工程结果](../../project/E011_m003_joint_routability_implementation/experiment_results/summary.md)。

AT028于2026-10-19 10:53:51Z真实启动原生INIT→OPT→debug→preplace。实际Vivado484538/start9684039，监督484413/start9683797，原单EDA/CPU/资源保护保持。G4/place/route未开始；后继实质G4依赖A007独立审核。

活动轮次在启动与摘要收尾后结束；detached监督继续，不保持模型轮询或观察器。实际模型/强度未取得独立元数据，不将期望gpt-6.1-sol/xhigh冒充已核实。

本次追加：两类告警限定离线归因完成。DDR纯信息puts沿用既审，11个Pblock顺序告警未证明有效归属丢失；AT027离线反向成员核通过，AT028实际阶段须再核。详细证据在E011 AT028/evidence/AT028_two_warning_classes_one_shot_attribution.json。未运行新EDA/observer、未改48源或停止AT028。

AT028后续已于11:56:29Z自然native1；194来源/17归属身份/锁空闭合。根因是临时native INIT unmanaged registry与持久XPR属性不同。实验内52源显式恢复适配7测试通过，核心48源未改；AT029于12:51:42Z真实启动，native565652/start10391332、监督565520/start10390975、199绑定及原保护核。原INIT继承、不重执行；实际G4/物理仍待。
