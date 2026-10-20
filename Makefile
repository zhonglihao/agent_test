# M0 scaffold helpers (Windows PowerShell-friendly via compose primarily)

.PHONY: up down logs build meta health sim-seed sim-tick sim-serve

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

build:
	docker compose build

health:
	curl -s http://localhost:8000/health

meta:
	curl -s http://localhost:8000/api/meta

# WorldSim (apps/sim) — set PYTHONPATH if not using a venv with editable install
SIM_PY=cd apps/sim && PYTHONPATH="$(CURDIR)/apps/sim:$(CURDIR)/apps/sim/.deps" python3 -m worldsim

sim-seed:
	$(SIM_PY) seed

sim-tick:
	$(SIM_PY) tick -n 8

sim-serve:
	$(SIM_PY) serve
