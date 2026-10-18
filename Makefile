.PHONY: up down test smoke extract kb-load seed reset-tenants eval export

API ?= http://localhost:8000
WEB ?= http://localhost:3001

up:
	docker compose up -d --build

down:
	docker compose down

test:
	cd services/api && .venv/bin/pytest

smoke:
	bash scripts/smoke.sh $(API) $(WEB)

extract:
	python3.12 scripts/extract_clinvar.py variants

kb-load:
	python3.12 scripts/load.py

seed:
	python3.12 scripts/seed_demo.py

reset-tenants:
	python3.12 scripts/seed_demo.py --reset-tenants

eval:
	python3.12 eval/run_eval.py

export:
	python3.12 scripts/export.py
