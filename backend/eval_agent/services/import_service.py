from __future__ import annotations

import csv
import json
import re
from io import BytesIO, StringIO
from pathlib import PurePosixPath
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile


EvaluationRow = dict[str, str]

CASE_NAME_KEYS = [
    "case_name",
    "caseName",
    "sample_id",
    "id",
    "样本名称",
    "样本名",
    "name",
    "title",
]
INSTRUCTION_KEYS = [
    "instruction",
    "task_instruction",
    "任务指令",
    "任务指令示例",
    "指令",
    "prompt",
]
INPUT_DATA_KEYS = [
    "input_data",
    "inputData",
    "input_variables",
    "待评测数据",
    "样本数据",
    "data",
    "context",
    "payload",
]


def parse_evaluation_rows(file_name: str, content: bytes) -> list[EvaluationRow]:
    lower_name = file_name.lower()
    if lower_name.endswith(".xlsx"):
        return _parse_xlsx_rows(content)
    if lower_name.endswith(".xls"):
        raise ValueError("暂不支持旧版 .xls 二进制格式，请另存为 .xlsx / CSV / JSONL 后导入。")

    text = content.decode("utf-8-sig")
    if lower_name.endswith(".jsonl"):
        return _parse_jsonl_rows(text)
    if lower_name.endswith(".json"):
        return _parse_json_rows(text)
    return _parse_tabular_rows(text, _detect_delimiter(text))


def _parse_tabular_rows(text: str, delimiter: str) -> list[EvaluationRow]:
    rows = [row for row in csv.reader(StringIO(text), delimiter=delimiter) if any(cell.strip() for cell in row)]
    if len(rows) < 2:
        return []
    headers = [cell.strip() for cell in rows[0]]
    return _filter_usable_rows(
        [_normalize_mapping(dict(zip(headers, row)), index) for index, row in enumerate(rows[1:])]
    )


def _parse_json_rows(text: str) -> list[EvaluationRow]:
    parsed = json.loads(text)
    if isinstance(parsed, list):
        rows = parsed
    elif isinstance(parsed, dict):
        rows = parsed.get("rows") or parsed.get("samples") or parsed.get("data") or [parsed]
    else:
        rows = []
    return _filter_usable_rows(
        [_normalize_mapping(row, index) for index, row in enumerate(rows) if isinstance(row, dict)]
    )


def _parse_jsonl_rows(text: str) -> list[EvaluationRow]:
    rows: list[EvaluationRow] = []
    for index, line in enumerate(line.strip() for line in text.splitlines()):
        if line:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(_normalize_mapping(parsed, index))
    return _filter_usable_rows(rows)


def _parse_xlsx_rows(content: bytes) -> list[EvaluationRow]:
    with ZipFile(BytesIO(content)) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_path = _first_sheet_path(archive)
        sheet_xml = ElementTree.fromstring(archive.read(sheet_path))

    rows: list[list[str]] = []
    for row_node in sheet_xml.findall(".//{*}sheetData/{*}row"):
        values_by_column: dict[int, str] = {}
        for cell_node in row_node.findall("{*}c"):
            reference = cell_node.attrib.get("r", "")
            column_index = _column_index(reference)
            if column_index is None:
                continue
            values_by_column[column_index] = _read_cell_value(cell_node, shared_strings)
        if values_by_column:
            max_column = max(values_by_column)
            rows.append([values_by_column.get(index, "") for index in range(max_column + 1)])

    if len(rows) < 2:
        return []
    headers = [cell.strip() for cell in rows[0]]
    return _filter_usable_rows(
        [_normalize_mapping(dict(zip(headers, row)), index) for index, row in enumerate(rows[1:])]
    )


def _read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("{*}si"):
        text_parts = [node.text or "" for node in item.findall(".//{*}t")]
        strings.append("".join(text_parts))
    return strings


def _first_sheet_path(archive: ZipFile) -> str:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    first_sheet = workbook.find(".//{*}sheet")
    if first_sheet is None:
        raise ValueError("Excel 文件中没有可读取的 sheet。")
    relationship_id = first_sheet.attrib.get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    )
    if not relationship_id:
        return "xl/worksheets/sheet1.xml"

    relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relationship in relationships.findall("{*}Relationship"):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib.get("Target", "worksheets/sheet1.xml")
            return str(PurePosixPath("xl") / target)
    return "xl/worksheets/sheet1.xml"


def _read_cell_value(cell_node: ElementTree.Element, shared_strings: list[str]) -> str:
    value_node = cell_node.find("{*}v")
    inline_text = cell_node.find(".//{*}is/{*}t")
    if inline_text is not None:
        return inline_text.text or ""
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell_node.attrib.get("t") == "s":
        index = int(value)
        return shared_strings[index] if 0 <= index < len(shared_strings) else ""
    return value


def _column_index(reference: str) -> int | None:
    match = re.match(r"([A-Z]+)", reference)
    if not match:
        return None
    index = 0
    for char in match.group(1):
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def _detect_delimiter(text: str) -> str:
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    return "\t" if "\t" in first_line else ","


def _normalize_mapping(row: dict[str, Any], index: int) -> EvaluationRow:
    return {
        "caseName": _read_value(row, CASE_NAME_KEYS) or f"样本 {index + 1}",
        "instruction": _read_value(row, INSTRUCTION_KEYS),
        "inputData": _read_value(row, INPUT_DATA_KEYS),
    }


def _filter_usable_rows(rows: list[EvaluationRow]) -> list[EvaluationRow]:
    return [row for row in rows if row["instruction"].strip() or row["inputData"].strip()]


def _read_value(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        if key in row:
            return _stringify(row[key])
    return ""


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)
