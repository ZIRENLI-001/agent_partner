import { request } from "./client";

export interface ModelConfig {
  provider?: string;
  model_name?: string;
  api_base?: string;
  api_key?: string;
  judge_mode?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface RunRequest {
  instruction: string;
  input_data?: string;
  minimum_scenarios?: number;
  model_config?: ModelConfig;
  selected_scenario_ids?: string[];
}

export interface RunSummary {
  run_id: string;
  task_name: string;
  model_name: string;
  pass_rate: number;
  normalized_score?: number;
  normalized_pass_rate?: number;
  scoring_scale?: number;
  scenario_count: number;
  updated_at: number;
}

export interface RunHistoryResponse {
  runs: RunSummary[];
}

export interface ComparisonScenarioRow {
  run_id: string;
  task_name: string;
  task_goal?: string;
  model_name: string;
  scenario_id: string;
  score: number;
  possible_score: number;
  raw_pass_rate: number;
  pass_rate: number;
  normalized_score?: number;
  normalized_pass_rate?: number;
  scoring_scale?: number;
  score_anomaly: boolean;
  status: string;
  critical_failure_count: number;
  updated_at: number;
}

export interface FailureReasonExample {
  run_id: string;
  scenario_id: string;
  model_name: string;
  reason: string;
  rubric_item_id: string;
}

export interface FailureReasonSummary {
  key: string;
  label: string;
  count: number;
  scenario_ids: string[];
  model_names: string[];
  run_ids: string[];
  examples: FailureReasonExample[];
}

export interface RunComparisonResponse {
  runs: RunSummary[];
  scenario_rows: ComparisonScenarioRow[];
  failure_reasons: FailureReasonSummary[];
  optimization_insights: OptimizationInsight[];
  filters: {
    model_names: string[];
    scenario_ids: string[];
    task_names: string[];
  };
}

export interface ScoreSummary {
  total_score: number;
  possible_score: number;
  pass_rate: number;
  raw_total_score?: number;
  raw_possible_score?: number;
  normalized_score?: number;
  normalized_pass_rate?: number;
  scoring_scale?: number;
  scenario_count: number;
  failure_count?: number;
  critical_failure_count?: number;
  quality_gate_status?: string;
  score_reliable?: boolean;
  score_reliability_reason?: string;
}

export interface DimensionSummary {
  dimension: string;
  score: number;
  possible_score: number;
  pass_rate: number;
}

export interface EvidenceItem {
  rubric_item_id: string;
  verdict: string;
  source: string;
  turn_ids: number[];
  reason: string;
  score: number;
  max_score: number;
  instruction_quote?: string;
  expected_behavior?: string;
  actual_behavior?: string;
  explanation?: string;
}

export interface EvaluationResult {
  trace_id: string;
  scenario_id: string;
  total_score: number;
  raw_total_score?: number;
  raw_possible_score?: number;
  normalized_score?: number;
  normalized_pass_rate?: number;
  scoring_scale?: number;
  dimension_scores: Record<string, number>;
  evidence: EvidenceItem[];
  critical_failures: string[];
}

export interface DialogueTurn {
  turn_id: number;
  speaker: string;
  content: string;
}

export interface DialogueTrace {
  trace_id: string;
  scenario_id: string;
  turns: DialogueTurn[];
  termination_reason: string;
  error?: string | null;
}

export interface FailureSummary {
  scenario_id: string;
  rubric_item_id: string;
  verdict: string;
  score: number;
  max_score: number;
  source: string;
  turn_ids: number[];
  reason: string;
  severity: string;
}

export interface OptimizationInsight {
  category: string;
  category_label: string;
  priority: "high" | "medium" | "low" | string;
  title: string;
  decision: string;
  recommended_action: string;
  issue_summary?: string;
  evidence_summary?: string;
  next_action?: string;
  business_context: string;
  sample_task_instruction?: string;
  scenario_ids: string[];
  rubric_item_ids: string[];
  run_ids?: string[];
  model_names?: string[];
  evidence_count: number;
  sample_references: Array<{
    sample_id: string;
    domain: string;
    scenario_type: string;
    difficulty: string;
    coverage_targets?: string[];
    risk_tags?: string[];
  }>;
  examples: Array<{
    run_id?: string;
    model_name?: string;
    scenario_id: string;
    rubric_item_id: string;
    reason: string;
    expected_behavior?: string;
    actual_behavior?: string;
    turn_ids?: number[];
  }>;
}

export interface ScenarioSummary {
  scenario_id: string;
  coverage_targets?: string[];
  expected_test_focus?: string;
  score: number;
  possible_score: number;
  pass_rate: number;
  normalized_score?: number;
  normalized_pass_rate?: number;
  scoring_scale?: number;
  status?: string;
  critical_failures: string[];
}

export interface QualitySummary {
  overall_status: "pass" | "warn" | "fail" | string;
  scenario_coverage?: {
    scenario_count?: number;
    diversity_score?: number;
  };
  judge_integrity?: {
    missing_item_count?: number;
    score_overflow_count?: number;
  };
  evidence_traceability?: {
    traceable_evidence_rate?: number;
  };
  timing_health?: {
    total_duration_ms?: number;
    slow_stages?: unknown[];
  };
  remediation_actions?: Array<{
    stage: string;
    action: string;
    reason: string;
    affected_count?: number;
  }>;
  auto_repair?: {
    attempted?: boolean;
    attempt_count?: number;
    before_status?: string;
    after_status?: string;
    actions?: Array<{
      stage: string;
      action: string;
      reason: string;
      affected_count?: number;
    }>;
  };
}

export interface EnrichedFailureEvidence extends EvidenceItem {
  scenario_id: string;
  severity?: string;
}

export interface RunResponse {
  run_id: string;
  updated_at?: number;
  trace_count: number;
  result_count: number;
  report: string;
  task_spec: Record<string, unknown>;
  rubric_spec: Record<string, unknown>;
  scenario_set: Record<string, unknown>;
  traces: DialogueTrace[];
  results: EvaluationResult[];
  score_summary: ScoreSummary;
  dimension_summary: DimensionSummary[];
  scenario_summary: ScenarioSummary[];
  failure_summary: FailureSummary[];
  optimization_insights?: OptimizationInsight[];
  stage_timings_ms: Record<string, number>;
  stage_diagnostics?: Record<string, Record<string, unknown>>;
  stage_model_config_summary?: Record<string, unknown>;
  quality_summary?: QualitySummary;
}

export interface RunDetailResponse extends RunResponse {
  run_config: Record<string, unknown>;
  model_config_summary: Record<string, unknown>;
}

export interface RunStatusStage {
  key: string;
  name: string;
  status: string;
}

export interface RunSubmitResponse {
  run_id: string;
  status: string;
  status_url: string;
  result_url: string;
}

export interface RunStatusResponse {
  run_id: string;
  status: string;
  current_stage: string;
  stages: RunStatusStage[];
  error?: string;
  result_url?: string;
  updated_at?: number;
}

export function createRun(payload: RunRequest) {
  return request<RunResponse>("/api/runs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function submitRun(payload: RunRequest) {
  return request<RunSubmitResponse>("/api/runs/async", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getRunStatus(runId: string) {
  return request<RunStatusResponse>(`/api/runs/${runId}/status`);
}

export function getRunHistory() {
  return request<RunHistoryResponse>("/api/runs/history");
}

export function getRunComparison() {
  return request<RunComparisonResponse>("/api/runs/comparison");
}

export function getRunDetail(runId: string) {
  return request<RunDetailResponse>(`/api/runs/${runId}`);
}
