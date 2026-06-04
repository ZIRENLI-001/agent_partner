from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.eval_agent.core.config import project_root
from backend.eval_agent.services.import_service import parse_evaluation_rows

router = APIRouter(prefix="/api/import", tags=["import"])
OFFICIAL_MOCK_EXCEL = project_root() / "background" / "命题二：外呼任务对话模型指令示例.xlsx"


@router.post("/evaluation-rows")
async def import_evaluation_rows(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        content = await file.read()
        rows = parse_evaluation_rows(file.filename or "evaluation_rows.csv", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="文件解析失败，请检查字段名和文件格式。") from exc

    return {
        "file_name": file.filename,
        "row_count": len(rows),
        "rows": rows,
    }


@router.get("/mock-evaluation-rows")
def mock_evaluation_rows() -> dict[str, object]:
    try:
        rows = parse_evaluation_rows(OFFICIAL_MOCK_EXCEL.name, OFFICIAL_MOCK_EXCEL.read_bytes())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="官方 mock Excel 文件不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="官方 mock Excel 解析失败。") from exc

    return {
        "file_name": OFFICIAL_MOCK_EXCEL.name,
        "row_count": len(rows),
        "rows": rows,
    }
