# 第32层Attention与MLP纯分支比较

仅3篇预声明诊断文档、299位置，每个纯分支1224704个数值；两分支均在残差相加前测量。不能标成1024篇纯分支比较：全1024缺同口径Attention自由轨迹分支原始统计。

入口见 [最终v3 Python图](pure_branch_comparison_v3.png)、[报告](report_v2.md) 和 [summary.json](summary.json)。纯分支、逐文档、MLP阶段、分开轨迹的4份CSV完整保留。报告副本只将旧v2图链接改到最终v3图，数值不改。

报告/CSV中 AB 是当前与参考完整轨迹；AC固定同一第32层入口比较两种算术；CB保留前31层不同输入、使用参考块。三者有交叉项，不可把AC变化移植为AB因果效应。OUTPUT_ONLY仍保留基础量化、ScaleCode、LUT/SwiGLU、共同出口和Host。

独审JSON在 `independent_review/`。MLP绝对RMSE高于Attention，同时参考RMS更大，而相对L2更低；尺度变化本身不是舍入因果放大的证明。来源/SHA见 [清单](../package_sources.json)。
