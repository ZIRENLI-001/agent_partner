from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


SAMPLE_TASKS_PATH = Path("background/命题二：外呼任务对话模型指令示例.xlsx")
SPREADSHEET_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

FULFILLMENT_BACKGROUND = {
    "department": "美团履约平台技术部",
    "capabilities": [
        "订单调度：实时分配、路由优化、多骑手协同",
        "骑手调度系统：骑手 App、接单/抢单、轨迹监控",
        "运力供给：运力池管理、弹性调度、专送/众包",
        "配送预测：ETA 预估、运力紧张预警",
        "智能调度：AI 全局最优路径规划与任务分配",
    ],
    "risk_tags": [
        "capacity_pressure",
        "route_eta_challenge",
        "rider_app_operation",
        "dispatch_fairness",
        "safety_boundary",
    ],
}


def load_sample_tasks(path: Path = SAMPLE_TASKS_PATH) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with ZipFile(path) as archive:
        shared_strings = _shared_strings(archive)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    tasks = []
    rows = sheet.findall(".//a:row", SPREADSHEET_NS)
    for row in rows[1:]:
        cells = [_cell_text(cell, shared_strings) for cell in row.findall("a:c", SPREADSHEET_NS)]
        if len(cells) < 2 or not cells[1].strip():
            continue
        tasks.append(
            {
                "id": cells[0].strip(),
                "name": _task_name(cells[1]),
                "instruction": cells[1],
            }
        )
    return tasks


def _shared_strings(archive: ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values = []
    for item in root.findall("a:si", SPREADSHEET_NS):
        texts = [node.text or "" for node in item.findall(".//a:t", SPREADSHEET_NS)]
        values.append("".join(texts))
    return values


def _cell_text(cell, shared_strings: list[str]) -> str:
    value = cell.find("a:v", SPREADSHEET_NS)
    if value is None or value.text is None:
        return ""
    if cell.get("t") == "s":
        return shared_strings[int(value.text)]
    return value.text


def _task_name(instruction: str) -> str:
    for line in instruction.splitlines():
        if "飞毛腿" in line:
            return "飞毛腿骑手外呼任务"
        if "课程" in line or "直播" in line:
            return "课程发布客服外呼任务"
    return "任务指令样例"
