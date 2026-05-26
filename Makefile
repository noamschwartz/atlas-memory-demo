# ==============================================================================
# Elastic Demo Starter - Makefile
# ==============================================================================
# Consolidates common commands for development, testing, and deployment.
#
# Quick reference:
#   make start      - Start development servers
#   make stop       - Stop servers
#   make status     - Check server status
#   make test       - Run all tests
#   make check      - Run lint and test
#   make help       - Show all available targets
# ==============================================================================

.PHONY: help start stop restart status logs logs-snapshot open verify test-agent \
        setup preflight install install-backend install-frontend \
        test test-backend test-frontend lint lint-backend lint-frontend \
        format format-backend format-frontend precommit run check \
        docker-up docker-down docker-build docker-logs \
        clean clean-logs clean-pids

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m

# ==============================================================================
# Server Management (wraps ./dev script)
# ==============================================================================

## start: Start backend and frontend servers in background
start:
	@./dev start

## stop: Stop all running servers
stop:
	@./dev stop

## restart: Restart all servers
restart:
	@./dev restart

## status: Show server status, PIDs, and ports
status:
	@./dev status

## logs: Tail server logs (Ctrl+C to exit)
logs:
	@./dev logs

## logs-snapshot: Show recent logs (default 50 lines)
logs-snapshot:
	@./dev logs-snapshot $(or $(LINES),50)

## open: Open browser to frontend
open:
	@./dev open

## verify: Quick setup verification check
verify:
	@./dev verify

## test-agent: Test Agent Builder connection
test-agent:
	@./dev test-agent

# ==============================================================================
# Setup & Installation
# ==============================================================================

## setup: Run interactive setup wizard
setup:
	@./setup.sh

## preflight: Check prerequisites are installed
preflight:
	@./preflight-check.sh

## install: Install all dependencies (backend + frontend)
install: install-backend install-frontend
	@echo "$(GREEN)✅ All dependencies installed$(NC)"

## install-backend: Install backend dependencies with uv
install-backend:
	@echo "$(BLUE)Installing backend dependencies...$(NC)"
	@cd backend && uv sync
	@echo "$(GREEN)✅ Backend dependencies installed$(NC)"

## install-frontend: Install frontend dependencies with yarn
install-frontend:
	@echo "$(BLUE)Installing frontend dependencies...$(NC)"
	@cd frontend && yarn install
	@echo "$(GREEN)✅ Frontend dependencies installed$(NC)"

## init-submodules: Initialize git submodules (hive-mind)
init-submodules:
	@echo "$(BLUE)Initializing submodules...$(NC)"
	@git submodule update --init --recursive
	@echo "$(GREEN)✅ Submodules initialized$(NC)"

# ==============================================================================
# Testing
# ==============================================================================

## test: Run all tests (backend + frontend)
test: test-backend test-frontend
	@echo "$(GREEN)✅ All tests passed$(NC)"

## test-backend: Run backend Python tests
test-backend:
	@echo "$(BLUE)Running backend tests...$(NC)"
	@cd backend && uv run pytest -v

## test-frontend: Run frontend tests with vitest
test-frontend:
	@echo "$(BLUE)Running frontend tests...$(NC)"
	@cd frontend && yarn test

## test-watch: Run frontend tests in watch mode
test-watch:
	@cd frontend && yarn test:watch

# ==============================================================================
# Linting & Code Quality
# ==============================================================================

## lint: Run all linters
lint: lint-backend lint-frontend
	@echo "$(GREEN)✅ Linting complete$(NC)"

## lint-backend: Lint Python code with ruff
lint-backend:
	@echo "$(BLUE)Linting backend...$(NC)"
	@cd backend && uv run ruff check .

## lint-frontend: Lint TypeScript/JavaScript code
lint-frontend:
	@echo "$(BLUE)Linting frontend...$(NC)"
	@cd frontend && yarn lint

## format: Format code (backend + frontend)
format: format-backend format-frontend

## format-backend: Format Python code with ruff
format-backend:
	@echo "$(BLUE)Formatting backend...$(NC)"
	@cd backend && uv run ruff format .

## format-frontend: Format frontend code
format-frontend:
	@echo "$(BLUE)Formatting frontend...$(NC)"
	@cd frontend && yarn lint --fix || true

## precommit: Run pre-commit hooks
precommit:
	@cd backend && uv run pre-commit run --all-files --config ../.pre-commit-config.yaml

