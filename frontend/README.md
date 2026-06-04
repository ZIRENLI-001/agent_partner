# Frontend

This directory contains the React + TypeScript + Vite frontend for the dialogue evaluation platform.

## Commands

```bash
npm ci
npm run build
npm run dev
```

The production build is written to `frontend/dist`. The FastAPI backend serves that directory when present.

`eval_agent/web/index.html` remains in the repository as a legacy fallback for old local demos, but the React app is the primary frontend.
