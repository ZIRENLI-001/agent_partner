from __future__ import annotations

from backend.evaluation_engine.domain import Scenario, Turn
from backend.evaluation_engine.providers import UserProvider


def next_user_turn(provider: UserProvider, scenario: Scenario, history: list[Turn]) -> str:
    content = provider.generate(scenario, history).strip()
    if content and is_valid_user_turn(content, scenario, history):
        return content
    fallback = _fallback_user_turn(scenario, history)
    if is_valid_user_turn(fallback, scenario, history):
        return fallback
    return "我没太听清。"


def is_valid_user_turn(
    content: str,
    scenario: Scenario,
    history: list[Turn] | None = None,
) -> bool:
    history = history or []
    return not (
        _looks_like_assistant_echo(content, history)
        or _looks_like_platform_role_leak(content)
        or _looks_like_cross_domain_content(content, scenario)
        or _looks_like_platform_side_question(content)
        or _looks_like_role_reversal(content, scenario)
        or _looks_like_meta_placeholder(content)
        or _looks_like_identity_contradiction(content, history)
    )


def _looks_like_assistant_echo(content: str, history: list[Turn]) -> bool:
    normalized_content = _normalize_for_overlap(content)
    if not normalized_content:
        return False

    assistant_turns = [
        _normalize_for_overlap(turn.content)
        for turn in history
        if turn.speaker == "assistant"
    ]
    assistant_turns = [turn for turn in assistant_turns if turn]
    if not assistant_turns:
        return False

    for normalized_assistant in assistant_turns:
        if normalized_content == normalized_assistant:
            return True
        if normalized_content in normalized_assistant or normalized_assistant in normalized_content:
            return True

        content_terms = _meaningful_terms(normalized_content)
        assistant_terms = _meaningful_terms(normalized_assistant)
        if not content_terms or not assistant_terms:
            continue
        overlap = content_terms & assistant_terms
        if len(overlap) >= 4 and len(overlap) / len(content_terms) >= 0.65:
            return True
    return False


def _last_assistant_content(history: list[Turn]) -> str:
    for turn in reversed(history):
        if turn.speaker == "assistant":
            return turn.content
    return ""


def _looks_like_platform_role_leak(content: str) -> bool:
    platform_markers = [
        "美团履约运营",
        "履约运营",
        "我是站长",
        "我是客服",
        "我是美团",
        "这边是美团",
        "平台这边",
    ]
    return any(marker in content for marker in platform_markers)


def _looks_like_platform_side_question(content: str) -> bool:
    platform_question_markers = [
        "您这边的店铺出了问题",
        "配送环节出现了延迟",
        "我这边需要了解",
        "方便告知吗",
        "请问是什么原因导致",
        "还需要多久能出餐",
        "还需要几分钟能出餐",
        "预计能完成多少单",
        "今天预计能完成",
        "能完成多少单",
        "奖励比较多",
        "抽点时间上线",
        "方便上线吗",
        "能不能上线",
        "午晚高峰上线",
        "午餐和晚餐高峰期需上线",
        "今天有活动",
        "可以告诉我吗",
        "你想退出",
        "帮你了解",
        "帮你处理",
        "帮你确认",
        "具体流程",
    ]
    return any(marker in content for marker in platform_question_markers)


def _looks_like_role_reversal(content: str, scenario: Scenario) -> bool:
    if _scenario_user_role(scenario) == "rider":
        return _looks_like_rider_role_reversal(content)
    return False


def _scenario_user_role(scenario: Scenario) -> str:
    scenario_text = " ".join(
        [
            str(scenario.user_profile.get("role", "")),
            scenario.scenario_id,
            scenario.scenario_type,
            " ".join(scenario.coverage_targets),
            " ".join(scenario.risk_tags),
            scenario.expected_test_focus,
            scenario.initial_user_intent,
        ]
    )
    if any(marker in scenario_text for marker in ["骑手", "rider", "飞毛腿"]):
        return "rider"
    if any(marker in scenario_text for marker in ["商家", "店长", "merchant", "出餐"]):
        return "merchant"
    if any(marker in scenario_text for marker in ["机构", "校区", "课程", "直播", "course"]):
        return "course_customer"
    return "unknown"


def _looks_like_rider_role_reversal(content: str) -> bool:
    normalized = content.replace("您", "你")
    platform_phrases = [
        "你今天有空吗",
        "今天有空吗",
        "上线完成",
        "完成单量",
        "单量任务",
        "现在方便说",
        "方便说几句",
        "确认一下合同",
        "确认合同信息",
        "合同信息",
        "你签了飞毛腿合同",
        "我们这边有指标",
        "有指标要完成",
        "影响后续接单",
        "能不能帮忙出一单",
        "帮忙出一单",
        "出来跑单吗",
        "能先跑吗",
        "高峰期要上线",
        "午晚高峰需要上线",
        "骑手app里的",
        "飞毛腿页面找到退出",
        "找到退出选项",
        "按照提示操作退出",
        "帮你详细说明",
        "帮你联系",
        "我帮你",
        "我这边好安排",
    ]
    return any(phrase in normalized.lower() for phrase in [p.lower() for p in platform_phrases])


