from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_has_clear_top_level_source_boundaries():
    expected_dirs = {
        "backend",
        "frontend",
        "tests",
        "docs",
        "background",
        "runs",
    }

    actual_dirs = {path.name for path in ROOT.iterdir() if path.is_dir()}

    assert expected_dirs.issubset(actual_dirs)
    assert (ROOT / "backend" / "eval_agent" / "api" / "main.py").exists()
    assert (ROOT / "backend" / "evaluation_engine" / "app.py").exists()
    assert (ROOT / "frontend" / "src" / "app" / "router.tsx").exists()
    assert not (ROOT / "eval_agent").exists()


def test_backend_package_boundaries_are_explicit():
    expected_files = [
        "backend/eval_agent/api/main.py",
        "backend/eval_agent/api/routes/context.py",
        "backend/eval_agent/api/routes/runs.py",
        "backend/eval_agent/api/routes/stages.py",
        "backend/eval_agent/core/config.py",
        "backend/eval_agent/providers/base.py",
        "backend/eval_agent/providers/openai_compatible.py",
        "backend/eval_agent/services/context_service.py",
        "backend/eval_agent/services/run_service.py",
        "backend/eval_agent/services/stage_service.py",
        "backend/eval_agent/storage/artifact_store.py",
    ]

    for relative_path in expected_files:
        assert (ROOT / relative_path).exists(), relative_path


def test_backend_code_no_longer_imports_top_level_eval_agent_package():
    source_roots = [ROOT / "backend", ROOT / "tests"]
    forbidden_import = "from " + "eval_agent"
    forbidden_module_import = "import " + "eval_agent"
    offenders = []
    for source_root in source_roots:
        for path in source_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if forbidden_import in text or forbidden_module_import in text:
                offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []


def test_frontend_package_boundaries_are_explicit():
    expected_files = [
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/vite.config.ts",
        "frontend/src/api/client.ts",
        "frontend/src/api/context.ts",
        "frontend/src/api/runs.ts",
        "frontend/src/api/stages.ts",
        "frontend/src/pages/HomePage.tsx",
        "frontend/src/pages/EvaluationWizardPage.tsx",
        "frontend/src/pages/RunHistoryPage.tsx",
        "frontend/src/pages/RunDetailPage.tsx",
        "frontend/src/components/layout/AppLayout.tsx",
    ]

    for relative_path in expected_files:
        assert (ROOT / relative_path).exists(), relative_path


def test_generated_artifacts_are_declared_as_ignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in [
        "__pycache__/",
        ".pytest_cache/",
        "frontend/node_modules/",
        "frontend/dist/",
        "frontend/tsconfig.tsbuildinfo",
        "runs/run_*/",
        "image copy*.png",
    ]:
        assert pattern in gitignore


def test_architecture_docs_describe_structure_and_production_path():
    tech_selection = (
        ROOT / "docs" / "architecture" / "production-platform-tech-selection.md"
    ).read_text(encoding="utf-8")

    assert "backend/" in tech_selection
    assert "frontend/" in tech_selection
    assert "artifacts/" in tech_selection
    assert "Docker Compose" in tech_selection
