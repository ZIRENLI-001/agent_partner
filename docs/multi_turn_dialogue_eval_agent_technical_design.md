# 复杂指令多轮对话评测系统技术方案

## 1. 技术目标

本技术方案对应 `multi_turn_dialogue_eval_agent_proposal.md`，聚焦比赛 MVP 的可实现路径。

系统目标：

- 输入已有任务指令。
- 自动生成用户模拟场景。
- 驱动待测对话模型完成多轮对话。
- 自动评估模型是否遵循任务指令。
- 输出可解释、可量化的评测报告。

该系统可以使用多个 LLM 模块协作实现，但不把“多 Agent 平台”作为核心目标。核心交付是用户模拟器和自动评测报告。

## 2. MVP 架构

```text
任务指令文件
   |
   v
InstructionParser
   |
   v
TaskSpec + RubricSpec
   |
   v
ScenarioGenerator
   |
   v
ScenarioSet
   |
   v
DialogueRunner
   |
   v
DialogueTrace
   |
   v
RuleEvaluator + JudgeEvaluator
   |
   v
EvaluationResult
   |
   v
ReportWriter
```

模块说明：

| 模块 | 作用 |
| --- | --- |
| `InstructionParser` | 将原始任务指令拆成结构化任务规格 |
| `ScenarioGenerator` | 根据任务流程和异常分支生成用户模拟场景 |
| `UserSimulator` | 根据场景和对话历史生成下一轮用户输入 |
| `DialogueRunner` | 控制用户模拟器和待测模型进行多轮对话 |
| `RuleEvaluator` | 校验硬约束和可程序化规则 |
| `JudgeEvaluator` | 判断语义类指令遵循结果 |
| `ReportWriter` | 输出量化分数、证据链和报告 |

## 3. 核心数据结构

### 3.1 TaskSpec

`TaskSpec` 表示任务指令的结构化结果。

```json
{
  "task_id": "task_001",
  "task_name": "飞毛腿骑手合同生效通知",
  "role": "美团外卖骑手站长",
  "target_user": "骑手",
  "task_goal": "通知骑手飞毛腿合同今日生效，并提醒完成配送任务",
  "opening_line": "你好，请问是${rider_name}吗？我是站长。",
  "required_steps": [
    {
      "id": "step_1",
      "text": "告知骑手今天飞毛腿合同已生效",
      "required": true
    },
    {
      "id": "step_2",
      "text": "询问骑手是否可以开始配送",
      "required": true
    },
    {
      "id": "step_3",
      "text": "说明合同单量和连续配送要求",
      "required": true
    }
  ],
  "constraints": [
    {
      "id": "constraint_1",
      "type": "max_length",
      "value": 30,
      "description": "每次回复约30字以内"
    },
    {
      "id": "constraint_2",
      "type": "tone",
      "description": "保持自然电话口语"
    }
  ],
  "faq": [
    {
      "intent": "退出飞毛腿",
      "expected_answer": "前一天 Z 点前在 App 的飞毛腿报名中取消，次日生效"
    }
  ],
  "edge_cases": [
    {
      "id": "edge_1",
      "trigger": "骑手表示不想配送",
      "expected_behavior": "尽量挽留；若坚持无法配送，安慰后结束"
    },
    {
      "id": "edge_2",
      "trigger": "骑手问超出职责范围的问题",
      "expected_behavior": "说明向同事确认后再回电"
    }
  ],
  "forbidden_actions": [
    "承诺额外奖励",
    "对超出职责范围问题直接下结论"
  ]
}
```

### 3.2 RubricSpec

`RubricSpec` 表示可评测项。

```json
{
  "rubric_id": "rubric_task_001",
  "items": [
    {
      "id": "r1",
      "dimension": "task_completion",
      "criterion": "是否告知合同今日生效",
      "source": "Call Flow 第1步",
      "check_type": "semantic",
      "weight": 8
    },
    {
      "id": "r2",
      "dimension": "constraint_adherence",
      "criterion": "单轮回复是否约30字以内",
      "source": "Constraints",
      "check_type": "rule",
      "weight": 5
    },
    {
      "id": "r3",
      "dimension": "boundary",
      "criterion": "是否避免承诺额外奖励",
      "source": "Knowledge Points / Constraints",
      "check_type": "rule_and_semantic",
      "weight": 8,
      "critical": true
    }
  ]
}
```

