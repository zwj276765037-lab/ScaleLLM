# E008 缓冲ALIAS细日志修复

原dcc64完整物理实现与top-port获取协议不变。六处非协议必须ALIAS细事件改写独立每point全缓冲sidecar，保留真实operation/event/time/sequence，local mapping成功或失败后统一关闭；原生错误code/options优先保留。top-port实际native BEGIN/END、完整参数/结果、关键阶段及owner进度保持。

只在独立新源码入口实施，不改当前R0061425或原dcc64。原有scope/acquisition/base、原生资格、实际P/origin/宏/资源保护、SLR2 Pblock、完整place→physopt→route及全部全局验收保持。受影响验证只覆盖logging正常/原生异常/日志异常/两者/已存在文件/配置异常；未改部分复用既有审核。准备不代表新原生运行或性能改善，也不授权停止当前进程。
