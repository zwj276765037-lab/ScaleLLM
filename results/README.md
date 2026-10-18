# ScaleLLM Results 目录结构

当前任务：[M003联合可布线改造](../mission/M003_joint_routability_closure/contract.md)，[定义与状态](missions/M003_summary.md)。工程尚未启动；最新实际结果仍是[E008自然布线失败](../project/E008_m002_exact_hotspot_offload_implementation/experiment_results/summary.md)。

**最后更新：** 2026-10-14

---

## 目录组织原则

```
results/
├─ YYYY-MM-DD_event_name/          # 按日期+事件组织
│  └─ 该日期的所有相关文档
│
├─ analysis/                        # 技术分析报告
│  ├─ performance/                  # 性能分析
│  ├─ timing/                       # 时序分析
│  └─ architecture/                 # 架构分析
│
├─ verification/                    # 验证报告
│  ├─ functional/                   # 功能验证
│  ├─ alignment/                    # 硬件-软件对齐
│  └─ simulation/                   # 仿真结果
│
├─ missions/                        # Mission 执行结果
│  ├─ M001_summary.md              # M001 最终汇总
│  └─ M00X_summary.md              # 其他 mission
│
└─ reviews/                         # 审核记录
   └─ review_YYYY-MM-DD.md
```

---

## 当前文档索引

### 2026-10-14 项目接管

**路径：** `2026-10-14_project_takeover/`

| 文档 | 描述 |
|---|---|
| `PROJECT_STATUS_2026-10-14.txt` | 项目现状快照 |
| `IMMEDIATE_ACTION_PLAN.md` | 立即行动计划 |

### 技术分析

**路径：** `analysis/`

| 文档 | 类别 | 描述 |
|---|---|---|
| `DSP_utilization_corrected_analysis.md` | 性能 | DSP 算力验证（5451 DSP） |
| `DDR_separation_architecture_analysis.md` | 架构 | DDR 双通道分离方案 |
| `hardware_functional_status_and_timing_analysis.md` | 时序 | 布线时序诊断与修复方案 |

### 验证报告

**路径：** `verification/`

| 文档 | 类别 | 描述 |
|---|---|---|
| `alignment_verification_2026-10-14.md` | 对齐 | 硬件-软件对齐完整验证 |

### Mission 结果

**路径：** `missions/`

| 文档 | Mission | 状态 |
|---|---|---|
| `M001_summary.md` | 工程整理 | ✅ 完成 |

---

## 文档命名规范

### 按日期命名
```
YYYY-MM-DD_event_description.md
例如: 2026-10-14_project_takeover_summary.md
```

### 按类型命名
```
category_topic_version.md
例如: analysis_ddr_performance_v1.md
```

### Mission 结果
```
M00X_summary.md
例如: M002_summary.md
```

---

## 快速导航

### 查看最新项目状态
```bash
cat results/2026-10-14_project_takeover/PROJECT_STATUS_2026-10-14.txt
```

### 查看技术分析
```bash
ls results/analysis/
```

### 查看验证报告
```bash
ls results/verification/
```

---

## 维护指南

**添加新文档时：**
1. 确定文档类型（分析/验证/Mission结果）
2. 放入对应目录
3. 更新本 README.md 的索引
4. 如果是重大事件，创建日期目录

**清理旧文档时：**
1. 归档到 `archive/YYYY/` 目录
2. 更新索引，标记为已归档
3. 保留至少 6 个月

---

**维护者：** Project Team  
**最后审核：** 2026-10-14
