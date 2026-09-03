.PHONY: help up down up-build down-volumes logs ps api-shell web-shell migrate seed \
        dev-web dev-api lint typecheck clean

help:
	@echo "Sentinel AI - Gujarat Police CCTV Intelligence Platform"
	@echo ""
	@echo "Docker workflow:"
	@echo "  make up            Build & start the full stack (web / api / postgres / redis)"
	@echo "  make up-build      Rebuild images and start"
	@echo "  make down          Stop all services"
	@echo "  make logs          Tail logs"
	@echo "  make ps            Service status"
	@echo "  make api-shell     Shell into the API container"
	@echo "  make migrate       Run alembic upgrades inside the API container"
	@echo "  make seed          Seed demo data (idempotent)"
	@echo ""
	@echo "Local (no docker) workflow:"
	@echo "  make dev-api       Start FastAPI (requires local postgres + redis)"
	@echo "  make dev-web       Start Next.js dev server"
	@echo "  make lint          Lint + typecheck frontend"
	@echo "  make clean         Remove generated artifacts"

up:
	docker compose up -d

up-build:
	docker compose up -d --build

down:
	docker compose down

down-volumes:
	docker compose down -v

logs:
	docker compose logs -f

ps:
	docker compose ps

api-shell:
	docker compose exec api bash

migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python -m src.seed

dev-api:
	cd apps/api && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-web:
	cd apps/web && npm run dev

lint:
	npm run lint:web

typecheck:
	npm run typecheck:web

clean:
	rm -rf apps/web/.next apps/web/node_modules apps/api/__pycache__