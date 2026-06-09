import { accessTokenHeaders, ApiError, promptForAccessToken } from "./client";

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

  let response = await fetch("/api/import/evaluation-rows", {
    method: "POST",
    body: formData,
    headers: accessTokenHeaders()
  });
  if (response.status === 401 && promptForAccessToken()) {
    response = await fetch("/api/import/evaluation-rows", {
      method: "POST",
      body: formData,
      headers: accessTokenHeaders()
    });
  }

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || response.statusText, response.status);
  }

  return (await response.json()) as EvaluationRowsImportResponse;
}

export async function fetchMockEvaluationRows(): Promise<EvaluationRowsImportResponse> {
  let response = await fetch("/api/import/mock-evaluation-rows", {
    headers: accessTokenHeaders()
  });
  if (response.status === 401 && promptForAccessToken()) {
    response = await fetch("/api/import/mock-evaluation-rows", {
      headers: accessTokenHeaders()
    });
  }

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || response.statusText, response.status);
  }

  return (await response.json()) as EvaluationRowsImportResponse;
}
