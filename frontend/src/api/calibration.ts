import { request } from "./client";

export interface CalibrationTurn {
  turn_id: number;
  speaker: string;
  content: string;
}

export interface CalibrationLabel {
  rubric_item_id: string;
  expected_verdict: string;
  expected_reason: string;
  evidence_turn_ids: number[];
  severity: string;
}

export interface CalibrationSample {
  sample_id: string;
  source_instruction_id: string;
  domain: string;
  difficulty: string;
  scenario_type: string;
  coverage_targets: string[];
  risk_tags: string[];
  task_instruction: string;
  input_variables: Record<string, string>;
  dialogue: CalibrationTurn[];
  expected_labels: CalibrationLabel[];
  expected_score_band: {
    min: number;
    max: number;
  };
}

export interface CalibrationSummary {
  dataset_id: string;
  sample_count: number;
  difficulty_counts: Record<string, number>;
  scenario_type_counts: Record<string, number>;
  risk_tag_counts: Record<string, number>;
  label_counts: Record<string, number>;
  coverage_targets: string[];
  evidence_coverage_rate: number;
}

export interface CalibrationSamplesResponse {
  summary: CalibrationSummary;
  samples: CalibrationSample[];
}

export function getCalibrationSamples() {
  return request<CalibrationSamplesResponse>("/api/calibration/samples");
}
