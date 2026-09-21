"""
agent.py
--------
LLM orchestration layer for the SQL Data Analyst Agent.

Exposes:
  generate_sql(question, schema) -> dict
      LLM call 1: convert a natural-language question to a SQL query.

  explain_result(question, sql, result) -> str
      LLM call 2: ground a plain-English explanation in the actual result.

  run_agent(question) -> dict
      Full pipeline: schema → generate_sql → validate_sql → execute_query
                     → explain_result.
      Always returns a structured dict; never raises.
"""

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load API key from .env (never hardcoded)
load_dotenv()

# ── Model config ──────────────────────────────────────────────────────────────
_MODEL = "gemini-3.6-flash"

# ── System prompt template ────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are a precise SQL generation assistant. You convert natural-language \
questions into safe, read-only SQLite queries.

DATABASE SCHEMA:
{schema}

RULES — you MUST follow every rule without exception:
1. Only generate SELECT statements. You may use WITH (CTEs), JOIN, GROUP BY,
   ORDER BY, WHERE, HAVING, and LIMIT clauses.
2. NEVER generate: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH,
   DETACH, PRAGMA, REPLACE, TRUNCATE, VACUUM, GRANT, or REVOKE.
3. NEVER generate Python code or any code other than SQL.
4. Only reference tables and columns that exist in the DATABASE SCHEMA above.
   Do not invent table or column names.
5. Use SQLite syntax (e.g., strftime for dates, no ILIKE).
6. Always include a LIMIT clause (default LIMIT 100 if not naturally limited).
7. If the question cannot be answered from the schema, set "sql" to "" and
   explain clearly why in "explanation". Do NOT guess or fabricate data.

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown fences, no extra text:
{{"sql": "<your SELECT statement or empty string>", "explanation": "<one sentence explaining what the query does, or why it cannot be answered>"}}
"""


# ── API client factory ────────────────────────────────────────────────────────

def _get_client() -> genai.Client:
    """
    Create and return a Gemini API client using GEMINI_API_KEY from the env.

    Raises:
        EnvironmentError: if the key is missing or blank.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Add it to your .env file: GEMINI_API_KEY=your_key_here"
        )
    return genai.Client(api_key=api_key)


# ── SQL generation ────────────────────────────────────────────────────────────

def generate_sql(question: str, schema: str) -> dict:
    """
    Ask the LLM to convert a natural-language question into a SQL query.

    Args:
        question: The user's plain-English question.
        schema:   The database schema string (from database.get_schema()).

    Returns:
        dict with keys:
          "sql"         – A SELECT statement, or "" if unanswerable.
          "explanation" – What the query does, or why it can't be answered.
          "error"       – Present only on failure; friendly error message.
    """
    # ── Validate inputs ───────────────────────────────────────────────────────
    question = (question or "").strip()
    if not question:
        return {"sql": "", "explanation": "No question was provided.", "error": "Empty question."}

    # ── Build prompt ──────────────────────────────────────────────────────────
    system_prompt = _SYSTEM_PROMPT.format(schema=schema)
    user_message = f"Question: {question}"

    # ── Call Gemini API ───────────────────────────────────────────────────────
    try:
        client = _get_client()
    except EnvironmentError as e:
        return {"sql": "", "explanation": "", "error": str(e)}

    try:
        response = client.models.generate_content(
            model=_MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                # Request JSON output directly — reduces formatting noise
                response_mime_type="application/json",
                temperature=0.0,   # Deterministic SQL generation
                max_output_tokens=1024,
            ),
        )
        raw_text = response.text.strip()
    except Exception as e:
        return {
            "sql": "",
            "explanation": "",
            "error": f"Gemini API error: {e}",
        }

    # ── Parse JSON response ───────────────────────────────────────────────────
    # Strip markdown fences if the model adds them despite instructions
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "sql": "",
            "explanation": "",
            "error": (
                f"Could not parse the model's response as JSON. "
                f"Raw response: {raw_text[:200]}"
            ),
        }

    # ── Normalise keys — ensure both fields exist ─────────────────────────────
    return {
        "sql":         result.get("sql", ""),
        "explanation": result.get("explanation", ""),
    }


# ── Result explanation ────────────────────────────────────────────────────────

_EXPLAIN_SYSTEM = """\
You are a data analyst assistant. Your job is to explain a SQL query result \
in plain English, in 1-3 sentences.

CRITICAL RULES:
1. Only reference numbers, names, and values that appear in the QUERY RESULT
   section below. NEVER invent, estimate, or extrapolate data.
2. If the result contains zero rows, you MUST state that no matching data was
   found. Do not guess what the answer might be.
3. Be concise and specific — include the actual top value/number from the result.
4. Do not explain how the SQL works — only explain what the data shows.
"""


