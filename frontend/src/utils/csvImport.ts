export interface CsvEvaluationRow {
  caseName: string;
  instruction: string;
  inputData: string;
}

const caseNameKeys = ["case_name", "caseName", "sample_id", "id", "样本名称", "样本名", "name", "title"];
const instructionKeys = ["instruction", "task_instruction", "任务指令", "任务指令示例", "指令", "prompt"];
const inputDataKeys = ["input_data", "inputData", "input_variables", "待评测数据", "样本数据", "data", "context", "payload"];
const excelExtensions = [".xlsx", ".xls"];

export function parseEvaluationRows(fileName: string, fileContent: string | ArrayBuffer): CsvEvaluationRow[] {
  const lowerName = fileName.toLowerCase();

  if (excelExtensions.some((extension) => lowerName.endsWith(extension))) {
    throw new Error("Excel 文件请通过后端上传接口解析。");
  }

  const fileText = typeof fileContent === "string" ? fileContent : new TextDecoder("utf-8").decode(fileContent);
  if (lowerName.endsWith(".jsonl")) return parseJsonLinesRows(fileText);
  if (lowerName.endsWith(".json")) return parseJsonRows(fileText);
  return parseTabularRows(fileText, detectDelimiter(fileText));
}

export function parseCsvRows(csvText: string): CsvEvaluationRow[] {
  return parseTabularRows(csvText, ",");
}

export function parseTabularRows(fileText: string, delimiter = ","): CsvEvaluationRow[] {
  const rows = splitDelimitedRows(fileText, delimiter).filter((row) => row.some((cell) => cell.trim()));
  if (rows.length < 2) return [];
  const headers = rows[0].map((cell) => cell.trim());
  return filterUsableRows(rows.slice(1).map((row, index) => normalizeTabularRow(headers, row, index)));
}

export function parseJsonRows(fileText: string): CsvEvaluationRow[] {
  const parsed = JSON.parse(fileText);
  const rows = Array.isArray(parsed) ? parsed : parsed.rows || parsed.samples || parsed.data || [parsed];
  if (!Array.isArray(rows)) return [];
  return filterUsableRows(rows.map((row, index) => normalizeObjectRow(row, index)));
}

export function parseJsonLinesRows(fileText: string): CsvEvaluationRow[] {
  return fileText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => normalizeObjectRow(JSON.parse(line), index))
    .filter((row) => row.instruction.trim() || row.inputData.trim());
}

export function detectDelimiter(fileText: string) {
  const firstDataLine = fileText
    .split(/\r?\n/)
    .find((line) => line.trim() && !line.trim().startsWith("#"));
  return firstDataLine?.includes("\t") ? "\t" : ",";
}

function normalizeTabularRow(headers: string[], row: string[], index: number): CsvEvaluationRow {
  return {
    caseName: readColumn(headers, row, caseNameKeys) || `样本 ${index + 1}`,
    instruction: readColumn(headers, row, instructionKeys),
    inputData: readColumn(headers, row, inputDataKeys)
  };
}

function normalizeObjectRow(row: unknown, index: number): CsvEvaluationRow {
  if (!row || typeof row !== "object" || Array.isArray(row)) {
    return { caseName: `样本 ${index + 1}`, instruction: "", inputData: stringifyInputData(row) };
  }

  const objectRow = row as Record<string, unknown>;
  return {
    caseName: readObjectValue(objectRow, caseNameKeys) || `样本 ${index + 1}`,
    instruction: readObjectValue(objectRow, instructionKeys),
    inputData: readObjectValue(objectRow, inputDataKeys)
  };
}

function filterUsableRows(rows: CsvEvaluationRow[]) {
  return rows.filter((row) => row.instruction.trim() || row.inputData.trim());
}

function readObjectValue(row: Record<string, unknown>, keys: string[]) {
  const key = keys.find((candidate) => Object.prototype.hasOwnProperty.call(row, candidate));
  return key ? stringifyInputData(row[key]) : "";
}

function stringifyInputData(value: unknown) {
  if (value === undefined || value === null) return "";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function readColumn(headers: string[], row: string[], keys: string[]) {
  const index = headers.findIndex((header) => keys.includes(header));
  return index >= 0 ? row[index] || "" : "";
}

function splitDelimitedRows(fileText: string, delimiter: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let index = 0; index < fileText.length; index += 1) {
    const char = fileText[index];
    const next = fileText[index + 1];
    if (char === '"' && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === delimiter && !inQuotes) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }

  row.push(cell);
  rows.push(row);
  return rows;
}