## check: Run linting and tests
check: lint test

# ==============================================================================
# Docker
# ==============================================================================

## docker-up: Start services with docker-compose
docker-up:
	@echo "$(BLUE)Starting Docker services...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)✅ Docker services started$(NC)"

## docker-down: Stop docker-compose services
docker-down:
	@echo "$(BLUE)Stopping Docker services...$(NC)"
	@docker-compose down

## docker-build: Build Docker images
docker-build:
	@echo "$(BLUE)Building Docker images...$(NC)"
	@docker-compose build

## docker-logs: Tail docker-compose logs
docker-logs:
	@docker-compose logs -f

## docker-restart: Rebuild and restart Docker services
docker-restart: docker-down docker-build docker-up

# ==============================================================================
# Utilities
# ==============================================================================

## clean: Remove build artifacts and temp files
clean: clean-logs clean-pids
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	@rm -rf backend/__pycache__ backend/**/__pycache__
	@rm -rf frontend/dist frontend/.vite
	@rm -rf .pytest_cache backend/.pytest_cache
	@echo "$(GREEN)✅ Clean complete$(NC)"

## clean-logs: Remove log files
clean-logs:
	@rm -rf .dev-logs/*.log

## clean-pids: Remove PID files (use if servers crash)
clean-pids:
	@rm -rf .dev-pids/*.pid .dev-pids/*.port

## ports: Show what's running on common ports
ports:
	@echo "$(BLUE)Checking ports...$(NC)"
	@echo "Port 3000 (frontend):"
	@lsof -i:3000 2>/dev/null || echo "  (available)"
	@echo "Port 8001 (backend):"
	@lsof -i:8001 2>/dev/null || echo "  (available)"

## health: Check backend health endpoint
health:
	@curl -s http://localhost:$$(cat .dev-pids/backend.port 2>/dev/null || echo 8001)/health | python3 -m json.tool 2>/dev/null || echo "$(RED)Backend not responding$(NC)"

## api-docs: Open API documentation in browser
api-docs:
## run: Run backend entrypoint with uv
run:
	@cd backend && uv run python run.py
	@open http://localhost:$$(cat .dev-pids/backend.port 2>/dev/null || echo 8001)/docs 2>/dev/null || \
		xdg-open http://localhost:$$(cat .dev-pids/backend.port 2>/dev/null || echo 8001)/docs 2>/dev/null || \
		echo "Open http://localhost:8001/docs in your browser"

# ==============================================================================
# Demo Creation
# ==============================================================================

## create-demo: Run the demo creation script
create-demo:
	@./create-demo.sh

# ==============================================================================
# Help
# ==============================================================================

## help: Show this help message
help:
	@echo ""
	@echo "$(BLUE)Elastic Demo Starter$(NC) - Available Commands"
	@echo ""
	@echo "$(YELLOW)Server Management:$(NC)"
	@grep -E '^## (start|stop|restart|status|logs|open|verify|test-agent):' $(MAKEFILE_LIST) | sed 's/## /  make /' | sed 's/:/:  /'
	@echo ""
	@echo "$(YELLOW)Setup & Installation:$(NC)"
	@grep -E '^## (setup|preflight|install|init-submodules):' $(MAKEFILE_LIST) | sed 's/## /  make /' | sed 's/:/:  /'
	@echo ""
	@echo "$(YELLOW)Testing:$(NC)"
	@grep -E '^## (test|check)' $(MAKEFILE_LIST) | sed 's/## /  make /' | sed 's/:/:  /'
	@echo ""
	@echo "$(YELLOW)Linting:$(NC)"
	@grep -E '^## (lint|format|precommit):' $(MAKEFILE_LIST) | sed 's/## /  make /' | sed 's/:/:  /'
	@echo ""
	@echo "$(YELLOW)Docker:$(NC)"
	@grep -E '^## docker' $(MAKEFILE_LIST) | sed 's/## /  make /' | sed 's/:/:  /'
	@echo ""
	@echo "$(YELLOW)Utilities:$(NC)"
	@grep -E '^## (clean|ports|health|api-docs|run|create-demo):' $(MAKEFILE_LIST) | sed 's/## /  make /' | sed 's/:/:  /'
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make start              # Start dev servers"
	@echo "  make test               # Run all tests"
	@echo "  make logs-snapshot LINES=100  # Show last 100 log lines"
	@echo "  make docker-up          # Start with Docker"
	@echo ""
