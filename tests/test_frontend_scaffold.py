from pathlib import Path

from fastapi.testclient import TestClient

from backend.eval_agent.api import main as backend_main


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_frontend_scaffold_declares_react_vite_stack():
    package_json = (FRONTEND / "package.json").read_text(encoding="utf-8")
    vite_config = (FRONTEND / "vite.config.ts").read_text(encoding="utf-8")

    assert (FRONTEND / "package-lock.json").exists()
    assert '"react"' in package_json
    assert '"vite"' in package_json
    assert '"typescript"' in package_json
    assert '"antd"' in package_json
    assert '"echarts"' in package_json
    assert '"build": "tsc -b && vite build"' in package_json
    assert '"typecheck": "tsc -b"' in package_json
    assert 'target: "http://127.0.0.1:8070"' in vite_config


def test_frontend_scaffold_has_routed_production_pages():
    router = (FRONTEND / "src" / "app" / "router.tsx").read_text(encoding="utf-8")
    layout = (
        FRONTEND / "src" / "components" / "layout" / "AppLayout.tsx"
    ).read_text(encoding="utf-8")

    assert 'path: "/"' in router
    assert 'path: "/quick-evaluation"' in router
    assert 'path: "/evaluation"' in router
    assert 'path: "/calibration"' in router
    assert 'path: "/history"' in router
    assert 'path: "/runs/:runId"' in router
    assert "首页" in layout
    assert "端到端评测" in layout
    assert "分阶段评测" in layout
    assert "评测样本库" in layout
    assert "历史评测" in layout


