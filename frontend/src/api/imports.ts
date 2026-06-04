import { ApiError } from "./client";

export interface ImportedEvaluationRow {
  caseName: string;
  instruction: string;
  inputData: string;
}

export interface EvaluationRowsImportResponse {
  file_name: string;
  row_count: number;
  rows: ImportedEvaluationRow[];
}

export async function uploadEvaluationRows(file: File): Promise<EvaluationRowsImportResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/import/evaluation-rows", {
    method: "POST",
    body: formData
  });

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || response.statusText, response.status);
  }

  return (await response.json()) as EvaluationRowsImportResponse;
}

export async function fetchMockEvaluationRows(): Promise<EvaluationRowsImportResponse> {
  const response = await fetch("/api/import/mock-evaluation-rows");

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || response.statusText, response.status);
  }

  return (await response.json()) as EvaluationRowsImportResponse;
}
