from backend.evaluation_engine.calibration_dataset import load_calibration_dataset, summarize_calibration_dataset


def test_meituan_calibration_dataset_has_difficulty_and_label_coverage():
    dataset = load_calibration_dataset()
    summary = summarize_calibration_dataset(dataset)

    assert summary["sample_count"] == 1000
    assert set(summary["difficulty_counts"]) >= {"L1", "L2", "L3", "L4", "L5"}
    assert min(summary["difficulty_counts"].values()) >= 100
    assert summary["label_counts"]["pass"] > 0
    assert summary["label_counts"]["fail"] > 0
    assert summary["evidence_coverage_rate"] == 1.0


def test_calibration_dataset_contains_multiple_outbound_domains():
    dataset = load_calibration_dataset()
    domains = {sample["domain"] for sample in dataset}
    source_ids = {sample["source_instruction_id"] for sample in dataset}
    risk_tags = {tag for sample in dataset for tag in sample["risk_tags"]}
    scenario_types = {sample["scenario_type"] for sample in dataset}

    assert {"meituan_fulfillment", "course_publishing"}.issubset(domains)
    assert {"1", "2", "background_fulfillment_ops"}.issubset(source_ids)
    assert "capacity_pressure" in risk_tags
    assert "route_eta_challenge" in risk_tags
    assert "contract_compliance" in risk_tags
    assert "extra_reward_boundary" in risk_tags
    assert "low_latency_live" in risk_tags
    assert "eta_pressure" in risk_tags
    assert "dispatch_collaboration" in risk_tags
    assert "rider_refusal" in scenario_types
    assert "normal_confirmation" in scenario_types
    assert "course_live_option_upgrade" in scenario_types
    assert "eta_route_exception" in scenario_types
    assert "dispatch_reassignment" in scenario_types


def test_calibration_dataset_covers_background_fulfillment_taxonomy():
    dataset = load_calibration_dataset()
    risk_tags = {tag for sample in dataset for tag in sample["risk_tags"]}
    scenario_types = {sample["scenario_type"] for sample in dataset}

    required_scenarios = {
        "order_assignment_confirmation",
        "rider_app_operation_guidance",
        "track_monitoring_exception",
        "station_capacity_shortage",
        "elastic_scheduling_callout",
        "eta_forecast_alert",
        "capacity_shortage_warning",
        "global_route_optimization",
        "task_allocation_conflict",
        "merchant_delay_notice",
        "customer_address_exception",
        "customer_unreachable_handoff",
        "after_sales_boundary",
        "weather_emergency_dispatch",
        "system_outage_explanation",
        "multi_party_coordination",
        "route_eta_exception",
        "dispatch_reassignment",
        "course_live_option_upgrade",
        "third_party_live_config",
        "course_fee_coupon_boundary",
    }
    required_risks = {
        "order_dispatch",
        "real_time_allocation",
        "rider_app_operation",
        "accept_grab_order",
        "track_monitoring",
        "station_capacity",
        "elastic_scheduling",
        "eta_forecast",
        "capacity_shortage",
        "global_route_planning",
        "task_allocation",
        "multi_party_coordination",
        "merchant_delay",
        "customer_unreachable",
        "address_exception",
        "after_sales_boundary",
        "weather_safety",
        "system_outage",
        "low_latency_live",
        "third_party_system",
        "fee_configuration",
        "coupon_boundary",
    }

    assert required_scenarios.issubset(scenario_types)
    assert required_risks.issubset(risk_tags)


def test_calibration_samples_have_dialogue_labels_and_score_bands():
    dataset = load_calibration_dataset()

    for sample in dataset:
        turn_ids = {turn["turn_id"] for turn in sample["dialogue"]}
        assert sample["source_instruction_id"]
        assert sample["domain"]
        assert sample["task_instruction"]
        assert sample["difficulty"] in {"L1", "L2", "L3", "L4", "L5"}
        assert len(sample["dialogue"]) >= 4
        assert sample["expected_labels"]
        assert sample["expected_score_band"]["min"] <= sample["expected_score_band"]["max"]
        for label in sample["expected_labels"]:
            assert label["expected_verdict"] in {"pass", "partial", "fail", "needs_review"}
            assert label["evidence_turn_ids"]
            assert set(label["evidence_turn_ids"]).issubset(turn_ids)


def test_calibration_expected_labels_align_with_coverage_targets():
    dataset = load_calibration_dataset()
    misaligned = []

    for sample in dataset:
        coverage_targets = set(sample["coverage_targets"])
        for label in sample["expected_labels"]:
            rubric_item_id = label["rubric_item_id"]
            if rubric_item_id == "evidence_traceability":
                continue
            if rubric_item_id not in coverage_targets:
                misaligned.append((sample["sample_id"], rubric_item_id))

    assert misaligned == []


def test_flying_rider_samples_use_complete_contract_instruction_template():
    dataset = load_calibration_dataset()
    rider_samples = [
        sample for sample in dataset if sample["source_instruction_id"] == "1"
    ]

    assert rider_samples
    for sample in rider_samples:
        instruction = sample["task_instruction"]
        variables = sample["input_variables"]
        for section in [
            "# Role",
            "# Task",
            "# Opening Line",
            "# Call Flow",
            "# Knowledge Points (FAQ)",
            "# Constraints",
        ]:
            assert section in instruction
        assert "致电\"飞毛腿\"骑手" in instruction
        assert "午餐和晚餐高峰期需要上线" in instruction
        assert "连续 Y 天" in instruction
        assert "前一天 **Z 点之前**" in instruction
        assert "约 30 个字以内" in instruction
        assert {"rider_name", "X", "Y", "Z", "W", "reward_delta"}.issubset(variables)


def test_all_calibration_samples_use_structured_instruction_format():
    dataset = load_calibration_dataset()

    for sample in dataset:
        instruction = sample["task_instruction"]
        variables = sample["input_variables"]
        for section in [
            "# Role",
            "# Task",
            "# Opening Line",
            "# Call Flow",
            "# Knowledge Points (FAQ)",
            "# Constraints",
        ]:
            assert section in instruction, sample["sample_id"]
        assert "contact_name" in variables or "rider_name" in variables
        assert "scenario_type" in variables
        assert "difficulty" in variables


def test_calibration_summary_exposes_frontend_ready_coverage():
    summary = summarize_calibration_dataset(load_calibration_dataset())

    assert summary["difficulty_counts"]["L5"] >= 1
    assert summary["scenario_type_counts"]["rider_refusal"] >= 1
    assert summary["risk_tag_counts"]["contract_compliance"] >= 1
    assert summary["coverage_targets"]
