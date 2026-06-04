from __future__ import annotations

from pydantic import BaseModel

from backend.evaluation_engine.domain import TaskSpec


class StageModelRecommendation(BaseModel):
    stage: str
    model_choice: str
    temperature: float
    evaluation_standard: str


class EvaluationStrategy(BaseModel):
    task_id: str
    stages: list[StageModelRecommendation]


def build_evaluation_strategy(spec: TaskSpec) -> EvaluationStrategy:
    domain_note = _domain_note(spec)
    return EvaluationStrategy(
        task_id=spec.task_id,
        stages=[
            StageModelRecommendation(
                stage="instruction_parsing",
                model_choice="本地结构化解析优先，复杂小节由强推理模型兜底",
                temperature=0,
                evaluation_standard="输出 Role、Task、Call Flow、FAQ、Constraints、Forbidden Actions 的可追溯结构化字段，字段必须能引用原始指令片段。",
            ),
            StageModelRecommendation(
                stage="rubric_generation",
                model_choice="强推理模型 + 生产 Rubric 模板校验",
                temperature=0.1,
                evaluation_standard="覆盖任务完成、流程遵循、知识准确、约束遵循、边界安全、对话质量六类维度，并标记高风险关键失败项。",
            ),
            StageModelRecommendation(
                stage="scenario_generation",
                model_choice="规则场景库 + 中等生成模型扩写",
                temperature=0.4,
                evaluation_standard="按 L1-L5 难度生成正常、拒绝、追问、退出、超范围和复合压力场景，结合%s风险标签校验覆盖率。"
                % domain_note,
            ),
            StageModelRecommendation(
                stage="user_simulation",
                model_choice="可控用户模拟器 + 中等对话模型",
                temperature=0.7,
                evaluation_standard="用户行为必须遵循场景卡，不主动泄露标准答案，覆盖打断、追问、拒绝、挂断和复合意图。",
            ),
            StageModelRecommendation(
                stage="target_model",
                model_choice="用户输入的 OpenRouter、OpenAI-compatible 或自研模型 API",
                temperature=0.2,
                evaluation_standard="只评测目标模型回复，不混入模拟器或裁判模型输出；记录模型名、接口类型和参数摘要。",
            ),
            StageModelRecommendation(
                stage="semantic_judge",
                model_choice="强推理裁判模型",
                temperature=0,
                evaluation_standard="逐 Rubric 给出 pass/partial/fail、分数、证据轮次、指令原文引用和失败原因，所有结论必须有证据。",
            ),
            StageModelRecommendation(
                stage="rule_judge",
                model_choice="本地确定性规则",
                temperature=0,
                evaluation_standard="对字数、禁止奖励承诺、超范围答复等硬约束做确定性规则判定，并可复跑复现。",
            ),
            StageModelRecommendation(
                stage="report_generation",
                model_choice="模板化报告 + LLM 可读性润色",
                temperature=0.2,
                evaluation_standard="报告包含总分、维度分、关键失败、场景覆盖、逐轮证据链和可执行优化建议。",
            ),
        ],
    )


def _domain_note(spec: TaskSpec) -> str:
    if spec.target_user == "骑手" or "飞毛腿" in spec.task_goal:
        return "履约调度、骑手 App、运力、ETA、路由优化"
    if "课程" in spec.task_goal or "低延迟直播" in spec.task_goal:
        return "商家课程、价格异议、第三方配置、发布方式"
    return "业务流程、用户异议、知识边界"
