# M0 scaffold helpers (Windows PowerShell-friendly via compose primarily)

.PHONY: up down logs build meta health

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
