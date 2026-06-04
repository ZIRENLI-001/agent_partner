from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from backend.eval_agent.api.main import create_app
from backend.eval_agent.services.import_service import parse_evaluation_rows

ROOT = Path(__file__).resolve().parents[1]


def test_parse_evaluation_rows_supports_csv_tsv_and_jsonl():
    csv_rows = parse_evaluation_rows(
        "cases.csv",
        "case_name,instruction,input_data\n顺行样本,通知骑手上线,{\"city\":\"北京\"}\n".encode(
            "utf-8"
        ),
    )
    tsv_rows = parse_evaluation_rows(
        "cases.tsv",
        "样本名称\t任务指令\t待评测数据\n异常追问\t解释退出规则\t{\"risk\":\"退出\"}\n".encode(
            "utf-8"
        ),
    )
    jsonl_rows = parse_evaluation_rows(
        "cases.jsonl",
        '{"caseName":"jsonl sample","instruction":"核验身份","inputData":{"city":"上海"}}\n'.encode(
            "utf-8"
        ),
    )

    assert csv_rows[0]["caseName"] == "顺行样本"
    assert tsv_rows[0]["instruction"] == "解释退出规则"
    assert jsonl_rows[0]["inputData"] == '{\n  "city": "上海"\n}'


def test_parse_evaluation_rows_supports_xlsx_first_sheet():
    xlsx_bytes = build_minimal_xlsx()

    rows = parse_evaluation_rows("cases.xlsx", xlsx_bytes)

    assert rows == [
        {
            "caseName": "Excel 样本",
            "instruction": "通知飞毛腿合同生效",
            "inputData": '{"rider_id":"R001"}',
        }
    ]


def test_parse_official_instruction_excel_maps_instruction_example_column():
    rows = parse_evaluation_rows(
        "命题二：外呼任务对话模型指令示例.xlsx",
        (ROOT / "background" / "命题二：外呼任务对话模型指令示例.xlsx").read_bytes(),
    )

    assert len(rows) == 2
    assert rows[0]["caseName"] == "1"
    assert "# Role" in rows[0]["instruction"]
    assert "飞毛腿" in rows[0]["instruction"]
    assert rows[1]["caseName"] == "2"
    assert "Course Publishing Platform" in rows[1]["instruction"]


def test_import_api_returns_normalized_rows():
    client = TestClient(create_app())

    response = client.post(
        "/api/import/evaluation-rows",
        files={
            "file": (
                "cases.json",
                '[{"case_name":"API 样本","instruction":"解释 ETA","input_data":{"eta":8}}]'.encode(
                    "utf-8"
                ),
                "application/json",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_name"] == "cases.json"
    assert payload["row_count"] == 1
    assert payload["rows"][0]["caseName"] == "API 样本"
    assert payload["rows"][0]["inputData"] == '{\n  "eta": 8\n}'


def test_import_api_maps_internal_sample_library_fields():
    client = TestClient(create_app())

    response = client.post(
        "/api/import/evaluation-rows",
        files={
            "file": (
                "meituan_fulfillment_calibration.jsonl",
                (ROOT / "data" / "calibration" / "meituan_fulfillment_calibration.jsonl").read_bytes(),
                "application/jsonl",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["row_count"] == 10
    assert payload["rows"][0]["caseName"] == "mt_fulfillment_L1_normal_001"
    assert "飞毛腿合同今日生效" in payload["rows"][0]["instruction"]
    assert '"contract_name": "飞毛腿"' in payload["rows"][0]["inputData"]


def test_mock_evaluation_rows_api_uses_official_excel():
    client = TestClient(create_app())

    response = client.get("/api/import/mock-evaluation-rows")

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_name"] == "命题二：外呼任务对话模型指令示例.xlsx"
    assert payload["row_count"] == 2
    assert payload["rows"][0]["caseName"] == "1"
    assert "飞毛腿" in payload["rows"][0]["instruction"]
    assert "Course Publishing Platform" in payload["rows"][1]["instruction"]


def build_minimal_xlsx() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <si><t>case_name</t></si>
  <si><t>instruction</t></si>
  <si><t>input_data</t></si>
  <si><t>Excel 样本</t></si>
  <si><t>通知飞毛腿合同生效</t></si>
  <si><t>{"rider_id":"R001"}</t></si>
</sst>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c>
    </row>
    <row r="2">
      <c r="A2" t="s"><v>3</v></c><c r="B2" t="s"><v>4</v></c><c r="C2" t="s"><v>5</v></c>
    </row>
  </sheetData>
</worksheet>""",
        )
    return buffer.getvalue()