### 3.3 Scenario

`Scenario` 表示一条用户模拟测试场景。

```json
{
  "scenario_id": "scenario_reward_question",
  "task_id": "task_001",
  "user_profile": {
    "role": "骑手",
    "attitude": "愿意沟通但关注收益",
    "background": "已报名飞毛腿，但不清楚奖励规则"
  },
  "coverage_targets": [
    "contract_active",
    "daily_order_requirement",
    "reward_question",
    "boundary_no_extra_promise"
  ],
  "initial_user_intent": "询问飞毛腿是否有额外奖励",
  "expected_test_focus": "模型是否准确回答奖励问题且不额外承诺"
}
```

### 3.4 DialogueTrace

`DialogueTrace` 记录完整测试轨迹。

```json
{
  "trace_id": "trace_001",
  "task_id": "task_001",
  "scenario_id": "scenario_reward_question",
  "turns": [
    {
      "turn_id": 1,
      "speaker": "assistant",
      "content": "你好，请问是王师傅吗？我是站长。"
    },
    {
      "turn_id": 2,
      "speaker": "user",
      "content": "是我，飞毛腿今天有额外奖励吗？"
    }
  ],
  "termination_reason": "task_completed"
}
```

### 3.5 EvaluationResult

`EvaluationResult` 保存评分和解释。

```json
{
  "trace_id": "trace_001",
  "total_score": 86,
  "dimension_scores": {
    "task_completion": 24,
    "flow_adherence": 18,
    "constraint_adherence": 17,
    "faq_accuracy": 9,
    "exception_handling": 10,
    "naturalness": 4,
    "boundary": 4
  },
  "evidence": [
    {
      "rubric_item_id": "r3",
      "verdict": "pass",
      "source": "Knowledge Points 中关于奖励规则的描述",
      "turn_ids": [4],
      "reason": "模型只说明指令中给出的奖励规则，没有承诺额外奖励"
    }
  ],
  "critical_failures": []
}
```

## 4. 任务指令解析

MVP 中，指令解析可以采用“LLM 解析 + 人工可检查”的方式。

流程：

```text
原始任务指令
  -> LLM 抽取 TaskSpec
  -> LLM 生成 RubricSpec
  -> 结构校验
  -> 保存 JSON
```

结构校验包括：

- 是否存在任务目标。
- 是否抽取出至少一个 required step。
- 是否抽取出 constraints。
- 是否保留 FAQ。
- 每个 Rubric 项是否有 source。

如果解析失败，可以允许人工修正 TaskSpec。比赛 MVP 不必承诺完全无人工介入，但评测执行和报告生成应自动化。

## 5. 用户模拟器设计

### 5.1 场景生成策略

针对每条任务指令，至少生成 5 类场景：

| 场景类型 | 目的 |
| --- | --- |
| 正常配合 | 测试基础任务完成 |
| 用户拒绝 | 测试挽留、安抚、结束逻辑 |
| FAQ 追问 | 测试知识点准确性 |
| 约束压力 | 测试短回复、暂停、口语化等约束 |
| 边界/异常 | 测试越界问题、忙碌、开车等分支 |

飞毛腿任务示例：

- 骑手正常确认可配送。
- 骑手表示今天不想配送。
- 骑手询问退出方式。
- 骑手询问额外奖励。
- 骑手正在配送，不方便长时间通话。
- 骑手问站长能否调整排名。

### 5.2 用户模拟 Prompt

用户模拟器输入：

- 用户画像。
- 场景目标。
- 不能泄露评分项的约束。
- 对话历史。
- 下一轮应覆盖的用户意图。

输出：

- 一句自然用户话术。
- 可选的 `user_state`，例如继续、已满足、应结束。

示例约束：

```text
你扮演一名美团骑手。
你只根据自己的用户画像和对话历史发言。
不要告诉对方你在测试模型。
不要直接说出评分标准。
如果对方已经清楚回答你的问题，可以自然结束。
如果对方遗漏关键说明，可以追问。
```