def explain_result(question: str, sql: str, result: dict) -> str:
    """
    Ask the LLM to explain a query result in plain English.

    The explanation is strictly grounded in the returned data — the LLM
    is explicitly instructed not to invent numbers or values.

    Args:
        question: The original natural-language question.
        sql:      The SQL that was executed.
        result:   Structured result from execute_query() {columns, rows, error}.

    Returns:
        A 1-3 sentence plain-English explanation, or a friendly error string.
    """
    # ── Zero-row short-circuit — no LLM call needed ───────────────────────────
    if not result.get("rows"):
        return "No matching data was found in the database for this question."

    # ── Format the result for the LLM prompt ─────────────────────────────────
    columns = result.get("columns", [])
    rows = result.get("rows", [])

    # Render as a simple text table (compact, easy for the LLM to read)
    header = " | ".join(columns)
    separator = "-" * len(header)
    row_lines = [" | ".join(str(v) for v in row) for row in rows[:20]]  # cap preview
    result_text = "\n".join([header, separator] + row_lines)
    if len(rows) > 20:
        result_text += f"\n... ({len(rows)} rows total, showing first 20)"

    user_message = (
        f"ORIGINAL QUESTION:\n{question}\n\n"
        f"SQL EXECUTED:\n{sql}\n\n"
        f"QUERY RESULT:\n{result_text}\n\n"
        "Please explain what this result shows in 1-3 plain-English sentences, "
        "referencing only the values shown above."
    )

    # ── Call Gemini API ───────────────────────────────────────────────────────
    try:
        client = _get_client()
    except EnvironmentError as e:
        return f"[Explanation unavailable: {e}]"

    try:
        response = client.models.generate_content(
            model=_MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=_EXPLAIN_SYSTEM,
                temperature=0.2,
                max_output_tokens=256,
            ),
        )
        return response.text.strip()
    except Exception as e:
        return f"[Explanation unavailable: Gemini API error — {e}]"


# ── Full pipeline orchestration ───────────────────────────────────────────────

def run_agent(question: str) -> dict:
    """
    Run the complete SQL agent pipeline for a user question.

    Pipeline:
        get_schema() → generate_sql() → validate_sql()
        → execute_query() [only if valid] → explain_result()

    Security guarantee: validate_sql() is ALWAYS called before execute_query().
    No code path bypasses validation.

    Args:
        question: The user's plain-English question.

    Returns:
        {
          "sql":         str   – generated SQL (empty if generation failed),
          "is_valid":    bool  – True if SQL passed validation,
          "result":      dict  – {columns, rows, error} from execute_query,
                                 or None if not reached,
          "explanation": str   – LLM explanation grounded in result,
          "error":       str|None – friendly error message, or None on success,
        }
    """
    # Import here to avoid circular imports (database imports nothing from agent)
    from database import get_schema, execute_query
    from sql_validator import validate_sql

    # ── Base response structure ───────────────────────────────────────────────
    response = {
        "sql":         "",
        "is_valid":    False,
        "result":      None,
        "explanation": "",
        "error":       None,
    }

    # ── Step 1: load schema ───────────────────────────────────────────────────
    try:
        schema = get_schema()
    except Exception as e:
        response["error"] = f"Could not load database schema: {e}"
        return response

    # ── Step 2: generate SQL ──────────────────────────────────────────────────
    try:
        gen = generate_sql(question, schema)
    except Exception as e:
        response["error"] = f"SQL generation failed unexpectedly: {e}"
        return response

    if gen.get("error"):
        response["error"] = gen["error"]
        return response

    sql = gen.get("sql", "").strip()
    response["sql"] = sql

    # LLM decided the question is unanswerable from the schema
    if not sql:
        response["explanation"] = gen.get(
            "explanation",
            "This question cannot be answered from the available database schema.",
        )
        return response

    # ── Step 3: validate SQL (MANDATORY — no bypass) ──────────────────────────
    is_valid, reason = validate_sql(sql)
    response["is_valid"] = is_valid

    if not is_valid:
        response["error"] = (
            f"The generated SQL was rejected by the safety validator: {reason} "
            "This question cannot be answered safely."
        )
        # execute_query() is NEVER called when validation fails
        return response

    # ── Step 4: execute query ─────────────────────────────────────────────────
    result = execute_query(sql)
    response["result"] = result

    if result.get("error"):
        response["error"] = f"Query execution error: {result['error']}"
        return response

    # ── Step 5: explain result ────────────────────────────────────────────────
    explanation = explain_result(question, sql, result)
    response["explanation"] = explanation

    return response


# ── Manual verification entry point ──────────────────────────────────────────

if __name__ == "__main__":
    import json as _json

    sample_questions = [
        "Which product generated the most revenue?",
        "Show the top 5 products by sales.",
        "What is the capital of France?",  # off-topic
    ]

    print("Running run_agent() end-to-end pipeline test\n" + "=" * 60)

    for q in sample_questions:
        print(f"\nQ: {q}")
        out = run_agent(q)
        print(f"  SQL:         {out['sql'][:80]}{'...' if len(out['sql']) > 80 else ''}")
        print(f"  is_valid:    {out['is_valid']}")
        if out['result']:
            print(f"  rows:        {len(out['result']['rows'])}")
            print(f"  columns:     {out['result']['columns']}")
        print(f"  explanation: {out['explanation']}")
        print(f"  error:       {out['error']}")
        print("-" * 60)