def test_frontend_api_modules_cover_current_backend_contracts():
    client = (FRONTEND / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    context = (FRONTEND / "src" / "api" / "context.ts").read_text(encoding="utf-8")
    runs = (FRONTEND / "src" / "api" / "runs.ts").read_text(encoding="utf-8")
    stages = (FRONTEND / "src" / "api" / "stages.ts").read_text(encoding="utf-8")
    imports = (FRONTEND / "src" / "api" / "imports.ts").read_text(
        encoding="utf-8"
    )

    assert "async function request" in client
    assert "DEFAULT_REQUEST_TIMEOUT_MS" in client
    assert "900_000" in client
    assert "AbortController" in client
    assert "请求超过" in client
    assert "15 分钟" in client
    assert 'request<PlatformContext>("/api/context")' in context
    assert 'request<RunHistoryResponse>("/api/runs/history")' in runs
    assert 'request<RunDetailResponse>(`/api/runs/${runId}`)' in runs
    assert 'request<RunResponse>("/api/runs"' in runs
    assert 'request<RunSubmitResponse>("/api/runs/async"' in runs
    assert 'request<RunStatusResponse>(`/api/runs/${runId}/status`)' in runs
    assert "stage_model_config?: " not in runs
    assert "StageModelConfig" not in runs
    assert 'request<ParseStageResponse>("/api/stages/parse"' in stages
    assert 'request<RubricStageResponse>("/api/stages/rubric"' in stages
    assert 'request<ScenariosStageResponse>("/api/stages/scenarios"' in stages
    assert 'fetch("/api/import/evaluation-rows"' in imports
    assert 'fetch("/api/import/mock-evaluation-rows"' in imports
    assert "fetchMockEvaluationRows" in imports
    assert "FormData" in imports


def test_staged_evaluation_submits_confirmed_stage_artifacts():
    runs = (FRONTEND / "src" / "api" / "runs.ts").read_text(encoding="utf-8")
    page = (
        FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx"
    ).read_text(encoding="utf-8")

    assert "task_spec?: Record<string, unknown>" in runs
    assert "rubric_spec?: Record<string, unknown>" in runs
    assert "scenario_set?:" in runs
    assert "task_spec: parseResult.task_spec" in page
    assert "rubric_spec: rubricResult.rubric_spec" in page
    assert "scenario_set: confirmedScenarioSet" in page
    assert "No selected scenarios" in page


def test_frontend_has_reusable_evaluation_progress_component():
    component = (
        FRONTEND / "src" / "components" / "evaluation" / "EvaluationProgress.tsx"
    ).read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "EvaluationProgress" in component
    assert "Progress" in component
    assert "progressPercent" in component
    assert "progress-stage-card" in component
    assert "description?: string" in component
    assert "progress-stage-copy" in component
    assert "onStageClick" in component
    assert "isStageDisabled" in component
    assert "status === \"running\"" in component
    assert "status === \"completed\"" in component
    assert ".evaluation-progress" in styles
    assert ".progress-stage-grid" in styles


def test_staged_evaluation_uses_dialogue_simulation_label():
    page = (FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx").read_text(
        encoding="utf-8"
    )
    home_page = (FRONTEND / "src" / "pages" / "HomePage.tsx").read_text(
        encoding="utf-8"
    )
    charts = (
        FRONTEND / "src" / "components" / "evaluation" / "RunCharts.tsx"
    ).read_text(encoding="utf-8")

    assert 'title: "对话模拟"' in page
    assert "模拟不同用户反应与风险分支" in page
    assert "场景生成" not in page
    assert 'title: "对话模拟"' in home_page
    assert "Rubric、对话模拟、执行评测和报告分析" in home_page
    assert 'scenario_generation: "对话模拟"' in charts


def test_frontend_has_visual_report_charts():
    runs = (FRONTEND / "src" / "api" / "runs.ts").read_text(encoding="utf-8")
    component = (
        FRONTEND / "src" / "components" / "evaluation" / "RunCharts.tsx"
    ).read_text(encoding="utf-8")
    detail_page = (FRONTEND / "src" / "pages" / "RunDetailPage.tsx").read_text(
        encoding="utf-8"
    )
    quick_page = (
        FRONTEND / "src" / "pages" / "QuickEvaluationPage.tsx"
    ).read_text(encoding="utf-8")
    wizard_page = (
        FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx"
    ).read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "ScenarioSummary" in runs
    assert "scenario_summary: ScenarioSummary[]" in runs
    assert "stage_timings_ms: Record<string, number>" in runs
    assert "stage_diagnostics?: Record<string, Record<string, unknown>>" in runs
    loader = (
        FRONTEND / "src" / "components" / "evaluation" / "loadECharts.ts"
    ).read_text(encoding="utf-8")
    assert 'import("./loadECharts")' in component
    assert 'from "echarts/core"' in loader
    assert 'from "echarts/charts"' in loader
    assert 'from "echarts/components"' in loader
    assert 'from "echarts/renderers"' in loader
    assert "BarChart" in loader
    assert "PieChart" in loader
    assert "dimensionOption" in component
    assert "scenarioOption" in component
    assert "failureOption" in component
    assert "timingOption" in component
    assert "<RunCharts result={data} />" in detail_page
    assert "<RunCharts result={runResult} compact />" in quick_page
    assert "<RunCharts result={result} compact />" in wizard_page
    assert ".run-chart-grid" in styles
    assert ".run-chart-canvas" in styles


def test_history_tables_use_sample_library_pagination_interaction():
    history_page = (
        FRONTEND / "src" / "pages" / "RunHistoryPage.tsx"
    ).read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert 'className: "history-pagination"' in history_page
    assert "showSizeChanger: false" in history_page
    assert "showLessItems: false" in history_page
    assert ".history-page .ant-pagination-item-active" in styles
    assert ".history-page .ant-pagination-item-active a" in styles


def test_report_charts_constrain_labels_so_text_stays_visible():
    component = (
        FRONTEND / "src" / "components" / "evaluation" / "RunCharts.tsx"
    ).read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "chartAxisLabel" in component
    assert "chartValueLabel" in component
    assert "fontSize: 10" in component
    assert "overflow: \"truncate\"" in component
    assert "width: 72" in component
    assert "hideOverlap: true" in component
    assert "bottom: 64" in component
    assert "containLabel: true" in component
    assert "height: 270px" in styles


def test_report_charts_format_small_stage_timings_without_zeroing_them():
    component = (
        FRONTEND / "src" / "components" / "evaluation" / "RunCharts.tsx"
    ).read_text(encoding="utf-8")

    assert "formatDuration" in component
    assert "value < 1000" in component
    assert '`${Math.max(1, Math.round(value))}ms`' in component
    assert "entries.map(([, value]) => Number(value))" in component
    assert "stage_diagnostics" in component
    assert "formatStageDiagnostic" in component


def test_react_calibration_dataset_page_is_read_only_and_explainable():
    router = (FRONTEND / "src" / "app" / "router.tsx").read_text(encoding="utf-8")
    api = (FRONTEND / "src" / "api" / "calibration.ts").read_text(
        encoding="utf-8"
    )
    page = (
        FRONTEND / "src" / "pages" / "CalibrationDatasetPage.tsx"
    ).read_text(encoding="utf-8")

    assert "CalibrationDatasetPage" in router
    assert 'request<CalibrationSamplesResponse>("/api/calibration/samples")' in api
    assert "评测样本库" in page
    assert "难度分层、风险标签、预期评分与证据轮次" in page
    assert "难度分层标准" in page
    assert "L1 基础顺行" in page
    assert "L5 复杂对抗" in page
    assert "轮次影响说明" in page
    assert "轮次会影响难度，但不会单独决定难度" in page
    assert "难度覆盖" in page
    assert "calibration-summary-grid" not in page
    assert "筛选标签" in page
    assert "filteredSamples" in page
    assert "riskFilter" in page
    assert "Pagination" in page
    assert "样本详情（{filteredSamples.length} / {samples.length} 条）" in page
    assert "预期标签" in page
    assert "证据轮次" in page
    assert "多轮对话" in page
    assert "Collapse" in page


def test_calibration_standard_is_collapsible_and_typography_is_compact():
    page = (
        FRONTEND / "src" / "pages" / "CalibrationDatasetPage.tsx"
    ).read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "calibration-standard-collapse" in page
    assert 'key: "difficulty-standard"' in page
    assert "难度分层标准" in page
    assert "defaultActiveKey" not in page.split("calibration-standard-collapse", 1)[1].split("calibration-body", 1)[0]
    assert ".calibration-standard-collapse .ant-collapse-header" in styles
    assert ".calibration-coverage" in styles
    assert ".calibration-samples" in styles
    assert ".calibration-detail" in styles
    assert "font-size: 12px" in styles
    assert "line-height: 1.45" in styles


def test_calibration_overview_and_samples_use_small_pages_instead_of_panel_scroll():
    page = (
        FRONTEND / "src" / "pages" / "CalibrationDatasetPage.tsx"
    ).read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "const samplePageSize = 9" in page
    assert "const coveragePageSize = 5" in page
    assert "CoverageBlock" in page
    assert "CoverageTags" in page
    assert "coverage-section" in page
    assert "coverage-target-list" in page
    assert "showAllTargets" in page
    assert "展开全部" in page
    assert "收起" in page
    assert "coverage-target-heading" in page
    assert "coverage-target-list-expanded" in page
    assert "pageSize={samplePageSize}" in page
    assert "filteredSamples.slice((page - 1) * samplePageSize, page * samplePageSize)" in page
    assert ".calibration-coverage,\n.calibration-samples" in styles
    assert "overflow: hidden" in styles
    assert ".coverage-pagination" in styles
    assert ".coverage-section" in styles
    assert ".coverage-target-list" in styles
    assert ".coverage-target-heading" in styles
    assert ".coverage-target-list-expanded" in styles
    assert "max-height: 260px" in styles
    assert "margin-top: 10px" in styles
    assert ".calibration-page .ant-pagination-item-active" in styles
    assert "background: var(--mt-yellow)" in styles
    assert ".calibration-page .ant-pagination-item-active a" in styles


def test_calibration_sample_expanded_detail_is_scrollable():
    page = (
        FRONTEND / "src" / "pages" / "CalibrationDatasetPage.tsx"
    ).read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "className=\"calibration-sample-collapse\"" in page
    assert "calibration-detail-scroll" in page
    assert ".calibration-sample-collapse .ant-collapse-content-box" in styles
    assert ".calibration-sample-collapse {\n  min-height: 0;\n  overflow-y: auto;" in styles
    assert "grid-template-rows: auto auto minmax(0, 1fr) auto" in styles
    assert ".calibration-detail-scroll" in styles
    assert "max-height: min(58vh, 620px)" in styles
    assert "overflow-y: auto" in styles
    assert "overscroll-behavior: contain" in styles


def test_frontend_report_surfaces_quality_summary_metrics():
    runs_api = (FRONTEND / "src" / "api" / "runs.ts").read_text(encoding="utf-8")
    wizard_page = (
        FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx"
    ).read_text(encoding="utf-8")

    assert "quality_summary" in runs_api
    assert "链路健康度" in wizard_page
    assert "quality_summary?.overall_status" in wizard_page
    assert "traceable_evidence_rate" in wizard_page
    assert "missing_item_count" in wizard_page
    assert "remediation_actions" in runs_api
    assert "auto_repair" in runs_api
    assert "质量门禁建议" in wizard_page
    assert "后端自动修复" in wizard_page
    assert "attempt_count" in wizard_page
    assert "handleQualityRemediation" in wizard_page


def test_react_evaluation_page_contains_functional_workflow():
    page = (
        FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx"
    ).read_text(encoding="utf-8")
    import_util = (FRONTEND / "src" / "utils" / "csvImport.ts").read_text(
        encoding="utf-8"
    )

    assert "模型名称" in page
    assert "OpenRouter 模型 ID" in page
    assert 'useState("openrouter")' in page
    assert "{ value: \"openrouter\", label: \"OpenRouter\" }," in page
    assert "AutoComplete" in page
    assert "openRouterModelOptions" in page
    assert "defaultOpenRouterModel" in page
    assert "使用后端默认 OpenRouter API Key" in page
    assert "openrouterBackendKeyHint" in page
    assert 'props.modelName === "smoke-test-model"' in page
    assert "filterOption={false}" in page
    assert "openai/gpt-4.1-mini" in page
    assert "anthropic/claude-sonnet-4.6" in page
    assert "meituan/longcat-flash-chat" not in page
    assert "qwen/qwen3-32b" not in page
    assert "anthropic/claude-3.5-sonnet" not in page
    assert "qwen/qwen3-max" in page
    assert "deepseek/deepseek-chat" in page
    assert "也可手动输入 OpenRouter 模型 ID" in page
    assert "https://openrouter.ai/api/v1" in page
    assert "被测模型" in page
    assert "用户模拟模型" not in page
    assert "语义裁判模型" not in page
    assert "stage_model_config" not in page
    assert "API Base" in page
    assert "任务指令" in page
    assert "导入数据" in page
    assert "导入表格" not in page
    assert 'className="form-field instruction-field"' in page
    assert "fetchMockEvaluationRows" in page
    assert "loadMockRows" in page
    assert "uploadEvaluationRows" in page
    assert "ImportedRowsEditor" in page
    assert "导入内容预览" in page
    assert "导入后将在这里显示" in page
    assert "importedCount" in page
    assert "import-preview-editor" in page
    assert ".csv,.tsv,.txt,.json,.jsonl,.xlsx,.xls" in page
    assert "支持 CSV / TSV / TXT / JSON / JSONL / Excel" in page
    assert "样本名称" in page
    assert "单条待评测数据" in page
    assert "当前样本 JSON" in page
    assert "模拟对话数量" in page
    assert "生成多少种不同用户反应和对话分支" in page
    assert "最少测试场景数" not in page
    assert "生成当前步骤" in page
    assert "进入下一步" in page
    assert "完成评测" in page
    assert "primaryActionLabel" in page
    assert "evaluation-primary-action" in page
    assert "isStepGenerated" in page
    assert "isStepProgressCompleted" in page
    assert "stepItems.slice(0, index + 1)" in page
    assert 'generatedSteps.has("report")' in page
    assert "maxVisitedIndex" in page
    assert "goToStep" in page
    assert "未开始" in page
    assert "已生成" in page
    assert "已调整，需重新生成" in page
    assert "StepForward" not in page
    assert "parseInstruction" in page
    assert "buildRubric" in page
    assert "generateScenarios" in page
    assert "createRun" not in page
    assert "submitRun" in page
    assert "pollRunStatus" in page
    assert "getRunStatus" in page
    assert "getRunDetail" in page
    assert "MAX_RUN_POLL_ATTEMPTS = 900" in page
    assert "后台任务仍在运行" in page
    assert "ScenarioTraceSwitcher" in page
    assert "<ScenarioTraceSwitcher result={result} compact />" in page
    assert "查看完整报告" in page
    assert "返回历史评测" in page
    assert "to={`/runs/${result.run_id}`}" in page
    assert 'to="/history"' in page
    assert "场景覆盖" in page
    assert "对话轨迹" in page
    assert "对话演示" in page
    assert "评分证据" in page
    assert "调整后重新生成" in page
    assert "环节调整说明" in page
    assert "stageAdjustments" in page
    assert "updateStageAdjustment" in page
    assert "canRegenerateActiveStep" in page
    assert 'regeneratableSteps.includes(activeStep)' in page
    assert "regenerateActiveStep" in page
    assert "重新生成当前步骤" in page
    assert "当前步骤自定义修改" in page
    assert "onResultChange" in page
    assert "setParseResult(value)" in page
    assert "setRubricResult(value)" in page
    assert "setScenarioResult(value)" in page
    assert "resetGeneratedFrom(activeStep)" in page
    assert "clearStageResultsFrom" in page
    assert "parseTabularRows" in import_util
    assert "parseJsonRows" in import_util
    assert "parseJsonLinesRows" in import_util
    assert "detectDelimiter" in import_util


def test_react_history_and_report_pages_are_visualized():
    history_page = (
        FRONTEND / "src" / "pages" / "RunHistoryPage.tsx"
    ).read_text(encoding="utf-8")
    detail_page = (
        FRONTEND / "src" / "pages" / "RunDetailPage.tsx"
    ).read_text(encoding="utf-8")
    wizard_page = (
        FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx"
    ).read_text(encoding="utf-8")

    assert "搜索任务或 Run" in history_page
    assert "通过率" in history_page
    assert "场景数" in history_page
    assert "查看报告" in history_page
    assert "mt-action-button" in history_page
    assert "保存时间" in history_page
    assert "formatSavedTime" in history_page
    assert "Progress" in detail_page
    assert "保存时间" in detail_page
    assert "高风险项" in detail_page
    assert "失败证据链" in detail_page
    assert "FailureEvidenceCollapse" in detail_page
    assert "评判标准" in detail_page
    assert "实际表现" in detail_page
    assert "对话轨迹" in detail_page
    assert "Markdown 原文" in detail_page


def test_history_page_supports_filterable_comparison_analysis():
    api = (FRONTEND / "src" / "api" / "runs.ts").read_text(encoding="utf-8")
    page = (FRONTEND / "src" / "pages" / "RunHistoryPage.tsx").read_text(
        encoding="utf-8"
    )
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "RunComparisonResponse" in api
    assert "getRunComparison" in api
    assert 'request<RunComparisonResponse>("/api/runs/comparison")' in api
    assert "同一场景不同模型" in page
    assert "同一模型不同场景" in page
    assert "失败原因汇总" in page
    assert "comparisonMode" in page
    assert "selectedScenarioId" in page
    assert "selectedModelName" in page
    assert "score_anomaly" in page
    assert ".history-comparison-panel" in styles


def test_history_page_records_and_comparison_are_collapsible():
    page = (FRONTEND / "src" / "pages" / "RunHistoryPage.tsx").read_text(
        encoding="utf-8"
    )
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "Collapse" in page
    assert "defaultActiveKey" in page
    assert "comparison-panel" in page
    assert "history-records-panel" in page
    assert "对比分析" in page
    assert "历史评测记录" in page
    assert ".history-collapse" in styles
    assert ".history-collapse .ant-collapse-header" in styles


def test_history_comparison_mode_switches_primary_filter():
    page = (FRONTEND / "src" / "pages" / "RunHistoryPage.tsx").read_text(
        encoding="utf-8"
    )

    assert "comparisonMode === \"scenario\"" in page
    assert "选择要横向比较的场景" in page
    assert "选择要横向比较的模型" in page
    assert "matchesComparison" in page
    assert "comparison-focus-select" in page


def test_history_comparison_failure_summary_scrolls_and_uses_balanced_typography():
    page = (FRONTEND / "src" / "pages" / "RunHistoryPage.tsx").read_text(
        encoding="utf-8"
    )
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "visibleFailureReasons.map" in page
    assert "visibleFailureReasons.slice" not in page
    assert ".failure-reason-panel" in styles
    assert ".comparison-scroll-region" in styles
    assert "max-height: 300px" in styles
    assert ".failure-reason-list" in styles
    assert "overflow-y: auto" in styles
    assert ".history-page .ant-table" in styles
    assert "font-size: 12px" in styles
    assert "line-height: 1.45" in styles
    assert ".history-page .ant-table-cell" in styles


def test_history_comparison_shows_optimization_insight_summary():
    api = (FRONTEND / "src" / "api" / "runs.ts").read_text(encoding="utf-8")
    page = (FRONTEND / "src" / "pages" / "RunHistoryPage.tsx").read_text(
        encoding="utf-8"
    )
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "optimization_insights: OptimizationInsight[]" in api
    assert "visibleOptimizationInsights" in page
    assert "优化建议摘要" in page
    assert "recommended_action" in page
    assert "business_context" in page
    assert "问题判断" in page
    assert "证据指向" in page
    assert "下一步动作" in page
    assert "issue_summary" in page
    assert "evidence_summary" in page
    assert "next_action" in page
    assert ".comparison-optimization-list" in styles
    assert ".comparison-optimization-card" in styles


def test_history_comparison_reason_and_optimization_panels_are_collapsible_and_scrollable():
    page = (FRONTEND / "src" / "pages" / "RunHistoryPage.tsx").read_text(
        encoding="utf-8"
    )
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "comparison-side-collapse" in page
    assert "failure-reasons-panel" in page
    assert "optimization-insights-panel" in page
    assert "失败原因汇总" in page
    assert "优化建议摘要" in page
    assert ".comparison-side-collapse" in styles
    assert ".comparison-scroll-region" in styles
    assert "max-height: 300px" in styles
    assert "overflow-y: auto" in styles


def test_history_comparison_optimization_filter_does_not_require_exact_scenario_ids():
    page = (FRONTEND / "src" / "pages" / "RunHistoryPage.tsx").read_text(
        encoding="utf-8"
    )
    function_body = page.split("function filterOptimizationInsights", 1)[1].split(
        "function formatScore", 1
    )[0]

    assert "const matchesScenario" not in function_body
    assert "return matchesRun && matchesModel;" in function_body


def test_react_reports_use_switchable_scenario_trace_viewer():
    component_path = (
        FRONTEND
        / "src"
        / "components"
        / "evaluation"
        / "ScenarioTraceSwitcher.tsx"
    )
    component = component_path.read_text(encoding="utf-8")
    quick_page = (
        FRONTEND / "src" / "pages" / "QuickEvaluationPage.tsx"
    ).read_text(encoding="utf-8")
    detail_page = (
        FRONTEND / "src" / "pages" / "RunDetailPage.tsx"
    ).read_text(encoding="utf-8")
    wizard_page = (
        FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx"
    ).read_text(encoding="utf-8")

    assert "ScenarioTraceSwitcher" in component
    assert "useState" in component
    assert "scenario_summary" in component
    assert "selectedScenarioId" in component
    assert "result.traces.find" in component
    assert "result.results.find" in component
    assert "场景切换" in component
    assert "对话轨迹" in component
    assert "<ScenarioTraceSwitcher result={runResult} compact />" in quick_page
    assert "<ScenarioTraceSwitcher result={result} compact />" in wizard_page
    assert "<ScenarioTraceSwitcher result={data} />" in detail_page


def test_scenario_switch_control_is_prominent_on_trace_right_side():
    component = (
        FRONTEND
        / "src"
        / "components"
        / "evaluation"
        / "ScenarioTraceSwitcher.tsx"
    ).read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "scenario-switcher-control" in component
    assert component.index("scenario-switcher-score") < component.index("scenario-switcher-control")
    assert ".scenario-switcher-control" in styles
    assert "justify-self: end" in styles
    assert ".scenario-switcher-control .ant-select-selector" in styles
    assert "background: var(--mt-yellow) !important" in styles
    assert "border-color: var(--mt-yellow) !important" in styles
    assert "background: transparent" in styles
    assert "min-width: 240px" in styles


def test_scenario_trace_score_prefers_evaluation_result_over_summary_cache():
    component = (
        FRONTEND
        / "src"
        / "components"
        / "evaluation"
        / "ScenarioTraceSwitcher.tsx"
    ).read_text(encoding="utf-8")

    assert "evaluationScore" in component
    assert "evaluationPossibleScore" in component
    assert "score: evaluationScore ?? summary?.score ?? 0" in component
    assert "possible_score: evaluationPossibleScore ?? summary?.possible_score ?? 0" in component


def test_report_detail_places_trace_and_failure_evidence_side_by_side():
    detail_page = (
        FRONTEND / "src" / "pages" / "RunDetailPage.tsx"
    ).read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "report-insight-grid" in detail_page
    assert "report-trace-card" in detail_page
    assert "report-failure-card" in detail_page
    assert "report-dimension-card" not in detail_page
    assert ".report-insight-grid" in styles
    assert "grid-template-columns: minmax(420px, 1.08fr) minmax(360px, 0.92fr)" in styles
    assert ".report-insight-grid .ant-card" in styles
    assert "align-items: stretch" in styles


def test_report_detail_collapses_markdown_source_by_default():
    detail_page = (
        FRONTEND / "src" / "pages" / "RunDetailPage.tsx"
    ).read_text(encoding="utf-8")

    assert "showMarkdown" in detail_page
    assert "setShowMarkdown" in detail_page
    assert "展开 Markdown 原文" in detail_page
    assert "收起 Markdown 原文" in detail_page
    assert 'className="mt-action-button"' in detail_page
    assert "{showMarkdown ? <pre>{data.report}</pre> : null}" in detail_page


def test_action_option_buttons_use_fixed_yellow_background():
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert ".home-hero-main .button-row .ant-btn" in styles
    assert ".mode-card .ant-btn" in styles
    assert ".evaluation-primary-action.ant-btn-primary" in styles
    assert ".quick-primary-action.ant-btn-primary" in styles
    assert ".mt-action-button.ant-btn" in styles
    assert styles.count("background: var(--mt-yellow)") >= 5
    assert "background: #ffffff;\n  color: var(--ink);\n  box-shadow: none;\n}" not in styles


def test_vite_build_splits_heavy_vendor_chunks():
    config = (FRONTEND / "vite.config.ts").read_text(encoding="utf-8")

    assert "manualChunks" in config
    assert "react-vendor" in config
    assert "antd-vendor" in config
    assert "antd-support-vendor" in config
    assert "echarts-vendor" in config
    assert "router-vendor" in config
    assert "query-vendor" in config


def test_react_home_and_evaluation_have_competition_ready_presentation():
    home_page = (FRONTEND / "src" / "pages" / "HomePage.tsx").read_text(
        encoding="utf-8"
    )
    evaluation_page = (
        FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx"
    ).read_text(encoding="utf-8")

    assert "端到端自动评测" in home_page
    assert 'to: "/quick-evaluation"' in home_page
    assert 'tags: ["快速评测", "快速验收", "证据链"]' in home_page
    assert "比赛演示" not in home_page
    assert "分阶段评测" in home_page
    assert "历史评测" in home_page
    assert "履约数字人外呼" in home_page
    assert "评测过程可解释" in home_page
    assert "评测结果可量化" in home_page
    assert "home-hero" in home_page
    assert "mode-card" in home_page
    assert "结构化摘要" in evaluation_page
    assert "result-section" in evaluation_page
    assert "rubric-table" in evaluation_page
    assert "trace-preview" in evaluation_page


def test_react_quick_evaluation_is_separate_from_visualized_workflow():
    router = (FRONTEND / "src" / "app" / "router.tsx").read_text(encoding="utf-8")
    home_page = (FRONTEND / "src" / "pages" / "HomePage.tsx").read_text(
        encoding="utf-8"
    )
    quick_page = (
        FRONTEND / "src" / "pages" / "QuickEvaluationPage.tsx"
    ).read_text(encoding="utf-8")

    assert "QuickEvaluationPage" in router
    assert 'to: "/quick-evaluation"' in home_page
    assert "生成端到端评测报告" in quick_page
    assert 'useState("openrouter")' in quick_page
    assert "{ value: \"openrouter\", label: \"OpenRouter\" }," in quick_page
    assert "useState(1)" in quick_page
    assert "模拟对话数量" in quick_page
    assert "生成多少种不同用户反应和对话分支" in quick_page
    assert "最少测试场景数" not in quick_page
    assert "quick-primary-action" in quick_page
    assert "mt-action-button" in quick_page
    assert "使用后端默认 OpenRouter API Key" in quick_page
    assert "openrouterBackendKeyHint" in quick_page
    assert "meituan/longcat-flash-chat" not in quick_page
    assert "qwen/qwen3-32b" not in quick_page
    assert "anthropic/claude-3.5-sonnet" not in quick_page
    assert "qwen/qwen3-max" in quick_page
    assert "deepseek/deepseek-chat" in quick_page
    assert "一次提交后自动完成全链路" in quick_page
    assert "导入数据" in quick_page
    assert "导入表格" not in quick_page
    assert 'className="form-field instruction-field"' in quick_page
    assert "SampleLibraryPicker" in quick_page
    assert "选择评测样本库" in quick_page
    assert "applyCalibrationSample" in quick_page
    assert "upsertEvaluationRow" in quick_page
    assert "setCsvRows((previous) => upsertEvaluationRow(previous, row))" in quick_page
    assert "fetchMockEvaluationRows" in quick_page
    assert "loadMockRows" in quick_page
    assert "uploadEvaluationRows" in quick_page
    assert "ImportedRowsEditor" in quick_page
    assert "导入内容预览" in quick_page
    assert "导入后将在这里显示" in quick_page
    assert "importedCount" in quick_page
    assert "import-preview-editor" in quick_page
    assert ".csv,.tsv,.txt,.json,.jsonl,.xlsx,.xls" in quick_page
    assert "支持 CSV / TSV / TXT / JSON / JSONL / Excel" in quick_page
    assert "样本名称" in quick_page
    assert "单条待评测数据" in quick_page
    assert "保存到历史评测" in quick_page
    assert "已保存到历史评测" in quick_page
    assert "FailureEvidencePanel" in quick_page
    assert "评判标准" in quick_page
    assert "实际表现" in quick_page
    assert "失败原因" in quick_page
    assert "submitRun" in quick_page
    assert "pollRunStatus" in quick_page
    assert "getRunStatus" in quick_page
    assert "后台任务生成中" in quick_page
    assert "MAX_RUN_POLL_ATTEMPTS = 900" in quick_page
    assert "后台任务仍在运行" in quick_page
    assert "EvaluationProgress" in quick_page
    assert "runStatusToProgressStages" in quick_page
    assert "parseInstruction" not in quick_page
    assert "buildRubric" not in quick_page
    assert "generateScenarios" not in quick_page


def test_react_visualized_evaluation_shows_step_progress():
    page = (
        FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx"
    ).read_text(encoding="utf-8")
    component = (
        FRONTEND / "src" / "components" / "evaluation" / "EvaluationProgress.tsx"
    ).read_text(encoding="utf-8")

    assert "EvaluationProgress" in page
    assert "SampleLibraryPicker" in page
    assert "选择评测样本库" in page
    assert "applyCalibrationSample" in page
    assert "upsertEvaluationRow" in page
    assert "setCsvRows((previous) => upsertEvaluationRow(previous, row))" in page
    assert "wizardProgressStages" in page
    assert "阶段评测进度" in page
    assert "模型配置" in page
    assert "样本导入" in page
    assert "对话模拟" in page
    assert "执行评测" in page
    assert "报告分析" in page
    assert "stageDescriptions" in page
    assert "配置被测模型和 API 连接方式" in page
    assert "检查最终量化指标和失败证据" in page
    assert "onStageClick={goToStep}" in page
    assert "isStageDisabled" in page
    assert " Steps," not in page
    assert "<Steps" not in page
    assert "已完成" in component
    assert "生成中" in component


def test_frontend_warns_when_percent_score_fails_quality_gate():
    wizard = (FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx").read_text(
        encoding="utf-8"
    )
    detail = (FRONTEND / "src" / "pages" / "RunDetailPage.tsx").read_text(
        encoding="utf-8"
    )
    quick = (FRONTEND / "src" / "pages" / "QuickEvaluationPage.tsx").read_text(
        encoding="utf-8"
    )
    types = (FRONTEND / "src" / "api" / "runs.ts").read_text(encoding="utf-8")

    assert "score_reliable?: boolean" in types
    assert "score_reliability_reason?: string" in types
    assert "当前百分制分数暂不可单独采信" in wizard
    assert "ScoreReliabilityAlert" in wizard
    assert "当前百分制分数暂不可单独采信" in detail
    assert "分数需复核" in detail
    assert "当前百分制分数暂不可单独采信" in quick


def test_staged_evaluation_page_uses_compact_spacing():
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert ".evaluation-page {\n  grid-template-rows: auto minmax(0, 1fr);" in styles
    assert ".evaluation-page .page-header" in styles
    assert ".evaluation-page .page-title" in styles
    assert ".evaluation-grid {\n  display: grid;\n  grid-template-columns: 260px minmax(0, 1fr);" in styles
    assert ".evaluation-stage {\n  min-height: 0;\n  height: 100%;\n  overflow-y: auto;\n  font-size: 12px;" in styles
    assert ".evaluation-page .evaluation-progress" in styles
    assert "border: 2px solid #efe2a4" in styles
    assert "font-size: 16px" in styles
    assert "font-size: 22px" in styles
    assert ".evaluation-grid > aside" in styles
    assert "grid-template-rows: minmax(0, 1fr)" in styles
    assert "grid-template-rows: auto auto minmax(0, 1fr)" in styles
    assert "grid-template-rows: repeat(7, minmax(0, 1fr))" in styles
    assert "min-height: 0" in styles
    assert "overflow: hidden" in styles
    assert ".progress-stage-card .ant-tag" in styles
    assert "align-self: center" in styles
    assert "display: inline-flex" in styles
    assert ".progress-stage-copy" in styles
    assert "white-space: normal" in styles
    assert "line-clamp" not in styles


def test_frontend_has_reusable_sample_library_picker():
    component = (
        FRONTEND / "src" / "components" / "evaluation" / "SampleLibraryPicker.tsx"
    ).read_text(encoding="utf-8")

    assert "getCalibrationSamples" in component
    assert "选择评测样本库" in component
    assert "difficultyFilter" in component
    assert "domainFilter" in component
    assert "riskFilter" in component
    assert "onSelect(sample)" in component
    assert "input_variables" in component


def test_react_frontend_matches_8070_workspace_design():
    layout = (
        FRONTEND / "src" / "components" / "layout" / "AppLayout.tsx"
    ).read_text(encoding="utf-8")
    home_page = (FRONTEND / "src" / "pages" / "HomePage.tsx").read_text(
        encoding="utf-8"
    )
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "topbar" in layout
    assert "global-nav light-nav" in layout
    assert "评测记录按项目隔离保存" in layout
    assert "履约评测平台" in layout
    assert "01" in layout
    assert "02" in layout
    assert "03" in layout

    assert "复杂指令分阶段评测流程" in home_page
    assert "home-dashboard compact-home" in home_page
    assert "home-hero-main" in home_page
    assert "home-capability-grid" in home_page
    assert "workflow-strip" in home_page
    assert "07" in home_page

    assert ".topbar" in styles
    assert ".workspace" in styles
    assert ".global-nav-item.active" in styles
    assert ".home-hero-main" in styles
    assert ".home-capability-grid" in styles
    assert ".workflow-strip" in styles


def test_react_home_visual_style_uses_subtle_hero_gradient_and_aligned_icons():
    home_page = (FRONTEND / "src" / "pages" / "HomePage.tsx").read_text(
        encoding="utf-8"
    )
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "icon: Zap" in home_page
    assert "icon: GitBranch" in home_page
    assert "icon: ClipboardList" in home_page
    assert "icon: ListChecks" not in home_page
    assert "icon: History" not in home_page
    assert ".home-hero-main" in styles
    assert "background: linear-gradient(104deg, #fff0a6 0%, #fff9dc 28%, #ffffff 66%);" in styles
    assert "box-shadow: inset 6px 0 0 rgba(255, 209, 0, 0.92);" not in styles
    assert ".home-hero-main .button-row .ant-btn-primary" in styles
    assert ".home-hero-main .button-row .ant-btn:hover" in styles
    assert "background: var(--mt-yellow);" in styles
    assert "color: var(--ink);" in styles
    assert ".capability-icon svg" in styles
    assert ".mode-card-icon svg" in styles
    assert "display: block;" in styles
    assert "font-size: 28px;" in styles
    assert "font-weight: 720;" in styles
    assert "font-size: 14px;" in styles
    assert "font-weight: 500;" in styles
    assert "font-size: 13px;" in styles
    assert "position: relative;" in styles
    assert "position: absolute;" in styles
    assert "transform: translate(-50%, -50%);" in styles


def test_react_primary_pages_use_single_viewport_layout():
    home_page = (FRONTEND / "src" / "pages" / "HomePage.tsx").read_text(
        encoding="utf-8"
    )
    evaluation_page = (
        FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx"
    ).read_text(encoding="utf-8")
    history_page = (
        FRONTEND / "src" / "pages" / "RunHistoryPage.tsx"
    ).read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "compact-home" in home_page
    assert 'className="viewport-page evaluation-page"' in evaluation_page
    assert 'className="viewport-page history-page"' in history_page
    assert "height: 100vh;" in styles
    assert "height: calc(100vh - 72px);" in styles
    assert "overflow: hidden;" in styles
    assert "grid-template-rows: minmax(300px, 1fr) auto minmax(150px, auto) auto;" in styles
    assert ".home-dashboard.compact-home" in styles
    assert "overflow-y: auto;" in styles
    assert "height: clamp(300px, 42vh, 360px);" not in styles
    assert "height: clamp(148px, 22vh, 172px);" not in styles
    assert "min-height: 156px;" in styles
    assert ".evaluation-stage" in styles
    assert ".evaluation-primary-action.ant-btn-primary" in styles
    assert ".quick-primary-action.ant-btn-primary" in styles
    assert ".mt-action-button.ant-btn" in styles
    assert "background: var(--mt-yellow);" in styles
    assert "overflow-y: auto;" in styles
    assert ".history-table-shell" in styles
    assert ".import-preview-editor" in styles
    assert ".import-preview-editor .ant-input" in styles
    assert "pagination={historyPagination(6)}" in history_page


def test_backend_scaffold_mentions_frontend_dist_fallback():
    main_py = (ROOT / "backend" / "eval_agent" / "api" / "main.py").read_text(
        encoding="utf-8"
    )

    assert "FRONTEND_DIST" in main_py
    assert "StaticFiles" in main_py
    assert "WEB_INDEX" in main_py


def test_backend_serves_frontend_dist_when_present(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<div>React App</div>", encoding="utf-8")

    monkeypatch.setattr(backend_main, "FRONTEND_DIST", dist)
    app = backend_main.create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "React App" in response.text


def test_backend_serves_frontend_dist_for_browser_router_paths(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<div>React App</div>", encoding="utf-8")

    monkeypatch.setattr(backend_main, "FRONTEND_DIST", dist)
    app = backend_main.create_app()
    client = TestClient(app)

    history_response = client.get("/history")
    detail_response = client.get("/runs/run_abc123")
    api_response = client.get("/api/unknown")

    assert history_response.status_code == 200
    assert "React App" in history_response.text
    assert detail_response.status_code == 200
    assert "React App" in detail_response.text
    assert api_response.status_code == 404
