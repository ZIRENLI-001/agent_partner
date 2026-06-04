from backend.evaluation_engine.instruction_parser import parse_instruction
from backend.evaluation_engine.engine import parse_task_spec
from backend.evaluation_engine.rubric_builder import build_rubric


RAW_TASK = """# Role
你是美团外卖骑手的站长。

# Task
致电"飞毛腿"骑手，通知他们今天合同已成功签署，并提醒他们完成配送任务。

# Opening Line
你好，请问是${rider_name}吗？我是站长。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效，并询问他们是否可以开始配送。
2. 说明单日飞毛腿合同需要连续 Y 天完成配送；否则合同将受到影响。
3. 尽量挽留不想配送的骑手，鼓励能配送的骑手，并提醒他们注意安全。

# Knowledge Points (FAQ)
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的"飞毛腿报名"中取消；次日生效。

# Constraints
- 保持语气随意，像打电话一样自然。
- 每次回复控制在约 30 个字以内。
- 如被问及超出职责范围的问题，回复："我向同事确认后再回电给你。我现在能回答的先回答。"
"""


def test_parse_instruction_extracts_core_sections():
    spec = parse_instruction(RAW_TASK, task_id="task_001")

    assert spec.role == "美团外卖骑手的站长"
    assert "合同已成功签署" in spec.task_goal
    assert spec.opening_line.startswith("你好，请问是")
    assert len(spec.required_steps) == 3
    assert any("30" in item for item in spec.constraints)
    assert spec.faq[0]["intent"] == "退出飞毛腿"
    assert spec.edge_cases[0]["trigger"] == "不想配送"


def test_parse_task_spec_uses_unclear_imported_sample_context_without_overriding_key_instruction():
    raw_task = """# Role
你是履约客服。

# Task
处理导入样本中的订单异常。

# Opening Line
您好，这边确认订单情况。
"""
    input_data = """
{
  "case_name": "地址异常样本",
  "scenario_type": "customer_address_exception",
  "coverage_targets": ["address_exception", "handoff_boundary"],
  "risk_tags": ["address_exception"],
  "input_variables": {
    "old_address": "A小区1号楼",
    "new_address": "B小区2号楼"
  },
  "expected_labels": [
    {"rubric_item_id": "address_exception", "expected_reason": "核实新旧地址并同步调度确认"}
  ]
}
"""

    spec = parse_task_spec(
        raw_task,
        task_id="task_address",
        input_data=input_data,
        parser_provider=None,
    )

    assert spec.role == "履约客服"
    assert spec.opening_line == "您好，这边确认订单情况。"
    assert any("address_exception" in item for item in spec.required_steps)
    assert any("handoff_boundary" in item for item in spec.required_steps)
    assert any(edge["trigger"] == "customer_address_exception" for edge in spec.edge_cases)
    assert any("A小区1号楼" in edge["expected_behavior"] for edge in spec.edge_cases)


def test_parse_task_spec_keeps_comma_separated_sample_targets_as_labels():
    raw_task = """# Role
你是履约客服。

# Task
处理导入样本中的订单通知。

# Opening Line
您好，这边同步订单情况。
"""
    input_data = """
{
  "case_name": "订单状态通知",
  "scenario_type": "order_status_notice",
  "coverage_targets": "order_status_notice,short_reply,handoff_boundary",
  "risk_tags": "order_dispatch,basic_handoff",
  "input_variables": {
    "order_id": "A123",
    "coverage_targets": "nested_target_should_not_split"
  },
  "expected_labels": []
}
"""

    spec = parse_task_spec(
        raw_task,
        task_id="task_order_notice",
        input_data=input_data,
        parser_provider=None,
    )

    assert "覆盖导入样本目标：order_status_notice" in spec.required_steps
    assert "覆盖导入样本目标：short_reply" in spec.required_steps
    assert "覆盖导入样本目标：handoff_boundary" in spec.required_steps
    assert "覆盖导入样本目标：o" not in spec.required_steps
    assert any(
        edge["trigger"] == "order_status_notice"
        and "order_dispatch、basic_handoff" in edge["expected_behavior"]
        for edge in spec.edge_cases
    )


def test_parse_instruction_prioritizes_raw_task_unwilling_to_deliver_edge_case():
    raw_task = """# Role
你是美团外卖骑手的站长。

# Task
致电"飞毛腿"骑手，通知合同已成功签署，并处理不想配送的情况。

# Opening Line
你好，请问是${rider_name}吗？我是站长。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效。
2. 说明单日飞毛腿合同需要连续 Y 天完成配送。

# Knowledge Points (FAQ)
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的"飞毛腿报名"中取消；次日生效。

# Constraints
- 如被问及超出职责范围的问题，回复："我向同事确认后再回电给你。我现在能回答的先回答。"
"""

    spec = parse_instruction(raw_task, task_id="task_002")

    assert spec.edge_cases[0]["trigger"] == "不想配送"


def test_build_rubric_contains_sources_and_mixed_check_types():
    spec = parse_instruction(RAW_TASK, task_id="task_001")
    rubric = build_rubric(spec)

    assert rubric.task_id == "task_001"
    assert len(rubric.items) >= 6
    assert all(item.source for item in rubric.items)
    assert any(item.check_type == "rule" for item in rubric.items)
    assert any(item.check_type == "semantic" for item in rubric.items)
    assert any(item.critical for item in rubric.items)
