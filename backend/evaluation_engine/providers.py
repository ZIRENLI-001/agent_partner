from __future__ import annotations

from typing import Protocol

from backend.evaluation_engine.domain import Scenario, TaskSpec, Turn

USER_ORIGINATED_SPEAKERS = {"user", "user_simulator"}


class AssistantProvider(Protocol):
    def generate(self, task_spec: TaskSpec, history: list[Turn]) -> str:
        ...


class UserProvider(Protocol):
    def generate(self, scenario: Scenario, history: list[Turn]) -> str:
        ...


class FakeAssistantProvider:
    def generate(self, task_spec: TaskSpec, history: list[Turn]) -> str:
        if not history:
            return task_spec.opening_line

        last_user = _last_user_content(history)

        if "退出" in last_user:
            return "如需退出飞毛腿，请提前一天在App取消。<DONE>"
        if "奖励" in last_user:
            return "目前按平台规则执行，我不能承诺额外奖励。<DONE>"
        if "不想" in last_user:
            return "理解你的情况，合同已生效，建议尽量完成配送。<DONE>"
        if "职责范围" in last_user:
            return "这个问题我需要确认后回电，先提醒合同已生效。<DONE>"

        return "今天合同已经生效，请按要求完成配送。<DONE>"


class FakeUserProvider:
    def generate(self, scenario: Scenario, history: list[Turn]) -> str:
        if not _has_user_turn(history):
            return scenario.initial_user_intent

        targets = set(scenario.coverage_targets)

        if "faq_exit" in targets:
            return "我想问下怎么退出飞毛腿？"
        if "reward_question" in targets:
            return "那今天会有额外奖励吗？"
        if "refusal_to_deliver" in targets:
            return "我今天不太想配送。"
        if "out_of_scope" in targets:
            return "这个属于你职责范围吗？"
        if "busy_or_unavailable" in targets:
            return "我现在有点忙，你简单说。"

        if len(history) <= 1:
            return "是我，你说。"
        return "好的，我知道了。"


def _last_user_content(history: list[Turn]) -> str:
    for turn in reversed(history):
        if turn.speaker in USER_ORIGINATED_SPEAKERS:
            return turn.content
    return ""


def _has_user_turn(history: list[Turn]) -> bool:
    return any(turn.speaker in USER_ORIGINATED_SPEAKERS for turn in history)
