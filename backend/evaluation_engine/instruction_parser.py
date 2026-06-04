from __future__ import annotations

import re

from backend.evaluation_engine.domain import TaskSpec


SECTION_HEADING_RE = re.compile(r"^(#{1,3})\s+([^:\n]+?)(?::\s*(.*))?\s*$", re.MULTILINE)


def parse_instruction(raw: str, task_id: str) -> TaskSpec:
    sections = _parse_sections(raw)
    flow_text = sections.get("Call Flow", "") or sections.get("Conversation Flow", "")
    required_steps = _parse_numbered_items(flow_text)
    if not required_steps:
        required_steps = _parse_step_sections(sections)
    constraints = _parse_bullets(sections.get("Constraints", ""))
    faq = _parse_faq(
        sections.get("Knowledge Points (FAQ)", "") or sections.get("FAQ", "")
    )
    edge_cases = _infer_edge_cases(raw, required_steps, constraints, faq)

    return TaskSpec(
        task_id=task_id,
        task_name=_task_name(sections.get("Task", "")),
        role=_clean_role(sections.get("Role", "")),
        target_user=_infer_target_user(raw),
        task_goal=_clean_text(sections.get("Task", "")),
        opening_line=_clean_text(sections.get("Opening Line", "")),
        required_steps=required_steps,
        constraints=constraints,
        faq=faq,
        edge_cases=edge_cases,
        forbidden_actions=_infer_forbidden_actions(raw, constraints),
    )


def _parse_sections(raw: str) -> dict[str, str]:
    matches = list(SECTION_HEADING_RE.finditer(raw))
    sections = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        title = match.group(2).strip()
        inline_content = (match.group(3) or "").strip()
        body = raw[start:end].strip()
        content = "\n".join(part for part in [inline_content, body] if part)
        sections[title] = content
    return sections


def _parse_numbered_items(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        cleaned = re.sub(r"^\s*\d+\.\s*", "", line).strip()
        cleaned = re.sub(r"^\s*[-*]\s*", "", cleaned).strip()
        if cleaned:
            items.append(_strip_terminal_punctuation(cleaned))
    return items


def _parse_step_sections(sections: dict[str, str]) -> list[str]:
    items = []
    for title, body in sections.items():
        if not title.lower().startswith("step "):
            continue
        body_lines = [line.strip() for line in body.splitlines() if line.strip()]
        summary = body_lines[0] if body_lines else title
        summary = re.sub(r"^\s*[-*]\s*", "", summary).strip()
        items.append(_strip_terminal_punctuation("%s：%s" % (title, summary)))
    return items


def _parse_bullets(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        cleaned = re.sub(r"^\s*[-*]\s*", "", line).strip()
        if cleaned:
            items.append(_strip_terminal_punctuation(cleaned))
    return items


def _parse_faq(text: str) -> list[dict[str, str]]:
    faq = []
    for item in _parse_bullets(text):
        intent = _infer_faq_intent(item)
        faq.append({"intent": intent, "expected_answer": item})
    return faq


def _infer_faq_intent(item: str) -> str:
    match = re.search(r"(退出[^，,；;。]*)", item)
    if match:
        return match.group(1).strip()
    match = re.search(r"如需([^，,；;。]*)", item)
    if match:
        return match.group(1).strip()
    return item[:20]


def _infer_edge_cases(
    raw: str,
    required_steps: list[str],
    constraints: list[str],
    faq: list[dict[str, str]],
) -> list[dict[str, str]]:
    edge_cases = []
    if "不想配送" in raw:
        edge_cases.append(
            {
                "trigger": "不想配送",
                "expected_behavior": "尽量挽留，并说明合同和配送影响",
            }
        )
    if any("超出职责范围" in item for item in constraints):
        edge_cases.append(
            {
                "trigger": "超出职责范围问题",
                "expected_behavior": "说明会向同事确认后回电，并先回答可回答内容",
            }
        )
    if any(item.get("intent") == "退出飞毛腿" for item in faq):
        edge_cases.append(
            {
                "trigger": "询问退出飞毛腿",
                "expected_behavior": "告知需前一天指定时间前在 App 取消，次日生效",
            }
        )
    return edge_cases


def _infer_forbidden_actions(raw: str, constraints: list[str]) -> list[str]:
    forbidden = []
    if any("超出职责范围" in item for item in constraints):
        forbidden.append("对超出职责范围的问题直接给出确定答复")
    if "奖励" in raw or "优惠" in raw:
        forbidden.append("承诺额外奖励或优惠")
    return forbidden


def _clean_role(text: str) -> str:
    cleaned = _clean_text(text)
    cleaned = re.sub(r"^你是", "", cleaned)
    return _strip_terminal_punctuation(cleaned)


def _clean_text(text: str) -> str:
    return " ".join(text.strip().split())


def _strip_terminal_punctuation(text: str) -> str:
    return text.rstrip("。；;")


def _task_name(task_goal: str) -> str:
    cleaned = _clean_text(task_goal)
    if "飞毛腿" in cleaned:
        return "飞毛腿通知"
    return cleaned[:20] or "instruction_task"


def _infer_target_user(raw: str) -> str:
    if "骑手" in raw:
        return "骑手"
    return "用户"