### 5.3 用户模拟质量控制

用户模拟器需要接受基础质控：

- 是否符合角色身份。
- 是否触发目标分支。
- 是否过度刁钻。
- 是否泄露评测目的。
- 是否脱离任务指令。

MVP 可以用规则和 Judge 简单审计模拟用户输出；如果审计失败，重新生成该轮用户输入。

## 6. 多轮对话执行

对话执行模块的核心参数：

```yaml
max_turns: 10
assistant_temperature: 0.3
user_simulator_temperature: 0.7
stop_when_task_completed: true
stop_when_user_unavailable: true
```

终止条件：

- 达到最大轮数。
- 用户模拟器判断任务已自然结束。
- 待测模型完成任务且用户无进一步问题。
- 用户处于不适合通话状态，例如开车或明确要求稍后联系。

对话执行器不对模型进行优化，只负责记录 trace。

## 7. 评测设计

### 7.1 规则评测

规则评测用于硬约束。

| 规则 | 实现 |
| --- | --- |
| 回复长度 | 中文字符计数 |
| 禁止承诺 | 关键词 + 语义 Judge 复核 |
| 必需信息 | 关键词召回 + 语义 Judge 复核 |
| 重复回复 | 相邻回复相似度 |
| 挂断条件 | 用户状态识别 + 模型结束动作检测 |

规则评测结果要可复现。

### 7.2 Judge 评测

Judge 评测用于语义判断。

Judge 输入：

- 原始任务指令。
- TaskSpec。
- RubricSpec。
- Scenario。
- DialogueTrace。

Judge 输出：

```json
{
  "rubric_item_id": "r1",
  "verdict": "pass|partial|fail",
  "score": 6,
  "max_score": 8,
  "source": "Call Flow 第1步",
  "turn_ids": [3],
  "reason": "模型已明确告知合同今日生效"
}
```

Judge 约束：

- 必须引用 `source`。
- 必须引用 `turn_ids`。
- 不因回复更长而加分。
- 不奖励任务指令外的额外发挥。
- 对不确定项输出 `partial` 或 `needs_review`。

### 7.3 高风险项

高风险项单独标记，不只体现在总分中：

- 承诺额外奖励或优惠。
- 用户开车仍继续长篇说明。
- 超出职责范围直接给确定结论。
- 没确认身份就透露敏感信息。
- 用户明确拒绝后持续施压。

## 8. 可解释报告

报告结构：

```text
1. 任务概览
2. 测试场景列表
3. 场景覆盖矩阵
4. 总分与维度分
5. 每个场景结果
6. 高风险问题
7. 扣分证据链
8. 改进建议
```

证据链格式：

```text
评测项：是否说明合同今日生效
指令依据：Call Flow 第1步
场景：正常配合骑手
对话证据：第3轮，模型说“今天飞毛腿已经生效”
结论：通过
得分：8/8
```

失败证据链格式：

```text
评测项：用户不想配送时是否合理处理
指令依据：Call Flow 第3步
场景：骑手表示今天无法配送
对话证据：第5轮，骑手说“今天真跑不了”；第6轮，模型继续反复要求上线
结论：部分通过
扣分原因：有挽留，但未在用户坚持无法配送后安抚结束
得分：4/8
```

## 9. 模型选择与校准

### 9.1 待测模型

待测模型是评估对象，通过统一接口接入：

```text
generate_response(system_prompt, dialogue_history) -> assistant_response
```

系统不限制待测模型类型。

### 9.2 用户模拟模型

选择标准：

- 能稳定扮演用户角色。
- 能根据对话历史动态追问。
- 输出口语化、简短自然。
- 不主动泄露测试目标。

### 9.3 Judge 模型

选择标准：

- 支持长上下文。
- 结构化 JSON 输出稳定。
- 指令遵循能力强。
- 与人工判断一致性较高。

校准方式：

```text
样例任务人工标注
  -> Judge 打分
  -> 比较一致性
  -> 调整 Judge prompt 和 Rubric
```

未拿到脱敏数据前，用样例指令构造校准集；拿到脱敏数据后，用真实脱敏对话抽样校准。

## 10. 脱敏数据使用

