"""
NYPA Analytics Chatbot — FastAPI backend.

Pipeline for POST /chat (mirrors the flow described in the project README):
  1. Authenticate the caller (JWT) -> Principal (username, role).
  2. Classify the question into schema domain(s).
  3. Generate SQL against only the curated metadata for those domains.
  4. Validate + authorize the SQL server-side (auth.py + sql_validator.py) —
     the LLM's output is never trusted or executed directly.
  5. Execute with the shared read-only warehouse connection.
  6. Summarize the results in natural language.
  7. Log the question, SQL, metrics, and outcome. Update conversation memory.
"""
import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
import classifier
import conversation
import executor
import logging_store
import responder
import sql_generation
import sql_validator
from config import settings

settings.validate()

app = FastAPI(title="NYPA Analytics Chatbot")
bearer_scheme = HTTPBearer()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    role: str


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sql: str | None = None
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0
    duration_ms: int = 0
    domains: list[str] = []


def get_principal(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> auth.Principal:
    try:
        return auth.verify_token(creds.credentials)
    except auth.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    try:
        principal = auth.authenticate(req.username, req.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return LoginResponse(token=auth.issue_token(principal), role=principal.role)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, principal: auth.Principal = Depends(get_principal)):
    session_id = req.session_id or str(uuid.uuid4())
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")

    entry = logging_store.LogEntry(
        session_id=session_id, username=principal.username, role=principal.role, question=question,
    )

    try:
        domains = classifier.classify_domains(question)
        entry.domains = domains

        if not domains:
            answer = "That doesn't look like a question about NYPA generation or supply-rate data — try asking about facility generation, rates, or customer segments."
            entry.status = "no_query"
            entry.answer = answer
            logging_store.log(entry)
            return ChatResponse(session_id=session_id, answer=answer, domains=[])

        context = conversation.store.context_text(session_id)
        raw_sql = sql_generation.generate_sql(question, domains, conversation_context=context)
        entry.generated_sql = raw_sql

        if raw_sql.upper().startswith("NO_QUERY"):
            answer = raw_sql.split(":", 1)[-1].strip() or "I can't answer that with the available data."
            entry.status = "no_query"
            entry.answer = answer
            logging_store.log(entry)
            return ChatResponse(session_id=session_id, answer=answer, domains=domains)

        try:
            validated = sql_validator.validate_and_authorize(raw_sql, principal)
        except sql_validator.SqlValidationError as e:
            entry.status = "validation_error"
            entry.error = str(e)
            logging_store.log(entry)
            # Surfaced to the user rather than silently retried — a rejected
            # query is a signal worth showing, not hiding.
            raise HTTPException(status_code=422, detail=f"Generated query was rejected: {e}")

        entry.validated_sql = validated.sql

        try:
            result = executor.execute(validated.sql)
        except executor.QueryExecutionError as e:
            entry.status = "execution_error"
            entry.error = str(e)
            entry.duration_ms = 0
            logging_store.log(entry)
            raise HTTPException(status_code=502, detail=f"Query execution failed: {e}")

        entry.row_count = result.row_count
        entry.duration_ms = result.duration_ms

        answer = responder.summarize(question, result, domains)
        entry.status = "success"
        entry.answer = answer
        logging_store.log(entry)

        conversation.store.add_turn(session_id, question, validated.sql, answer)

        return ChatResponse(
            session_id=session_id,
            answer=answer,
            sql=validated.sql,
            columns=result.columns,
            rows=[list(r) for r in result.rows],
            row_count=result.row_count,
            duration_ms=result.duration_ms,
            domains=domains,
        )
    except HTTPException:
        raise
    except Exception as e:
        entry.status = "execution_error"
        entry.error = str(e)
        logging_store.log(entry)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@app.get("/logs")
def logs(limit: int = 50, principal: auth.Principal = Depends(get_principal)):
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can view the audit log.")
    return logging_store.recent(limit)


# Serve the frontend as static files, mounted last so it doesn't shadow the API routes.
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