def _looks_like_meta_placeholder(content: str) -> bool:
    stripped = content.strip()
    if not stripped:
        return False
    if len(stripped) > 24:
        return False

    meta_prefixes = [
        "确认",
        "表达",
        "询问",
        "追问",
        "拒绝",
        "说明",
        "表示",
        "质疑",
        "抱怨",
        "配合",
        "打断",
    ]
    meta_objects = [
        "自己",
        "身份",
        "负责人",
        "忙碌",
        "没空",
        "不满",
        "疑问",
        "奖励",
        "补贴",
        "地址",
        "原因",
        "意愿",
        "态度",
    ]
    return any(stripped.startswith(prefix) for prefix in meta_prefixes) and any(
        marker in stripped for marker in meta_objects
    )


def _looks_like_cross_domain_content(content: str, scenario: Scenario) -> bool:
    scenario_text = " ".join(
        [
            scenario.scenario_id,
            scenario.scenario_type,
            " ".join(scenario.coverage_targets),
            " ".join(scenario.risk_tags),
            scenario.expected_test_focus,
            scenario.initial_user_intent,
        ]
    )
    if "merchant" in scenario_text or "出餐" in scenario_text or "商家" in scenario_text:
        forbidden_terms = ["低延迟直播", "标准直播", "课程", "直播", "校务系统", "SaaS"]
        return any(term in content for term in forbidden_terms)
    if "course" in scenario_text or "直播" in scenario_text or "课程" in scenario_text:
        forbidden_terms = ["出餐", "订单延迟", "配送环节", "骑手"]
        return any(term in content for term in forbidden_terms)
    return False


def _looks_like_identity_contradiction(content: str, history: list[Turn]) -> bool:
    previous_user_text = " ".join(
        turn.content
        for turn in history
        if turn.speaker in {"user", "user_simulator"}
    )
    said_not_responsible = any(
        marker in previous_user_text
        for marker in ["不是负责人", "不是店长", "打工的", "我只是店员", "我喊一下老板"]
    )
    claims_responsible = any(
        marker in content
        for marker in ["我是负责人", "我是店长", "我店里", "我们店里", "我这边负责"]
    )
    return said_not_responsible and claims_responsible


def _normalize_for_overlap(content: str) -> str:
    return "".join(ch for ch in content.strip().lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _meaningful_terms(content: str) -> set[str]:
    if len(content) <= 2:
        return {content}
    return {content[index : index + 2] for index in range(len(content) - 1)}


def _fallback_user_turn(scenario: Scenario, history: list[Turn] | None = None) -> str:
    targets = set(scenario.coverage_targets) | set(scenario.risk_tags)
    previous_user_text = " ".join(
        turn.content
        for turn in (history or [])
        if turn.speaker in {"user", "user_simulator"}
    )
    if any(
        marker in previous_user_text
        for marker in ["不是负责人", "不是店长", "打工的", "我只是店员", "我喊一下老板"]
    ):
        return "我不是负责人，我帮您喊一下老板。"
    if targets & {"merchant_delay_notice", "merchant_ready_confirmation", "merchant_notice", "merchant_delay"}:
        return "后厨有点压单，还需要五分钟左右。"
    initial_intent = scenario.initial_user_intent.strip()
    if initial_intent:
        return initial_intent
    if targets & {"busy_or_unavailable", "boss_busy_retention", "capacity_pressure"}:
        return "我现在不太方便，能不能简单说重点？"
    if targets & {"poor_signal", "interruption_recovery", "conversation_repair"}:
        return "喂？你刚说哪件事，我这边没听清。"
    if targets & {"address_exception", "route_eta_challenge"}:
        return "这个地址我有点不确定，你先帮我核一下。"
    if targets & {"reward_question", "boundary_no_extra_promise", "benefit_boundary"}:
        return "那有没有额外补贴？没有的话我不太想接。"
    if targets & {"faq_exit", "rider_app_operation"}:
        return "我想确认一下这个规则具体怎么操作。"
    if targets & {"product_upgrade_notice", "upgrade_notice"}:
        return "我是负责人，您说是什么事？"
    if targets & {"identity_mismatch", "identity_confirmation"}:
        return "你是不是找错人了？我不确定你说的是我。"
    return "我没太听清，能简单说一下重点吗？"
