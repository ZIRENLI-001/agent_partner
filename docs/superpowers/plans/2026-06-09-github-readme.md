# GitHub README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the minimal repository README with an accurate, attractive, comprehensive GitHub landing page.

**Architecture:** Keep documentation in a single root `README.md`, link to detailed repository documents, and use GitHub-native Markdown, HTML alignment, tables, badges, and Mermaid. No runtime code or configuration behavior changes.

**Tech Stack:** GitHub Flavored Markdown, Mermaid, shields.io badges

---

### Task 1: Rewrite The Root README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the current content**

Write the approved sections in this order:

1. centered product header, badges, navigation, and demo;
2. product problem and value;
3. core capabilities and two evaluation modes;
4. evaluation-chain Mermaid diagram;
5. explainability, dialogue protocol, and run artifacts;
6. technology stack and repository structure;
7. local mock quick start;
8. real-model environment configuration;
9. API, testing, deployment, security, and documentation links.

- [ ] **Step 2: Check Markdown structure**

Run:

```powershell
rg -n "^#|^```|agentpartner\\.top|docs/" README.md
```

Expected: one H1, balanced fenced blocks, demo URL, and valid document links.

### Task 2: Verify Repository Accuracy

**Files:**
- No additional source changes expected.

- [ ] **Step 1: Validate relative links**

Use PowerShell to extract local Markdown targets and confirm each path exists.

- [ ] **Step 2: Validate documented commands**

Run:

```powershell
python -m pytest -q
```

Run from `frontend/`:

```powershell
npm run build
```

Expected: backend tests and frontend production build pass.

- [ ] **Step 3: Scan for secrets and formatting errors**

Run:

```powershell
git diff --check
git diff -- README.md
```

Confirm the README contains placeholders only, not actual keys or tokens.

### Task 3: Commit And Publish

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Commit**

```powershell
git add README.md docs/superpowers/plans/2026-06-09-github-readme.md
git commit -m "docs: refresh GitHub project introduction"
```

- [ ] **Step 2: Push**

```powershell
git push origin feature/invited-public-beta
git ls-remote origin refs/heads/feature/invited-public-beta
```

Expected: remote SHA matches local `HEAD`.
