# E011：M003联合可布线版本（用户暂停）

最高优先为2026-10-18用户“需要先中断了 因为服务器需要重启”。已受控停止；禁止自动新EDA、重试或恢复，等待用户新的明确继续指令。Root维护全局pause与mission重启handoff。

G2 4424c426冻结M2（81 CE组、head/tail各6560 FF）+A3（40+40 URAM、2×81920×128、34自身反馈地址FF）+C-P1（原C01 hard-SLR2/25保护及旧80边界）。算法/ABI/core100MHz/UI200MHz/双DDR不变。当前45源manifest151e4f11，3RTL未改；v3仅入口适配。当前payload direct-child选择器实际不适用，不能原样重跑冒充资格。

恢复原23/22新综合网表只允许同源内容闭合；原AT003外层失败1保持，不使用旧基线DCP。原单EDA/CPU0–7/nice5/max8/synth1、RSS192GiB/available48GiB30s/disk30GiB与禁区保持。当前用户暂停覆盖此前连续推进授权。

---
Published: 2026-10-18T07:48:23.091152+00:00
Publication: P922f8ed5536047698e7775e35d50e494
