import { request } from "./client";

export interface StageRequest {
  instruction: string;
  input_data?: string;
  minimum_scenarios?: number;
}

export interface Scenario {
  scenario_id: string;
  task_id?: string;
  user_profile: Record<string, string>;
  coverage_targets: string[];
  initial_user_intent: string;
  expected_test_focus: string;
  difficulty?: string;
  scenario_type?: string;
  expected_behavior?: string;
  risk_tags?: string[];
}

export interface ScenarioSetPayload {
  suite_id?: string;
  task_id?: string;
  version?: string;
  scenarios: Scenario[];
}

export interface ParseStageResponse {
  stage: "parse";
  task_spec: Record<string, unknown>;
  input_data_summary: Record<string, unknown>;
  evaluation_strategy?: Record<string, unknown>;
}

export interface RubricStageResponse {
  stage: "rubric";
  task_spec: Record<string, unknown>;
  rubric_spec: Record<string, unknown>;
  evaluation_strategy?: Record<string, unknown>;
}

export interface ScenariosStageResponse {
  stage: "scenarios";
  task_spec: Record<string, unknown>;
  rubric_spec: Record<string, unknown>;
  scenario_set: ScenarioSetPayload;
  evaluation_strategy?: Record<string, unknown>;
}

export function parseInstruction(payload: StageRequest) {
  return request<ParseStageResponse>("/api/stages/parse", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function buildRubric(payload: StageRequest) {
  return request<RubricStageResponse>("/api/stages/rubric", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function generateScenarios(payload: StageRequest) {
  return request<ScenariosStageResponse>("/api/stages/scenarios", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
