.PHONY: install start seed test lint deploy clean schema why cost audit

install:
	uv venv --python 3.11
	uv pip install -e ".[dev]"
	cd frontend && npm install

start:
	@echo "Starting backend..."
	cd backend && uvicorn app.main:app --reload --port 8000 &
	@echo "Starting frontend..."
	cd frontend && npm run dev &
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"

seed:
	python backend/scripts/seed_data.py

test:
	pytest backend/tests/ -v

lint:
	ruff check backend/ lambda_functions/

schema:
	python backend/scripts/apply_schema.py

deploy-lambdas:
	python infrastructure/deploy_lambdas.py

deploy-agentcore:
	python deploy/deploy_runtime.py

deploy: deploy-lambdas deploy-agentcore

clean:
	rm -rf .venv node_modules frontend/.next lambda_packages/

verify-infra:
	python backend/scripts/verify_infra.py

why:
	@read -p "Trace ID: " id; \
	curl -s "http://localhost:8000/api/why/$$id" | jq .

cost:
	@read -p "Tenant ID: " tid; \
	curl -s "http://localhost:8000/api/cost?tenant_id=$$tid" | jq .

audit:
	@read -p "Trace ID: " tid; \
	curl -s -X POST "http://localhost:8000/api/audit/$$tid" -o audit_report.pdf; \
	echo "Saved to audit_report.pdf"
