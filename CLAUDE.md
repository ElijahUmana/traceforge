# TraceForge

Production-grade cross-agent decision provenance substrate built at the Neo4j + AWS Hack Day (2026-05-19).

## Architecture

- **Neo4j Aura** — provenance graph: `:ReasoningTrace -> :ReasoningStep -> :ToolCall` with `:TOUCHED` audit edges
- **AWS Strands Agents v1.40** — `GraphBuilder` DAG swarm: Researcher -> Analyst -> Writer
- **Bedrock AgentCore Runtime** — production deployment via boto3 (folder 06 pattern)
- **ProvenanceHook** — Strands lifecycle hook emitting events to SQS FIFO -> Lambda -> Neo4j

## Key Directories

- `backend/app/` — Strands swarm, ProvenanceHook, FastAPI server
- `lambda_functions/` — 14 Lambda functions (10 tools + provenance writer + 3 APIs)
- `cypher/` — Neo4j constraints, indexes, provenance queries
- `deploy/` — AgentCore Gateway + Runtime deployment scripts
- `infrastructure/` — DynamoDB, SQS, IAM, Secrets Manager provisioning
- `frontend/` — Next.js dashboard (live provenance stream, Why? explorer, Cost, Audit)
- `data/` — Domain ontology and seed fixtures

## Commands

```
make install         # Set up Python venv + frontend deps
make schema          # Apply Neo4j constraints and indexes
make seed            # Seed DynamoDB + Neo4j with demo data
make start           # Start backend (port 8000) + frontend (port 3000)
make test            # Run pytest
make deploy-lambdas  # Deploy all Lambda functions
make deploy-agentcore # Deploy to AgentCore Runtime
make verify-infra    # Verify all AWS + Neo4j infrastructure is ready
```

## Environment

Requires `.env` with `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`. See `.env.example`.

## Conventions

- Python 3.11+, formatted with ruff
- Commit messages explain WHY, not just WHAT
- Every Lambda follows the same pattern: parse event, execute logic, return JSON
- Cypher queries live in `cypher/` as standalone `.cypher` files
- No mocks in tests — hit real Neo4j and DynamoDB
