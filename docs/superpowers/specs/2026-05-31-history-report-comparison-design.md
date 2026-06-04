# 历史评测报告筛选与对比设计

## 背景

当前历史评测页主要按 run 展示整体通过率、模型、场景数和详情入口。这个视角适合回看单次评测，但不足以回答两个核心问题：

- 业务侧：哪些场景风险最高，失败原因是什么，应该反馈给业务流程、话术或约束设计的哪一部分。
- 训练侧：同一场景下不同模型表现差异在哪里，哪些失败样本可以沉淀为训练或回归数据。

第一版目标是增加可扩展的历史对比能力，同时保证所有结论来自真实评测产物，不做相似场景猜测、不补造缺失数据。

## 用户目标

支持在历史评测报告中筛选和对比：

- 同一场景下不同模型的表现。
- 同一模型在不同场景下的表现。
- 当前筛选结果中的主要失败原因汇总。
- 从对比结果跳转到具体 run 详情，查看对话轨迹和失败证据链。

## 设计选择

采用新增专门对比接口的方案，而不是让历史列表接口承载所有分析数据。

接口：

```text
GET /api/runs/comparison
```

原因：

- 历史列表继续保持轻量，只负责 run 级别摘要。
- 对比接口可以独立扩展趋势、导出、人工场景映射、失败原因聚合等能力。
- 前端不需要逐个拉取 run 详情，避免历史数据多时出现大量请求。
- 数据口径集中在后端，方便测试和复用。

## 数据口径

第一版严格按真实字段计算：

- 同一场景只按 `scenario_id` 完全一致判断。
- 同一模型只按 `model_name` 完全一致判断。
- 分数来自 `evaluation_results.json` 和 evidence 的 `max_score`。
- 场景原始通过率按 `total_score / possible_score * 100` 计算。
- 展示通过率使用 `min(100, raw_pass_rate)`，避免把异常分数展示成正常百分比。
- 当 `total_score > possible_score` 时返回 `score_anomaly: true`，前端展示为数据异常，而不是正常高分。
- 失败原因来自真实 `failure_summary` 或 evaluation evidence，不做模型生成式总结。
- 当某个 run 缺少场景、证据或报告产物时，接口跳过不完整项或返回空数组，并在前端显示“暂无可用证据”。

不做：

- 不自动合并相似场景。
- 不推断缺失模型名。
- 不生成趋势预测。
- 不用 LLM 编写失败分类。
- 不把没有证据的数据展示成结论。

## 后端接口

`GET /api/runs/comparison` 返回面向分析的扁平数据和聚合数据。

响应结构：

```json
{
  "runs": [
    {
      "run_id": "run_xxx",
      "task_name": "任务名",
      "task_goal": "任务目标",
      "model_name": "model-a",
      "updated_at": 1710000000,
      "scenario_count": 3,
      "pass_rate": 64.2
    }
  ],
  "scenario_rows": [
    {
      "run_id": "run_xxx",
      "model_name": "model-a",
      "scenario_id": "scenario_001",
      "score": 112,
      "possible_score": 170,
      "raw_pass_rate": 65.9,
      "pass_rate": 65.9,
      "score_anomaly": false,
      "status": "partial",
      "critical_failure_count": 1,
      "updated_at": 1710000000
    }
  ],
  "failure_reasons": [
    {
      "key": "order_confirmation",
      "label": "订单确认失败",
      "count": 3,
      "scenario_ids": ["scenario_001"],
      "model_names": ["model-a", "model-b"],
      "run_ids": ["run_xxx"],
      "examples": [
        {
          "run_id": "run_xxx",
          "scenario_id": "scenario_001",
          "model_name": "model-a",
          "reason": "未确认订单金额和配送地址",
          "rubric_item_id": "confirm_order_details"
        }
      ]
    }
  ],
  "filters": {
    "model_names": ["model-a", "model-b"],
    "scenario_ids": ["scenario_001", "scenario_002"],
    "task_names": ["任务名"]
  }
}
```

失败原因聚合规则：

- 优先使用 `rubric_item_id` 作为聚合 key。
- 展示 label 时优先使用 evidence 的 `expected_behavior`，否则使用 `rubric_item_id`。
- 每个原因最多返回少量 examples，避免响应过大。
- count 统计当前全量历史中的真实出现次数；前端筛选后可在本地二次过滤。

## 前端交互

历史评测页保留原有 run 表格，并新增“对比分析”区域。

筛选区：

- 关键词搜索：沿用现有 run 搜索。
- 模型筛选：来自接口 `filters.model_names`。
- 场景筛选：来自接口 `filters.scenario_ids`。
- 对比模式：
  - 同一场景不同模型。
  - 同一模型不同场景。

对比区：

- 同一场景不同模型：
  - 用户选择一个 `scenario_id`。
  - 表格按模型/run 展示通过率、得分、关键失败数、保存时间、详情入口。
  - 可按通过率排序。

- 同一模型不同场景：
  - 用户选择一个 `model_name`。
  - 表格按场景/run 展示通过率、得分、关键失败数、保存时间、详情入口。
  - 可快速定位该模型最薄弱的场景。

失败原因汇总区：

- 基于当前筛选后的 rows 和接口返回的真实 failure reasons 展示。
- 显示失败原因、出现次数、涉及模型数、涉及场景数、示例 run。
- 点击示例 run 跳转到报告详情页。
- 没有失败证据时显示“当前筛选结果暂无失败证据”。

## 可视化边界

第一版以筛选、表格和失败原因汇总为主，不做复杂 BI。

可以保留轻量视觉辅助：

- 对比表中使用进度条展示通过率。
- 失败原因使用紧凑列表或标签展示。
- 低于阈值的通过率标红或使用风险标签。

不新增复杂趋势图，避免在数据量不足时制造误导。

## 错误处理

- 对比接口读取某个 run 失败时跳过该 run，不影响其他历史记录。
- 如果所有 run 都不可用，返回空数组，前端展示空状态。
- 如果 selected model/scenario 在当前数据中不存在，前端清空选择并提示暂无数据。
- 缺失 `possible_score` 时通过率为 0，并标记为不可用口径，不展示成有效表现。

## 测试

后端测试：

- `/api/runs/comparison` 返回 run 摘要、scenario rows、filters。
- 同一场景不同模型的数据来自真实 `scenario_id`。
- 原始通过率按真实分母计算；展示通过率不超过 100；原始评分超过分母时返回 `score_anomaly: true`。
- 失败原因按 `rubric_item_id` 聚合，examples 指向真实 run/scenario/model。
- 不完整 run 不导致接口整体失败。

前端测试：

- 历史页调用 `getRunComparison`。
- 页面包含模型筛选、场景筛选、对比模式切换。
- 同一场景不同模型模式使用 `scenario_id` 过滤。
- 同一模型不同场景模式使用 `model_name` 过滤。
- 失败原因汇总基于当前筛选结果显示，并提供 run 详情链接。

## 后续扩展

后续可以在同一接口或新增参数上扩展：

- 人工维护的场景映射表，用于跨批次对齐相似场景。
- 时间趋势和模型版本趋势。
- 导出 CSV/JSON，供训练侧沉淀样本。
- 失败原因标准化词表。
- 对比快照保存，便于报告给业务。
