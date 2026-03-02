.PHONY: dev down build test migrate seed lint

# Development
dev:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f

# Backend
backend-shell:
	docker-compose exec backend bash

# Database
migrate:
	docker-compose exec backend alembic upgrade head

migrate-create:
	docker-compose exec backend alembic revision --autogenerate -m "$(msg)"

seed:
	docker-compose exec backend python -m scripts.seed_db

# Testing
test-backend:
	docker-compose exec backend pytest -v

test-frontend:
	docker-compose exec frontend npm test

test: test-backend test-frontend

# Linting
lint-backend:
	docker-compose exec backend ruff check app/
	docker-compose exec backend ruff format --check app/

lint-frontend:
	docker-compose exec frontend npm run lint

lint: lint-backend lint-frontend

# Utilities
create-admin:
	docker-compose exec backend python -m scripts.create_admin

psql:
	docker-compose exec postgres psql -U winaity -d winaity

redis-cli:
	docker-compose exec redis redis-cli
