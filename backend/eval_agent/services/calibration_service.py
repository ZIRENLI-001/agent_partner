from __future__ import annotations

from backend.evaluation_engine.calibration_dataset import (
    calibration_payload,
    load_calibration_dataset,
    summarize_calibration_dataset,
)
from backend.evaluation_engine.calibration_benchmark import (
    compare_evaluator_output_to_expected_labels,
)


def calibration_summary_payload() -> dict[str, object]:
    return summarize_calibration_dataset(load_calibration_dataset())


def calibration_samples_payload() -> dict[str, object]:
    return calibration_payload()


def calibration_self_check_payload() -> dict[str, object]:
    dataset = load_calibration_dataset()
    return compare_evaluator_output_to_expected_labels(dataset, {})