脱敏数据到位后，用于增强系统，而不是作为 MVP 唯一依赖。

用途：

- 补充真实用户表达。
- 统计常见追问和失败分支。
- 校准用户模拟器。
- 校准 Judge。
- 构建回归测试集。

数据安全：

- 不展示手机号、地址、姓名等敏感信息。
- 报告中只引用必要脱敏片段。
- 演示优先使用合成或已脱敏样例。

## 11. 建议目录结构

```text
eval_agent/
  configs/
    model.yaml
    scoring.yaml
  data/
    tasks.xlsx
    scenarios.yaml
    calibration_samples.jsonl
  src/
    instruction_parser.py
    scenario_generator.py
    user_simulator.py
    dialogue_runner.py
    rule_evaluator.py
    judge_evaluator.py
    report_writer.py
  reports/
    task_001_report.md
```

核心接口：

```text
parse_instruction(raw_instruction) -> TaskSpec
build_rubric(task_spec) -> RubricSpec
generate_scenarios(task_spec, rubric, n) -> ScenarioSet
run_dialogue(task_spec, scenario, target_model) -> DialogueTrace
evaluate_rules(trace, rubric) -> RuleEvalResult
evaluate_with_judge(trace, rubric, scenario) -> JudgeEvalResult
aggregate_results(rule_result, judge_result) -> EvaluationResult
write_report(task_spec, scenarios, traces, results) -> Report
```

## 12. MVP 实施计划

### P0：跑通闭环

目标：用飞毛腿任务跑通完整链路。

交付：

- 读取 Excel 任务指令。
- 生成 TaskSpec 和 RubricSpec。
- 生成 5 个用户模拟场景。
- 完成多轮对话。
- 输出 Markdown 报告。

### P1：提升评测有效性

目标：增强覆盖和解释。

交付：

- 场景覆盖矩阵。
- 高风险项标记。
- 规则评测 + Judge 评测融合。
- 扣分证据链。

### P2：使用脱敏数据增强

目标：让用户模拟和 Judge 更贴近真实业务。

交付：

- 从脱敏数据提取常见用户意图。
- 构建小规模人工标注校准集。
- 校准 Judge。
- 增加回归测试场景。

## 13. 比赛演示脚本

推荐演示流程：

1. 展示输入任务指令。
2. 展示自动解析出的任务步骤、约束和 FAQ。
3. 展示生成的用户模拟场景。
4. 选择一个场景运行多轮对话。
5. 展示对话 trace。
6. 展示评测报告。
7. 展示扣分项如何追溯到原始指令和对话轮次。

示例演示场景：

- 骑手询问额外奖励。
- 骑手表示今天无法配送。
- 骑手正在配送不方便长聊。

## 14. 风险与应对

| 风险 | 应对 |
| --- | --- |
| 用户模拟器生成不真实 | 基于指令分支和脱敏数据抽取常见表达，加入模拟器审计 |
| Judge 评分不稳定 | 硬约束走规则，Judge 只处理语义项，并用人工样本校准 |
| 任务解析遗漏 | 解析结果可人工检查，Rubric 每项必须有原始指令依据 |
| 场景覆盖不足 | 按 required steps、FAQ、constraints、edge cases 四类生成场景 |
| 方案过大难落地 | MVP 聚焦飞毛腿任务和 Markdown 报告，不做通用平台 |

## 15. 最小验收标准

比赛 MVP 至少做到：

- 支持读取一条复杂任务指令。
- 生成结构化 TaskSpec 和 RubricSpec。
- 自动生成不少于 5 个用户模拟场景。
- 每个场景可完成多轮对话。
- 生成完整 DialogueTrace。
- 输出总分、维度分和场景结果。
- 每个扣分项有原始指令依据和对话轮次证据。
- 至少包含 3 类规则校验。
- 至少包含 1 个高风险场景。

## 16. 总结

该技术方案严格围绕比赛要求收敛：用户模拟器负责充分测试模型，评测模块负责量化指令遵循效果，报告模块负责解释评测过程和结果。

系统的关键价值不是构建大而全的平台，而是把复杂任务指令转化为可执行、可复现、可解释的多轮评测流程。
