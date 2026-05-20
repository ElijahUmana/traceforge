"""TraceForge FastAPI application.

Serves the REST API for credit evaluation, provenance queries,
cost attribution, and trace listing. All data lives in Neo4j Aura.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create Neo4j driver on startup, close on shutdown."""
    uri = os.environ["NEO4J_URI"]
    username = os.environ["NEO4J_USERNAME"]
    password = os.environ["NEO4J_PASSWORD"]
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    driver = GraphDatabase.driver(uri, auth=(username, password))
    driver.verify_connectivity()
    app.state.neo4j_driver = driver
    app.state.neo4j_database = database

    yield

    driver.close()


app = FastAPI(
    title="TraceForge",
    description="Cross-agent decision provenance API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.app.routes import router  # noqa: E402

app.include_router(router)
