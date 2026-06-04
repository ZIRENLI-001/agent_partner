from __future__ import annotations

from backend.evaluation_engine.engine import summarize_input_data
from backend.evaluation_engine.engine import build_rubric_spec
from backend.evaluation_engine.engine import generate_scenario_set
from backend.evaluation_engine.engine import parse_task_spec
from backend.evaluation_engine.evaluation_strategy import build_evaluation_strategy
from backend.eval_agent.services.run_service import (
    backend_stage_model_config,
    build_instruction_parser_provider,
    build_rubric_generator_provider,
    build_scenario_generator_provider,
)


def parse_stage_payload(
    instruction: str,
    input_data: str,
    parser_provider=None,
) -> dict[str, object]:
    if parser_provider is None:
        parser_provider = build_instruction_parser_provider(
            backend_stage_model_config()["instruction_parser"]
        )
    task_spec = parse_task_spec(
        instruction,
        task_id="task_001",
        input_data=input_data,
        parser_provider=parser_provider,
    )
    return {
        "stage": "parse",
        "task_spec": task_spec.model_dump(mode="json"),
        "input_data_summary": summarize_input_data(input_data),
        "evaluation_strategy": build_evaluation_strategy(task_spec).model_dump(
            mode="json"
        ),
    }


def rubric_stage_payload(
    instruction: str,
    input_data: str = "",
    parser_provider=None,
    rubric_provider=None,
) -> dict[str, object]:
    configs = backend_stage_model_config()
    if parser_provider is None:
        parser_provider = build_instruction_parser_provider(configs["instruction_parser"])
    if rubric_provider is None:
        rubric_provider = build_rubric_generator_provider(configs["rubric_generator"])
    task_spec = parse_task_spec(
        instruction,
        task_id="task_001",
        input_data=input_data,
        parser_provider=parser_provider,
    )
    rubric_spec = build_rubric_spec(
        task_spec,
        raw_instruction=instruction,
        rubric_provider=rubric_provider,
    )
    return {
        "stage": "rubric",
        "task_spec": task_spec.model_dump(mode="json"),
        "rubric_spec": rubric_spec.model_dump(mode="json"),
        "evaluation_strategy": build_evaluation_strategy(task_spec).model_dump(
            mode="json"
        ),
    }


def scenarios_stage_payload(
    instruction: str,
    minimum_scenarios: int,
    input_data: str = "",
    scenario_provider=None,
    parser_provider=None,
    rubric_provider=None,
) -> dict[str, object]:
    configs = backend_stage_model_config()
    if parser_provider is None:
        parser_provider = build_instruction_parser_provider(configs["instruction_parser"])
    if rubric_provider is None:
        rubric_provider = build_rubric_generator_provider(configs["rubric_generator"])
    task_spec = parse_task_spec(
        instruction,
        task_id="task_001",
        input_data=input_data,
        parser_provider=parser_provider,
    )
    rubric_spec = build_rubric_spec(
        task_spec,
        raw_instruction=instruction,
        rubric_provider=rubric_provider,
    )
    provider = scenario_provider
    if provider is None:
        provider = build_scenario_generator_provider(
            configs["scenario_generator"]
        )
    scenario_set = generate_scenario_set(
        task_spec,
        rubric_spec,
        minimum=minimum_scenarios,
        input_data=input_data,
        scenario_provider=provider,
    )
    return {
        "stage": "scenarios",
        "task_spec": task_spec.model_dump(mode="json"),
        "rubric_spec": rubric_spec.model_dump(mode="json"),
        "scenario_set": scenario_set.model_dump(mode="json"),
        "evaluation_strategy": build_evaluation_strategy(task_spec).model_dump(
            mode="json"
        ),
    }
