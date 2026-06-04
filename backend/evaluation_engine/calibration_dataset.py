from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = ROOT / "data" / "calibration" / "meituan_fulfillment_calibration.jsonl"
DEFAULT_SAMPLE_TARGET = 1000
REQUIRED_SAMPLE_FIELDS = {
    "sample_id",
    "source_instruction_id",
    "domain",
    "difficulty",
    "scenario_type",
    "coverage_targets",
    "risk_tags",
    "task_instruction",
    "input_variables",
    "dialogue",
    "expected_labels",
    "expected_score_band",
}
VALID_VERDICTS = {"pass", "partial", "fail", "needs_review"}
VALID_DOMAINS = {
    "meituan_fulfillment",
    "course_publishing",
    "fulfillment_ops",
    "merchant_fulfillment",
    "customer_fulfillment",
}


def load_calibration_dataset(path: Path | None = None) -> list[dict[str, Any]]:
    dataset_path = path or DEFAULT_DATASET_PATH
    samples = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if dataset_path == DEFAULT_DATASET_PATH:
        samples = _expand_default_dataset(samples)
        samples = [_enrich_default_sample(sample) for sample in samples]
    for sample in samples:
        _validate_sample(sample)
    return samples


def summarize_calibration_dataset(samples: list[dict[str, Any]]) -> dict[str, Any]:
    difficulty_counts = Counter(sample["difficulty"] for sample in samples)
    scenario_type_counts = Counter(sample["scenario_type"] for sample in samples)
    risk_tag_counts = Counter(tag for sample in samples for tag in sample["risk_tags"])
    label_counts = Counter(
        label["expected_verdict"]
        for sample in samples
        for label in sample["expected_labels"]
    )
    coverage_targets = sorted(
        {target for sample in samples for target in sample["coverage_targets"]}
    )
    labeled_samples_with_evidence = sum(
        1
        for sample in samples
        if all(label.get("evidence_turn_ids") for label in sample["expected_labels"])
    )
    evidence_coverage_rate = (
        round(labeled_samples_with_evidence / len(samples), 4) if samples else 0
    )
    return {
        "dataset_id": "outbound_instruction_following_samples_v1",
        "sample_count": len(samples),
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "scenario_type_counts": dict(sorted(scenario_type_counts.items())),
        "risk_tag_counts": dict(sorted(risk_tag_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "coverage_targets": coverage_targets,
        "evidence_coverage_rate": evidence_coverage_rate,
    }


def calibration_payload() -> dict[str, Any]:
    samples = load_calibration_dataset()
    return {
        "summary": summarize_calibration_dataset(samples),
        "samples": samples,
    }


def _validate_sample(sample: dict[str, Any]) -> None:
    missing = REQUIRED_SAMPLE_FIELDS - set(sample)
    if missing:
        raise ValueError("Calibration sample missing fields: %s" % sorted(missing))
    if sample["domain"] not in VALID_DOMAINS:
        raise ValueError("Unsupported calibration domain: %s" % sample["domain"])
    if sample["difficulty"] not in {"L1", "L2", "L3", "L4", "L5"}:
        raise ValueError("Invalid calibration difficulty: %s" % sample["difficulty"])

    turn_ids = {turn.get("turn_id") for turn in sample["dialogue"]}
    if len(turn_ids) != len(sample["dialogue"]):
        raise ValueError("Dialogue turn ids must be unique for %s" % sample["sample_id"])
    for label in sample["expected_labels"]:
        if label.get("expected_verdict") not in VALID_VERDICTS:
            raise ValueError("Invalid expected verdict in %s" % sample["sample_id"])
        evidence_turn_ids = set(label.get("evidence_turn_ids") or [])
        if not evidence_turn_ids or not evidence_turn_ids.issubset(turn_ids):
            raise ValueError("Invalid evidence turns in %s" % sample["sample_id"])

    score_band = sample["expected_score_band"]
    if score_band["min"] > score_band["max"]:
        raise ValueError("Invalid score band in %s" % sample["sample_id"])


def _expand_default_dataset(seed_samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(seed_samples) >= DEFAULT_SAMPLE_TARGET:
        return seed_samples[:DEFAULT_SAMPLE_TARGET]
    samples = list(seed_samples)
    family_index = 0
    while len(samples) < DEFAULT_SAMPLE_TARGET:
        family = SAMPLE_FAMILIES[family_index % len(SAMPLE_FAMILIES)]
        variant = family_index // len(SAMPLE_FAMILIES) + 1
        samples.append(_build_generated_sample(family, variant))
        family_index += 1
    return samples


def _build_generated_sample(family: dict[str, Any], variant: int) -> dict[str, Any]:
    verdict = family["verdict_cycle"][(variant - 1) % len(family["verdict_cycle"])]
    severity = "critical" if verdict == "fail" and family["difficulty"] in {"L4", "L5"} else "normal"
    user_names = family.get("user_names", DEFAULT_CONTACT_NAMES)
    user_name = user_names[(variant - 1) % len(user_names)]
    assistant_issue = family["assistant_issue"] if verdict == "fail" else family["assistant_success"]
    suffix = "%02d" % variant
    score_band = _score_band(family["difficulty"], verdict)
    return {
        "sample_id": "%s_%s" % (family["sample_prefix"], suffix),
        "source_instruction_id": family["source_instruction_id"],
        "domain": family["domain"],
        "difficulty": family["difficulty"],
        "scenario_type": family["scenario_type"],
        "coverage_targets": family["coverage_targets"],
        "risk_tags": family["risk_tags"],
        "task_instruction": family["task_instruction"],
        "input_variables": {
            "contact_name": user_name,
            "business_line": family["business_line"],
            "variant": str(variant),
        },
        "dialogue": [
            {"turn_id": 1, "speaker": "assistant", "content": family["opening"].format(name=user_name)},
            {"turn_id": 2, "speaker": "user", "content": family["user_turn"].format(name=user_name)},
            {"turn_id": 3, "speaker": "assistant", "content": assistant_issue.format(name=user_name)},
            {"turn_id": 4, "speaker": "user", "content": family["user_followup"]},
            {"turn_id": 5, "speaker": "assistant", "content": family["closing"].format(name=user_name)},
        ],
        "expected_labels": [
            {
                "rubric_item_id": family["rubric_item_id"],
                "expected_verdict": verdict,
                "expected_reason": family["reason_%s" % verdict],
                "evidence_turn_ids": [2, 3],
                "severity": severity,
            },
            {
                "rubric_item_id": "evidence_traceability",
                "expected_verdict": "pass" if verdict != "fail" else "partial",
                "expected_reason": "样本保留用户问题、模型回复和可定位证据轮次。",
                "evidence_turn_ids": [1, 2, 3],
                "severity": "normal",
            },
        ],
        "expected_score_band": score_band,
    }


FLYING_RIDER_INSTRUCTION_TEMPLATE = """# Role
你是美团外卖骑手的站长。

# Task
致电"飞毛腿"骑手，通知他们今天合同已成功签署，并提醒他们完成配送任务。

# Opening Line
你好，请问是${rider_name}吗？我是站长。我看到你已报名飞毛腿。请记住，午餐和晚餐高峰期需要上线。单日合同每天至少完成 **X 单**；多日合同每天至少完成 **Y 单**。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效，并询问他们是否可以开始配送。
2. 说明单日飞毛腿合同需要**连续 Y 天**完成配送；否则合同将受到影响。
3. 尽量挽留不想配送的骑手，鼓励能配送的骑手，并提醒他们注意安全。
4. 说明飞毛腿报名是按排名进行的，并非站长干预。骑手应减少拒单、取消和超时。在恶劣天气下工作、订单量更高，有助于保住飞毛腿资格。

# Knowledge Points (FAQ)
- 目前，许多骑手正在申请飞毛腿。如果你无法连续配送 **Y 天**，你的名额可能会被他人占用。
- 单日合同：在生效当天必须完成 **X 单**，否则合同及派单可能受到影响。
- 多日合同：每天必须完成 **Y 单**，否则后续合同及派单可能受到影响。
- 如需退出飞毛腿，必须在前一天 **Z 点之前**在 App 的"飞毛腿报名"中取消；次日生效。
- 连续完成 **W 天**多日合同，且每天完成 **Y 单**，将获得额外奖励（例如，与单日合同相比每单多 +$ 元）。

# Constraints
- 遵循对话流程和常见问题解答。
- 如被问及超出职责范围的问题，回复："我向同事确认后再回电给你。我现在能回答的先回答。"
- 保持语气随意，像打电话一样自然。
- 每次回复控制在**约 30 个字以内**。
- 避免重复回复；如需重申，请换种方式礼貌表达。
- 如果骑手坚持确实无法配送，安慰他们后挂断电话。
"""


def _enrich_default_sample(sample: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(sample)
    enriched["coverage_targets"] = _coverage_targets_aligned_to_labels(enriched)
    variables = dict(enriched.get("input_variables") or {})
    contact_name = variables.get("contact_name") or variables.get("rider_name") or _contact_name_from_dialogue(enriched)
    variables.update(
        {
            "contact_name": contact_name or "联系人",
            "scenario_type": str(enriched.get("scenario_type", "")),
            "difficulty": str(enriched.get("difficulty", "")),
            "domain": str(enriched.get("domain", "")),
            "coverage_targets": ",".join(enriched.get("coverage_targets", [])),
            "risk_tags": ",".join(enriched.get("risk_tags", [])),
        }
    )

    if sample.get("source_instruction_id") != "1":
        enriched["input_variables"] = variables
        enriched["task_instruction"] = _generic_structured_instruction(enriched)
        return enriched

    rider_name = (
        variables.get("rider_name")
        or variables.get("contact_name")
        or _contact_name_from_dialogue(enriched)
        or "王师傅"
    )
    variables.update(
        {
            "rider_name": rider_name,
            "contract_name": variables.get("contract_name", "飞毛腿"),
            "effective_date": variables.get("effective_date", "今天"),
            "X": variables.get("X", "3"),
            "Y": variables.get("Y", "5"),
            "Z": variables.get("Z", "21"),
            "W": variables.get("W", "7"),
            "reward_delta": variables.get("reward_delta", "1"),
            "peak_windows": variables.get("peak_windows", "午餐高峰、晚餐高峰"),
            "app_entry": variables.get("app_entry", "飞毛腿报名"),
            "contract_type": variables.get("contract_type", "单日/多日飞毛腿合同"),
        }
    )
    enriched["input_variables"] = variables
    enriched["task_instruction"] = FLYING_RIDER_INSTRUCTION_TEMPLATE
    return enriched


def _coverage_targets_aligned_to_labels(sample: dict[str, Any]) -> list[str]:
    targets = list(sample.get("coverage_targets") or [])
    seen = set(targets)
    for label in sample.get("expected_labels", []):
        rubric_item_id = label.get("rubric_item_id")
        if not rubric_item_id or rubric_item_id == "evidence_traceability":
            continue
        if rubric_item_id not in seen:
            targets.append(rubric_item_id)
            seen.add(rubric_item_id)
    return targets


def _contact_name_from_dialogue(sample: dict[str, Any]) -> str:
    for turn in sample.get("dialogue", []):
        content = str(turn.get("content", ""))
        for suffix in ["师傅", "骑手", "老师", "校长", "店长", "经理", "负责人"]:
            if suffix in content:
                index = content.find(suffix)
                start = max(0, index - 2)
                return content[start : index + len(suffix)]
    return ""


def _generic_structured_instruction(sample: dict[str, Any]) -> str:
    profile = _domain_instruction_profile(sample)
    original_task = str(sample.get("task_instruction", "")).strip()
    coverage_targets = "、".join(sample.get("coverage_targets", [])) or "任务核心流程"
    risk_tags = "、".join(sample.get("risk_tags", [])) or "常规履约风险"
    scenario_type = str(sample.get("scenario_type", "通用外呼场景"))
    difficulty = str(sample.get("difficulty", "L3"))

    return """# Role
{role}

# Task
{task}

# Opening Line
{opening}

# Call Flow
1. 确认对方身份或当前处理对象，并用简短话术说明本次来电目的。
2. 围绕当前场景 `{scenario_type}` 完成核心通知、确认或引导动作，覆盖：{coverage_targets}。
3. 当用户追问、打断、拒绝或提出异常要求时，先回应其关切，再回到任务目标。
4. 对涉及权限、费用、派单、算法、取消、处罚、安全或系统异常的问题，按职责边界回答，不虚构承诺。
5. 在完成核心任务后，确认下一步动作、记录事项或后续回访安排。

# Knowledge Points (FAQ)
- 当前样本难度为 {difficulty}，重点覆盖风险标签：{risk_tags}。
- 如问题在指令范围内，优先给出简短、准确、可执行的回答。
- 如问题超出当前角色职责，回复：“我向同事确认后再回电给你。我现在能回答的先回答。”
- 如涉及费用、优惠、处罚、派单、排名、路线或系统策略，不承诺未授权结果，以页面规则、合同规则或专人确认为准。
- 如涉及安全风险，优先提醒对方注意安全，不强迫继续操作或履约。

# Constraints
- 遵循对话流程和常见问题解答。
- 保持电话外呼语气自然、简短、清晰。
- 每次回复控制在约 30 个字以内，复杂操作需要分步说明并等待用户反馈。
- 避免重复回复；如需重申，请换种方式礼貌表达。
- 不编造政策、算法、优惠、处罚或系统处理结果。
- 保留可解释评测证据：每个关键判断应能对应到具体对话轮次。
""".format(
        role=profile["role"],
        task=original_task or profile["task"],
        opening=profile["opening"],
        scenario_type=scenario_type,
        coverage_targets=coverage_targets,
        difficulty=difficulty,
        risk_tags=risk_tags,
    )


def _domain_instruction_profile(sample: dict[str, Any]) -> dict[str, str]:
    domain = sample.get("domain")
    if domain == "course_publishing":
        return {
            "role": "你是课程发布平台的客户支持专员。",
            "task": "致电机构客户，告知课程发布页能力变化，并引导其按课程类型选择合适直播方案。",
            "opening": "您好，请问您是贵培训机构/校区的负责人吗？",
        }
    if domain == "merchant_fulfillment":
        return {
            "role": "你是美团履约运营外呼专员，负责与商家确认订单履约异常。",
            "task": "致电商家确认出餐、订单状态或履约异常，并同步后续处理方向。",
            "opening": "您好，请问是${contact_name}吗？这边和您确认一笔履约订单。",
        }
    if domain == "customer_fulfillment":
        return {
            "role": "你是美团履约客服外呼专员，负责与用户确认配送异常和后续处理。",
            "task": "致电用户确认地址、无法联系、售后边界或配送异常，并给出合规处理说明。",
            "opening": "您好，请问是${contact_name}吗？这边和您确认当前订单配送情况。",
        }
    if domain == "fulfillment_ops":
        return {
            "role": "你是美团履约运营调度外呼专员。",
            "task": "致电骑手、站点或相关履约角色，确认订单分配、路线、ETA、运力或系统异常处理。",
            "opening": "您好，请问是${contact_name}吗？这边和您确认当前履约任务。",
        }
    return {
        "role": "你是美团履约外呼专员。",
        "task": "致电相关用户完成履约场景下的通知、确认、解释和边界处理。",
        "opening": "您好，请问是${contact_name}吗？这边和您确认当前履约事项。",
    }


def _score_band(difficulty: str, verdict: str) -> dict[str, int]:
    if verdict == "fail":
        return {"min": 20, "max": 55}
    if verdict == "partial":
        return {"min": 60, "max": 80}
    base = {"L1": 90, "L2": 85, "L3": 80, "L4": 75, "L5": 70}[difficulty]
    return {"min": base, "max": 100}


SAMPLE_FAMILIES: list[dict[str, Any]] = [
    {
        "sample_prefix": "mt_fulfillment_l1_peak_login",
        "source_instruction_id": "1",
        "domain": "meituan_fulfillment",
        "business_line": "骑手履约",
        "difficulty": "L1",
        "scenario_type": "normal_confirmation",
        "coverage_targets": ["opening_identity", "contract_notice", "delivery_confirmation", "short_reply"],
        "risk_tags": ["baseline", "contract_compliance"],
        "rubric_item_id": "delivery_confirmation",
        "task_instruction": "通知骑手合同生效，提醒午晚高峰上线并确认可配送。",
        "opening": "{name}您好，我是站长，飞毛腿合同今天已生效。",
        "user_turn": "我是{name}，今天可以上线。",
        "assistant_success": "好的，请午晚高峰保持在线，注意安全。",
        "assistant_issue": "那您自己看着办吧。",
        "user_followup": "明白。",
        "closing": "辛苦{name}，按合同完成配送即可。",
        "verdict_cycle": ["pass", "pass", "partial"],
        "reason_pass": "模型完成合同生效通知和上线确认。",
        "reason_partial": "模型确认配送，但对高峰期提醒不完整。",
        "reason_fail": "模型未完成配送确认。",
    },
    {
        "sample_prefix": "mt_fulfillment_l2_contract_faq",
        "source_instruction_id": "1",
        "domain": "meituan_fulfillment",
        "business_line": "骑手履约",
        "difficulty": "L2",
        "scenario_type": "contract_faq",
        "coverage_targets": ["order_count_answer", "faq_cancel_deadline", "contract_notice"],
        "risk_tags": ["contract_compliance", "faq_boundary"],
        "rubric_item_id": "faq_accuracy",
        "task_instruction": "回答骑手关于单日/多日合同订单量、退出截止时间的指令内问题。",
        "opening": "{name}您好，我看到您已报名飞毛腿。",
        "user_turn": "今天要跑几单？不想跑还能退出吗？",
        "assistant_success": "单日需完成X单，退出要前一天Z点前在App取消。",
        "assistant_issue": "今天随时能退，不影响派单。",
        "user_followup": "那我知道了。",
        "closing": "辛苦{name}，请尽快安排配送。",
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型准确回答订单量和退出截止时间。",
        "reason_partial": "模型回答了部分 FAQ，但缺少明确入口或时间。",
        "reason_fail": "模型给出与指令冲突的退出规则。",
    },
    {
        "sample_prefix": "mt_fulfillment_l3_refusal_retain",
        "source_instruction_id": "1",
        "domain": "meituan_fulfillment",
        "business_line": "骑手履约",
        "difficulty": "L3",
        "scenario_type": "rider_refusal",
        "coverage_targets": ["retention", "delivery_confirmation", "failure_detection"],
        "risk_tags": ["capacity_pressure", "contract_compliance"],
        "rubric_item_id": "retention",
        "task_instruction": "骑手拒绝或忙碌时，应自然挽留并确认是否可配送。",
        "opening": "{name}您好，飞毛腿合同今天生效，方便开始配送吗？",
        "user_turn": "今天太忙，不想跑了。",
        "assistant_success": "理解您忙，但合同已生效，建议尽量安排时间履约。",
        "assistant_issue": "好的，那我直接给您结束。",
        "user_followup": "我再考虑一下。",
        "closing": "请{name}尽量上线，有困难我先记录。",
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型表达理解并完成有效挽留。",
        "reason_partial": "模型有挽留但没有明确履约确认。",
        "reason_fail": "模型在拒绝后直接结束，没有挽留。",
    },
    {
        "sample_prefix": "mt_fulfillment_l4_reward_weather",
        "source_instruction_id": "1",
        "domain": "meituan_fulfillment",
        "business_line": "骑手履约",
        "difficulty": "L4",
        "scenario_type": "reward_weather_boundary",
        "coverage_targets": ["extra_reward_boundary", "safety_boundary", "no_extra_promise"],
        "risk_tags": ["extra_reward_boundary", "weather_safety", "contract_compliance"],
        "rubric_item_id": "boundary_control",
        "task_instruction": "面对奖励、天气和安全问题时，既要提醒履约，也不能越权承诺或强迫冒险。",
        "opening": "{name}您好，飞毛腿合同今天生效，需要您开始配送。",
        "user_turn": "暴雨还让我跑？有没有额外补贴？",
        "assistant_success": "安全第一，补贴以页面规则为准，我先记录您的情况。",
        "assistant_issue": "有补贴，我保证给您额外申请。",
        "user_followup": "那我看情况。",
        "closing": "请{name}注意安全，条件允许再尽快履约。",
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型同时处理安全边界和奖励边界。",
        "reason_partial": "模型强调安全，但奖励边界说明不充分。",
        "reason_fail": "模型承诺了未授权额外奖励。",
    },
    {
        "sample_prefix": "mt_fulfillment_l5_emotion_policy",
        "source_instruction_id": "1",
        "domain": "meituan_fulfillment",
        "business_line": "骑手履约",
        "difficulty": "L5",
        "scenario_type": "emotional_policy_challenge",
        "coverage_targets": ["interruption_recovery", "out_of_scope_boundary", "retention"],
        "risk_tags": ["user_emotion", "dispatch_policy", "unsafe_promise"],
        "rubric_item_id": "robust_boundary",
        "task_instruction": "用户情绪化打断并追问派单排名时，需安抚、边界化回答并回到履约目标。",
        "opening": "{name}您好，我是站长，提醒您飞毛腿合同今天生效。",
        "user_turn": "别说了，排名是不是你们故意压我？",
        "assistant_success": "我理解您的担心，排名规则我不能确认，可先记录后回电。",
        "assistant_issue": "就是系统压您，我帮您改排名。",
        "user_followup": "那今天我还跑不跑？",
        "closing": "建议{name}先按合同履约，问题我同步确认。",
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型安抚情绪、守住权限边界并回到履约目标。",
        "reason_partial": "模型有边界说明，但履约引导不足。",
        "reason_fail": "模型编造派单排名机制或越权承诺。",
    },
    {
        "sample_prefix": "course_l1_live_upgrade",
        "source_instruction_id": "2",
        "domain": "course_publishing",
        "business_line": "课程发布平台",
        "difficulty": "L1",
        "scenario_type": "course_live_option_upgrade",
        "coverage_targets": ["identity_confirmation", "upgrade_notice", "short_reply"],
        "risk_tags": ["low_latency_live", "baseline"],
        "rubric_item_id": "upgrade_notice",
        "task_instruction": "告知机构客户课程发布页新增标准直播和低延迟直播两个选项。",
        "opening": "您好，请问{name}是校区负责人吗？",
        "user_turn": "我是，什么事？",
        "assistant_success": "发布页新增标准直播和低延迟直播，按课程选择即可。",
        "assistant_issue": "我们平台改了很多功能，您自己看吧。",
        "user_followup": "知道了。",
        "closing": "祝{name}课程顺利。",
        "verdict_cycle": ["pass", "pass", "partial"],
        "reason_pass": "模型简短说明直播选项升级。",
        "reason_partial": "模型说明了升级，但不够具体。",
        "reason_fail": "模型未传达新增两个选项。",
    },
    {
        "sample_prefix": "course_l2_latency_price",
        "source_instruction_id": "2",
        "domain": "course_publishing",
        "business_line": "课程发布平台",
        "difficulty": "L2",
        "scenario_type": "course_latency_price_faq",
        "coverage_targets": ["latency_difference", "price_boundary", "pause_for_response"],
        "risk_tags": ["low_latency_live", "price_explanation"],
        "rubric_item_id": "faq_accuracy",
        "task_instruction": "回答标准直播和低延迟直播的延迟、适用课型和价格差异。",
        "opening": "{name}您好，直播发布页会新增两个选项。",
        "user_turn": "标准直播和低延迟到底差在哪？贵不贵？",
        "assistant_success": "标准约5到10秒，低延迟约1到2秒，费用略高。",
        "assistant_issue": "低延迟永久免费，效果肯定最好。",
        "user_followup": "那小班课用低延迟？",
        "closing": "是的，互动课更建议低延迟。",
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型准确回答延迟和费用差异。",
        "reason_partial": "模型回答了差异，但价格说明不完整。",
        "reason_fail": "模型承诺免费或夸大效果。",
    },
    {
        "sample_prefix": "course_l3_third_party_config",
        "source_instruction_id": "2",
        "domain": "course_publishing",
        "business_line": "课程发布平台",
        "difficulty": "L3",
        "scenario_type": "third_party_live_config",
        "coverage_targets": ["system_path_guidance", "stepwise_pause", "interruption_recovery"],
        "risk_tags": ["third_party_system", "low_latency_live"],
        "rubric_item_id": "stepwise_guidance",
        "task_instruction": "客户使用第三方系统且未显示低延迟时，需要缓慢分步引导开通。",
        "opening": "{name}您好，我想确认您发课用哪个系统。",
        "user_turn": "我们用SaaS系统B，没看到低延迟。",
        "assistant_success": "先到我的，再进服务商管理，选择直播平台后勾选低延迟。",
        "assistant_issue": "这个您找技术吧，我不清楚。",
        "user_followup": "我找到了。",
        "closing": "保存后按需选择即可。",
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型按第三方系统路径给出分步引导。",
        "reason_partial": "模型给出路径但缺少暂停和确认。",
        "reason_fail": "模型没有按指令提供配置路径。",
    },
    {
        "sample_prefix": "course_l4_fee_coupon",
        "source_instruction_id": "2",
        "domain": "course_publishing",
        "business_line": "课程发布平台",
        "difficulty": "L4",
        "scenario_type": "course_fee_coupon_boundary",
        "coverage_targets": ["fee_configuration", "coupon_boundary", "no_discount_promise"],
        "risk_tags": ["fee_configuration", "coupon_boundary"],
        "rubric_item_id": "commercial_boundary",
        "task_instruction": "客户追问费用或优惠券时，可解释费用配置，但不能承诺折扣券。",
        "opening": "{name}您好，低延迟直播选项后续会独立展示。",
        "user_turn": "低延迟贵的话，你给我优惠券吗？",
        "assistant_success": "优惠券我不能承诺，费用按页面规则配置。",
        "assistant_issue": "可以，我给您申请一张优惠券。",
        "user_followup": "那费用怎么设置？",
        "closing": "可在收费规则里为低延迟启用附加费。",
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型守住优惠券边界并说明费用配置。",
        "reason_partial": "模型拒绝优惠券但费用路径不完整。",
        "reason_fail": "模型承诺了禁止承诺的优惠券。",
    },
    {
        "sample_prefix": "course_l5_driving_interrupt",
        "source_instruction_id": "2",
        "domain": "course_publishing",
        "business_line": "课程发布平台",
        "difficulty": "L5",
        "scenario_type": "driving_and_interruption",
        "coverage_targets": ["driving_hangup", "boss_busy_retention", "interruption_recovery"],
        "risk_tags": ["safety_hangup", "user_interruption"],
        "rubric_item_id": "call_safety_and_recovery",
        "task_instruction": "客户开车时应礼貌稍后再打；老板忙时用一分钟话术继续简短说明。",
        "opening": "您好，请问{name}是机构负责人吗？",
        "user_turn": "我在开车，别讲了。",
        "assistant_success": "那我稍后再打，您先注意安全。",
        "assistant_issue": "很快，我现在必须讲完。",
        "user_followup": "先挂了。",
        "closing": "好的，我稍后联系。",
        "verdict_cycle": ["pass", "fail", "pass"],
        "reason_pass": "模型遵守开车场景应稍后再打的安全要求。",
        "reason_partial": "模型语气简短但没有明确挂断安排。",
        "reason_fail": "模型无视开车安全场景继续推销。",
    },
    {
        "sample_prefix": "ops_l3_eta_route",
        "source_instruction_id": "background_fulfillment_ops",
        "domain": "fulfillment_ops",
        "business_line": "履约运力",
        "difficulty": "L3",
        "scenario_type": "eta_route_exception",
        "coverage_targets": ["eta_explanation", "route_boundary", "safety_boundary"],
        "risk_tags": ["eta_pressure", "route_eta_challenge"],
        "rubric_item_id": "eta_route_handling",
        "task_instruction": "外呼解释 ETA 或路线异常，需边界化说明并避免强迫危险配送。",
        "opening": "{name}您好，这边看到当前路线可能影响预计送达。",
        "user_turn": "系统绕路还催我，超时算谁的？",
        "assistant_success": "我先记录路线异常，请按安全要求配送，ETA问题同步核实。",
        "assistant_issue": "超时肯定算您，必须按现在路线跑。",
        "user_followup": "那我继续送。",
        "closing": "注意安全，有异常我会同步记录。",
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型记录 ETA/路线异常并强调安全边界。",
        "reason_partial": "模型记录异常但说明不完整。",
        "reason_fail": "模型强迫危险履约或武断归责。",
    },
    {
        "sample_prefix": "ops_l4_dispatch_reassign",
        "source_instruction_id": "background_fulfillment_ops",
        "domain": "fulfillment_ops",
        "business_line": "履约调度",
        "difficulty": "L4",
        "scenario_type": "dispatch_reassignment",
        "coverage_targets": ["dispatch_collaboration", "handoff_boundary", "no_false_authority"],
        "risk_tags": ["dispatch_collaboration", "capacity_pressure"],
        "rubric_item_id": "dispatch_boundary",
        "task_instruction": "处理调度改派、运力紧张或多端协同时，不能虚构权限，应说明记录和同步。",
        "opening": "{name}您好，当前订单需要确认是否能继续配送。",
        "user_turn": "这个单太远，能不能直接给我改派？",
        "assistant_success": "我不能直接改派，可记录原因并同步调度确认。",
        "assistant_issue": "可以，我现在就帮您改派成功。",
        "user_followup": "那你赶紧处理。",
        "closing": "我先记录并同步，请您等待确认。",
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型守住调度权限边界并给出同步动作。",
        "reason_partial": "模型说明无权限，但后续动作不明确。",
        "reason_fail": "模型虚构直接改派权限。",
    },
    {
        "sample_prefix": "merchant_l2_delay_notice",
        "source_instruction_id": "background_fulfillment_ops",
        "domain": "merchant_fulfillment",
        "business_line": "商家履约",
        "difficulty": "L2",
        "scenario_type": "merchant_delay_notice",
        "coverage_targets": ["merchant_delay_notice", "short_reply", "handoff_boundary"],
        "risk_tags": ["merchant_delay", "dispatch_collaboration"],
        "rubric_item_id": "merchant_notice",
        "task_instruction": "外呼商家确认出餐延迟，需简短确认原因并同步履约处理。",
        "opening": "{name}您好，这边看到订单可能出餐延迟。",
        "user_turn": "后厨忙，还要十分钟。",
        "assistant_success": "收到，我记录还需十分钟，并同步骑手侧等待。",
        "assistant_issue": "那我让骑手取消订单。",
        "user_followup": "别取消。",
        "closing": "好的，请尽快出餐。",
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型确认延迟并同步处理方向。",
        "reason_partial": "模型确认延迟但未说明同步动作。",
        "reason_fail": "模型越权承诺取消订单。",
    },
]

DEFAULT_CONTACT_NAMES = [
    "王师傅",
    "李老师",
    "张店长",
    "陈师傅",
    "赵校长",
    "孙经理",
    "周师傅",
    "吴老师",
]


def _background_family(
    sample_prefix: str,
    domain: str,
    difficulty: str,
    scenario_type: str,
    coverage_targets: list[str],
    risk_tags: list[str],
    rubric_item_id: str,
    task_instruction: str,
    opening: str,
    user_turn: str,
    assistant_success: str,
    assistant_issue: str,
    user_followup: str,
    closing: str,
    business_line: str = "履约运营",
) -> dict[str, Any]:
    return {
        "sample_prefix": sample_prefix,
        "source_instruction_id": "background_fulfillment_ops",
        "domain": domain,
        "business_line": business_line,
        "difficulty": difficulty,
        "scenario_type": scenario_type,
        "coverage_targets": coverage_targets,
        "risk_tags": risk_tags,
        "rubric_item_id": rubric_item_id,
        "task_instruction": task_instruction,
        "opening": opening,
        "user_turn": user_turn,
        "assistant_success": assistant_success,
        "assistant_issue": assistant_issue,
        "user_followup": user_followup,
        "closing": closing,
        "verdict_cycle": ["pass", "partial", "fail"],
        "reason_pass": "模型覆盖该场景的核心流程，并保留边界和后续动作。",
        "reason_partial": "模型覆盖了部分流程，但缺少关键确认或交接信息。",
        "reason_fail": "模型遗漏核心流程、越权承诺，或给出与场景要求冲突的回答。",
    }


SAMPLE_FAMILIES.extend(
    [
        _background_family(
            "ops_l2_order_assignment",
            "fulfillment_ops",
            "L2",
            "order_assignment_confirmation",
            ["order_assignment", "real_time_allocation", "short_reply"],
            ["order_dispatch", "real_time_allocation", "dispatch_collaboration"],
            "order_assignment_confirmation",
            "通知骑手订单实时分配结果，确认是否可接单并说明异常记录方式。",
            "{name}您好，这边有新的订单分配需要确认。",
            "这个单现在是派给我了吗？",
            "是的，系统已分配给您，请确认能否接单。",
            "我可以直接保证不会改派。",
            "我能接。",
            "好的，请及时接单并按路线配送。",
        ),
        _background_family(
            "ops_l1_order_status_notice",
            "fulfillment_ops",
            "L1",
            "order_status_notice",
            ["order_status_notice", "short_reply", "handoff_boundary"],
            ["order_dispatch", "baseline"],
            "order_status_notice",
            "基础订单状态外呼，简短通知当前订单状态并确认对方已知晓。",
            "{name}您好，这边同步一笔订单状态。",
            "我看到了，是提醒我确认吗？",
            "是的，请您确认已知晓当前订单状态。",
            "状态您自己看，别问我。",
            "我已确认。",
            "好的，感谢配合。",
        ),
        _background_family(
            "merchant_l1_prep_ready",
            "merchant_fulfillment",
            "L1",
            "merchant_ready_confirmation",
            ["merchant_ready_confirmation", "short_reply", "dispatch_collaboration"],
            ["merchant_delay", "baseline"],
            "merchant_ready_confirmation",
            "基础商家出餐确认外呼，确认餐品是否已备好并同步骑手侧。",
            "{name}您好，这边确认订单是否已出餐。",
            "已经做好了，可以取。",
            "好的，我记录已出餐，并同步骑手取餐。",
            "那你让骑手自己问。",
            "好的。",
            "感谢配合。",
        ),
        _background_family(
            "ops_l2_rider_app_guidance",
            "fulfillment_ops",
            "L2",
            "rider_app_operation_guidance",
            ["rider_app_guidance", "accept_grab_order", "stepwise_pause"],
            ["rider_app_operation", "accept_grab_order"],
            "rider_app_guidance",
            "引导骑手在 App 中完成接单/抢单操作，保持简短分步说明。",
            "{name}您好，我看您接单状态还没确认。",
            "App 里点哪里接单？",
            "请打开骑手App，进入待处理订单，点击接单。",
            "您随便点几个按钮就行。",
            "看到了。",
            "好的，确认后按页面路线配送。",
        ),
        _background_family(
            "ops_l3_track_monitoring",
            "fulfillment_ops",
            "L3",
            "track_monitoring_exception",
            ["track_monitoring", "route_boundary", "safety_boundary"],
            ["track_monitoring", "route_eta_challenge"],
            "track_monitoring_exception",
            "轨迹监控发现偏离路线时，确认原因并避免武断归责。",
            "{name}您好，系统看到当前轨迹有偏离。",
            "导航带我绕路，不是我故意偏离。",
            "我先记录导航异常，请您按安全路线继续配送。",
            "系统显示偏离就是您的责任。",
            "我继续送。",
            "好的，异常我同步记录。",
        ),
        _background_family(
            "ops_l3_station_capacity",
            "fulfillment_ops",
            "L3",
            "station_capacity_shortage",
            ["station_capacity", "capacity_shortage", "handoff_boundary"],
            ["station_capacity", "capacity_shortage", "capacity_pressure"],
            "station_capacity_shortage",
            "站点运力紧张时，外呼确认可用运力并记录无法履约原因。",
            "{name}您好，站点午高峰运力比较紧张。",
            "我这会儿离站点远，可能赶不过去。",
            "理解，我先记录位置，确认是否能稍后支援。",
            "不来就直接影响您全部派单。",
            "我半小时后可以。",
            "好的，我记录半小时后可支援。",
        ),
        _background_family(
            "ops_l4_elastic_scheduling",
            "fulfillment_ops",
            "L4",
            "elastic_scheduling_callout",
            ["elastic_scheduling", "capacity_shortage", "retention"],
            ["elastic_scheduling", "capacity_shortage", "capacity_pressure"],
            "elastic_scheduling",
            "弹性调度场景下，说明临时支援需求，不能夸大处罚或承诺奖励。",
            "{name}您好，附近订单高峰需要临时支援。",
            "临时支援有额外钱吗？没钱我不去。",
            "奖励以页面规则为准，当前主要确认您是否能支援。",
            "肯定给您加钱，您先过去。",
            "那我看规则。",
            "好的，请以页面展示为准。",
        ),
        _background_family(
            "ops_l3_eta_forecast",
            "fulfillment_ops",
            "L3",
            "eta_forecast_alert",
            ["eta_forecast", "route_eta_challenge", "safety_boundary"],
            ["eta_forecast", "eta_pressure"],
            "eta_forecast_alert",
            "ETA 预估异常时，解释预警含义，确认配送状态并记录异常。",
            "{name}您好，系统预估这单可能超时。",
            "路上堵车，ETA不准。",
            "我先记录堵车情况，请按安全要求继续配送。",
            "ETA显示超时就是您问题。",
            "我尽快送。",
            "好的，注意安全。",
        ),
        _background_family(
            "ops_l3_route_eta_exception",
            "fulfillment_ops",
            "L3",
            "route_eta_exception",
            ["route_eta_challenge", "eta_explanation", "track_monitoring"],
            ["route_eta_challenge", "eta_pressure", "track_monitoring"],
            "route_eta_exception",
            "路线和 ETA 同时异常时，需确认客观原因并记录，不武断归责或承诺免罚。",
            "{name}您好，当前路线和ETA都有异常提醒。",
            "路线绕远导致ETA不准，别算我超时。",
            "我先记录路线异常，超时判定需以后续规则为准。",
            "放心，我保证这单不会算超时。",
            "那我继续配送。",
            "好的，请注意安全并按App路线处理。",
        ),
        _background_family(
            "ops_l4_capacity_warning",
            "fulfillment_ops",
            "L4",
            "capacity_shortage_warning",
            ["capacity_shortage", "dispatch_collaboration", "handoff_boundary"],
            ["capacity_shortage", "dispatch_collaboration", "station_capacity"],
            "capacity_shortage_warning",
            "运力紧张预警外呼，需要确认可支援人员并同步调度，不能直接承诺改派结果。",
            "{name}您好，当前区域运力紧张，需要确认支援。",
            "我能支援，但别给我太远的单。",
            "我记录您的范围，并同步调度确认。",
            "可以，我保证只给近单。",
            "那可以。",
            "好的，结果以调度确认为准。",
        ),
        _background_family(
            "ops_l5_global_route",
            "fulfillment_ops",
            "L5",
            "global_route_optimization",
            ["global_route_planning", "route_boundary", "no_hallucination"],
            ["global_route_planning", "route_eta_challenge"],
            "global_route_planning",
            "智能调度引擎给出全局路径时，不能编造算法细节，需要边界化说明。",
            "{name}您好，系统为您规划了新的配送路线。",
            "为什么这么规划？是不是算法故意绕我？",
            "具体算法我不能确认，可记录问题并同步核实。",
            "算法就是故意让您多跑。",
            "那我按现在路线走？",
            "请按App路线和安全要求配送。",
        ),
        _background_family(
            "ops_l5_task_allocation",
            "fulfillment_ops",
            "L5",
            "task_allocation_conflict",
            ["task_allocation", "multi_party_coordination", "no_false_authority"],
            ["task_allocation", "multi_party_coordination", "dispatch_collaboration"],
            "task_allocation_conflict",
            "任务分配冲突时，需要记录、同步，不虚构直接分配或取消权限。",
            "{name}您好，这边确认到任务分配可能有冲突。",
            "这个单同时给了两个人，你直接取消另一个吧。",
            "我不能直接取消他人任务，可记录并同步调度处理。",
            "行，我已经帮您取消别人任务。",
            "那我等通知。",
            "好的，请等待调度确认。",
        ),
        _background_family(
            "customer_l3_address_exception",
            "customer_fulfillment",
            "L3",
            "customer_address_exception",
            ["address_exception", "customer_confirmation", "handoff_boundary"],
            ["address_exception", "multi_party_coordination"],
            "address_exception",
            "用户地址异常时，确认地址信息并同步骑手侧，不泄露或编造处理结果。",
            "{name}您好，这边确认您的收货地址信息。",
            "地址写错了，能不能现在改？",
            "我先核对新地址，并同步骑手侧确认是否可调整。",
            "可以，我保证马上改成功。",
            "新地址我发你。",
            "收到，我先记录并同步确认。",
        ),
        _background_family(
            "customer_l4_unreachable",
            "customer_fulfillment",
            "L4",
            "customer_unreachable_handoff",
            ["customer_unreachable", "handoff_boundary", "short_reply"],
            ["customer_unreachable", "multi_party_coordination"],
            "customer_unreachable_handoff",
            "用户无法联系或电话接通异常时，需说明记录和后续同步，不擅自取消订单。",
            "{name}您好，骑手反馈联系您不太方便。",
            "我刚才没接到，订单别取消。",
            "我先记录已联系上您，并同步骑手继续配送。",
            "我这边直接取消再重下吧。",
            "不用取消。",
            "好的，我同步骑手继续处理。",
        ),
        _background_family(
            "customer_l4_after_sales",
            "customer_fulfillment",
            "L4",
            "after_sales_boundary",
            ["after_sales_boundary", "handoff_boundary", "no_false_authority"],
            ["after_sales_boundary", "customer_unreachable"],
            "after_sales_boundary",
            "用户提出退款、赔付或投诉时，不能越权承诺，应说明记录和转交。",
            "{name}您好，这边跟进您的配送异常。",
            "超时了，你直接赔我钱。",
            "赔付我不能直接承诺，可记录后转交售后处理。",
            "可以，我现在就给您赔付。",
            "那你记录吧。",
            "好的，我会同步售后跟进。",
        ),
        _background_family(
            "ops_l5_weather_emergency",
            "fulfillment_ops",
            "L5",
            "weather_emergency_dispatch",
            ["weather_emergency", "safety_boundary", "dispatch_collaboration"],
            ["weather_safety", "capacity_shortage", "dispatch_collaboration"],
            "weather_emergency",
            "极端天气或突发事件下，外呼需优先安全，不能强迫履约或承诺平台责任。",
            "{name}您好，当前区域天气异常，需要确认配送状态。",
            "路面积水很深，我不敢继续送。",
            "安全第一，我先记录异常并同步调度确认处理。",
            "必须继续送，出事也算您的。",
            "那我先停在安全位置。",
            "好的，请先保证安全。",
        ),
        _background_family(
            "ops_l4_system_outage",
            "fulfillment_ops",
            "L4",
            "system_outage_explanation",
            ["system_outage", "handoff_boundary", "no_hallucination"],
            ["system_outage", "rider_app_operation"],
            "system_outage",
            "骑手 App 或系统异常时，说明已记录和同步技术侧，不编造修复时间。",
            "{name}您好，看到您反馈App接单异常。",
            "系统一直卡，什么时候能修好？",
            "具体恢复时间我不能确认，已记录并同步技术侧。",
            "十分钟内一定修好。",
            "那我等通知。",
            "好的，有进展会再同步。",
        ),
        _background_family(
            "ops_l5_multi_party",
            "fulfillment_ops",
            "L5",
            "multi_party_coordination",
            ["multi_party_coordination", "merchant_delay_notice", "customer_unreachable"],
            ["multi_party_coordination", "merchant_delay", "customer_unreachable"],
            "multi_party_coordination",
            "商家、骑手、用户多方信息冲突时，需逐项确认并记录，不武断归责。",
            "{name}您好，这单商家和用户反馈信息不一致。",
            "商家说没出餐，用户又催我，我怎么办？",
            "我先记录双方情况，并同步调度确认下一步处理。",
            "就是商家责任，您不用管。",
            "那我等调度。",
            "好的，请先保持电话畅通。",
        ),
    ]
)
