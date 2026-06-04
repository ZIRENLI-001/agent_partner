HOST ?= 127.0.0.1
PORT ?= 8070

.PHONY: install build test dev smoke

install:
	python3 -m pip install -e ".[dev]"
	cd frontend && npm ci

build:
	cd frontend && npm run build

test:
	python3 -m pytest -q
	cd frontend && npm run build

dev:
	python3 -m uvicorn backend.eval_agent.api.main:app --host $(HOST) --port $(PORT)

smoke:
	curl -fsS -o /tmp/dialogue-eval-home.html http://$(HOST):$(PORT)/
	curl -fsS http://$(HOST):$(PORT)/api/health
	curl -fsS http://$(HOST):$(PORT)/api/context
	curl -fsS http://$(HOST):$(PORT)/api/calibration/summary
	curl -fsS http://$(HOST):$(PORT)/api/import/mock-evaluation-rows
