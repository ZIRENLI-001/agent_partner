# React Frontend Scaffold Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the React + TypeScript + Vite frontend scaffold while keeping the existing static MVP available.

**Architecture:** Add a new `frontend/` app with routing, API client modules, typed evaluation data, and placeholder pages for Home, Evaluation Visualization, Run History, and Run Detail. Do not remove `eval_agent/web/index.html` until the React app reaches feature parity.

**Tech Stack:** React, TypeScript, Vite, React Router, TanStack Query, Ant Design, ECharts.

---

## File Structure

- Create `frontend/package.json`: scripts and dependencies.
- Create `frontend/tsconfig.json`: TypeScript settings.
- Create `frontend/vite.config.ts`: Vite dev/build config with API proxy.
- Create `frontend/index.html`: Vite root document.
- Create `frontend/src/main.tsx`: React entrypoint.
- Create `frontend/src/app/router.tsx`: route definitions.
- Create `frontend/src/app/queryClient.ts`: TanStack Query client.
- Create `frontend/src/api/client.ts`: fetch wrapper.
- Create `frontend/src/api/context.ts`: context API.
- Create `frontend/src/api/runs.ts`: run API.
- Create `frontend/src/api/stages.ts`: stage API.
- Create `frontend/src/pages/HomePage.tsx`: landing workbench.
- Create `frontend/src/pages/EvaluationWizardPage.tsx`: evaluation visualization placeholder.
- Create `frontend/src/pages/RunHistoryPage.tsx`: history placeholder.
- Create `frontend/src/pages/RunDetailPage.tsx`: report placeholder.
- Create `frontend/src/components/layout/AppLayout.tsx`: top-level layout and nav.
- Create `frontend/src/styles/globals.css`: base Meituan-themed styles.

## Task 1: Package And Build Config

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`

Steps:
- [ ] Add package scripts: `dev`, `build`, `preview`, `typecheck`.
- [ ] Add dependencies: `@vitejs/plugin-react`, `vite`, `typescript`, `react`, `react-dom`, `react-router-dom`, `@tanstack/react-query`, `antd`, `echarts`, `lucide-react`.
- [ ] Configure Vite proxy `/api` to `http://127.0.0.1:8070`.
- [ ] Verify `npm install` and `npm run build` after dependencies are available.

## Task 2: React App Skeleton

**Files:**
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/app/queryClient.ts`
- Create: `frontend/src/components/layout/AppLayout.tsx`
- Create: `frontend/src/styles/globals.css`

Steps:
- [ ] Build a routed shell with left navigation: 首页、评测可视化、历史评测.
- [ ] Apply Meituan yellow/black theme through CSS variables and Ant Design ConfigProvider.
- [ ] Keep pages one-screen friendly by default and avoid dense long-text blocks.

## Task 3: API Client Modules

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/context.ts`
- Create: `frontend/src/api/runs.ts`
- Create: `frontend/src/api/stages.ts`

Steps:
- [ ] Implement a typed `request<T>()` wrapper around `fetch`.
- [ ] Add context, run creation/history/detail, parse/rubric/scenarios calls.
- [ ] Ensure API errors produce readable messages for the UI.

## Task 4: Initial Pages

**Files:**
- Create: `frontend/src/pages/HomePage.tsx`
- Create: `frontend/src/pages/EvaluationWizardPage.tsx`
- Create: `frontend/src/pages/RunHistoryPage.tsx`
- Create: `frontend/src/pages/RunDetailPage.tsx`

Steps:
- [ ] Home shows platform positioning and three entry cards.
- [ ] Evaluation page mirrors the existing seven-step flow at placeholder level.
- [ ] History page queries `/api/runs/history`.
- [ ] Detail page reads `run_id` from route and queries `/api/runs/{run_id}`.

## Task 5: Backend Static Build Integration

**Files:**
- Modify: `backend/eval_agent/api/main.py`
- Test: `tests/test_backend_scaffold.py`

Steps:
- [ ] Add optional static serving for `frontend/dist` when present.
- [ ] Keep current `/` fallback to `eval_agent/web/index.html` when `frontend/dist` does not exist.
- [ ] Add tests verifying fallback behavior.

## Task 6: Verification

Steps:
- [ ] Run `python3 -m pytest -q`.
- [ ] Run current static MVP script syntax check.
- [ ] If npm dependencies are installed, run `cd frontend && npm run build`.
