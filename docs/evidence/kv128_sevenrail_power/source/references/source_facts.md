# 官方来源核查：传感器更新、格式与限制

核查日期：2026-11-02。以下资料通过web工具读取了官方PDF的文本。PDF直接下载四次均超时，见[下载回执](manifest.json)；没有本地完整PDF或其哈希，不宣称已经归档。网页截图接口亦未成功，因此MAX20751时间数值只称表列值，不将列位置未复核的值当作保证最大值。

| 来源与版本 | 已核查位置 | 支持的事实与限制 |
|---|---|---|
| [MAX20751 data sheet](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX20751.pdf), 19-7080 Rev2, 3/15 | Electrical Characteristics, printed pp.6–7 | IOUT更新512µs、分辨率0.5A；VOUT和POUT更新3ms，分辨率5mV和2W。未取得内部平均核/最大年龄的可用说明，不能由更新值推导严格物理测量窗口。文档高负载特定条件误差不直接移用至本轮轻载。 |
| [MAX20751 PMBus implementation guide](https://www.analog.com/media/en/technical-documentation/user-guides/max20751-pmbus-implementation-guide.pdf), UG5941 Rev2, 12/16 | Table9 pp.4–5；§7.4/Eq.28、§7.5 p.14 | mode0x20、READ_VOUT为VR12 VID：V=0.25+(word−1)/200；IOUT Linear11指数−1，POUT指数+1。READ_WORD低字节在先。没有找到平均窗口数值。 |
| [MAX15301 PMBus command set guide](https://www.analog.com/media/en/technical-documentation/user-guides/max15301-pmbus-command-set-users-guide.pdf), Rev1, 10/14 | VOUT_MODE p.10；Telemetry p.30–32；Calibration p.34 | VOUT mode0x14、unsigned mantissa/4096；IOUT Linear11、8-bit底层测量且滤波/抽取，需电流校准。完整命令集未列0x96/READ_POUT。READ_DUTY_CYCLE的256PWM周期平均不能移用IOUT；读出IOUT已应用内部校准。 |
| [MAX15301 data sheet](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX15301.pdf), 19-6267 Rev4, 11/13 | Regulation and Monitoring p.12；Input feed-forward p.15；Table7 pp.20–22 | 确认连续监测但未建立VOUT/IOUT遥测更新或平均窗数值；INSNS每4µs针对输入路径；命令表未列0x96。 |
| [VCU118 UG1224](https://docs.amd.com/v/u/en-US/ug1224-vcu118-eval-bd) | 本轮复用仓库docs/POWER_MEASUREMENT与既有provenance所核查Tables3-33/3-34 | 七轨地址和器件对应；本轮未重新下载板手册，不宣称新校准或整板测量。 |

“未找到”限定为上述官方资料及已读章节/命令表，不等于厂商绝无其他内部文档。公开更新值、板级外部滤波、内部数字平均和主机API返回延迟是不同概念。主测前保存本轮可知/未知项和实测读延迟，再固定采样周期。

简短原文核查片段：MAX20751数据手册p.6为“Update Rate of Reported Output Current”，同一行数值512µs；MAX15301命令指南p.30为“READ_IOUT data is filtered and decimated”。MAX15301的VOUT_MODE原始章节明确0x14和指数−12；用这些具体条目约束解码，不靠历史数值反推比例。
