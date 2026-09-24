# SQL Data Analyst Agent

An agentic AI application that converts natural-language questions into safe SQL queries and analyzes a SQLite database.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Description

The SQL Data Analyst Agent is a self-contained agentic AI application that lets a non-technical user ask natural-language questions about a local SQLite sales database and receive accurate, verified, natural-language answers.

Instead of letting an LLM "hallucinate" numbers, the system uses the LLM strictly as a **reasoning and language layer** — it inspects the schema, generates SQL, and explains results — while all schema access, SQL validation, and query execution are handled by deterministic, controlled Python functions.

---

## Problem Statement

Most people who need answers from a database — students, analysts, and even many developers — don't know SQL well enough to write ad-hoc queries confidently. Existing "chat with your data" demos are often unsafe (letting the LLM run arbitrary queries) or misleadingly complex (RAG pipelines, vector DBs) for what is fundamentally a narrow, well-defined problem: translate a question into a safe, verifiable SQL query.

This project solves that narrow problem cleanly, with an architecture that is simple enough to explain in an interview and safe enough to demo publicly.

---

## Features

- **Natural-language to SQL** — ask questions in plain English, get SQL back
- **Agentic tool-calling** — the LLM uses `get_schema()` as a tool; it never touches the DB directly
- **Safety-first SQL validation** — deterministic keyword-based gatekeeper rejects all destructive SQL
- **Read-only execution** — SQLite connection opened in `mode=ro`; writes are impossible
- **Grounded explanations** — LLM is instructed to only reference values present in the actual result
- **Transparent output** — users always see the generated SQL, raw result table, and AI explanation
- **Clean Streamlit UI** — single-page app with example questions, schema viewer, and result display

---

## Architecture Diagram

```
User
  |
  v
Streamlit UI  (app.py)
  |
  v
run_agent()   (agent.py)
  |
  +--[Tool 1]--> get_schema()        (database.py) --> SQLite PRAGMA
  |
  +--[LLM 1]---> generate_sql()      Gemini API -> {sql, explanation}
  |
  +-----------> validate_sql()       (sql_validator.py) -- deterministic gatekeeper
  |                  |
  |              REJECTED? --> return error (execute_query never called)
  |
  +-----------> execute_query()      (database.py) --> SQLite read-only
  |
  +--[LLM 2]---> explain_result()   Gemini API -> plain-English explanation
  |
  v
Streamlit UI displays: SQL + Result Table + Explanation
```

---

## Agent Workflow Explanation

The system follows a strict linear pipeline:

1. **Schema inspection** — `get_schema()` queries SQLite PRAGMA metadata and returns a compact schema string that is injected into the LLM prompt.
2. **SQL generation** — `generate_sql()` sends the schema + user question to the Gemini LLM, requesting structured JSON output: `{"sql": "...", "explanation": "..."}`.
3. **SQL validation** — `validate_sql()` deterministically checks the generated SQL: rejects blank input, multiple statements, non-SELECT statements, and 14 blocked destructive keywords.
4. **Query execution** — `execute_query()` runs the validated SQL against `sales.db` in read-only mode, capping results at 100 rows.
5. **Result explanation** — `explain_result()` sends the original question, SQL, and actual result rows to the LLM, instructing it to only describe values present in the result.

**Key principle:** The LLM never touches the database, filesystem, or Python interpreter. All "doing" is performed by three predefined, controlled functions.

---

## Natural-Language-to-SQL Explanation

The LLM call in `generate_sql()` includes:
- The user's question
- The full database schema (from `get_schema()`)
- Explicit instructions: SQLite dialect, read-only only, reference only existing tables/columns
- A request for structured JSON output: `{"sql": "...", "explanation": "..."}`

Providing the schema directly in the prompt (rather than via RAG) ensures the LLM uses correct table and column names, dramatically reducing hallucinated identifiers.

If the question cannot be answered from the schema, the LLM returns an empty `sql` field and explains why — the app handles this gracefully rather than forcing a guess.

---

## SQL Safety Model

```
LLM-generated SQL (untrusted text)
         |
         v
validate_sql()  ← deterministic, no LLM involvement
         |
  ┌──────┴──────┐
  │             │
Invalid        Valid
  │             │
  v             v
Reject        execute_query()
(show error)  (read-only SQLite connection)
```

`validate_sql()` enforces:
1. Rejects empty/blank SQL
2. Rejects multiple statements (`;` injection)
3. Requires `SELECT` or `WITH` as the opening keyword
4. Word-boundary rejects: `INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH, DETACH, PRAGMA, REPLACE, TRUNCATE, VACUUM, GRANT, REVOKE`

`execute_query()` enforces as defense-in-depth:
- Opens SQLite with `?mode=ro` URI (read-only at OS level)
- Caps results at 100 rows via `fetchmany(100)`

---

## Database Schema

```sql
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    region      TEXT NOT NULL
);

CREATE TABLE products (
    product_id   INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category     TEXT NOT NULL,
    price        REAL NOT NULL
);

CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id  INTEGER NOT NULL,
    quantity    INTEGER NOT NULL,
    order_date  TEXT NOT NULL,   -- ISO format: YYYY-MM-DD
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id)  REFERENCES products(product_id)
);
```

`revenue` is a derived value (`quantity * price`), computed in SQL, never stored — this keeps the schema normalized and gives the agent a genuine reason to write JOIN + arithmetic queries.

The sample database contains 10 customers (4 regions), 10 products (4 categories), and 50 orders spread across Jan 2024 – Apr 2025.

---

## Technology Stack

| Package | Purpose | Rationale |
|---|---|---|
| `streamlit` | Web UI | Renders input, buttons, tables, and code blocks with minimal boilerplate |
| `pandas` | Tabular display | Converts SQL result rows into clean, interactive `st.dataframe` tables |
| `python-dotenv` | Config management | Loads `GEMINI_API_KEY` from `.env` without hardcoding secrets |
| `google-genai` | LLM SDK | Official Google Gemini SDK (non-deprecated); used for SQL generation and result explanation |
| `sqlite3` | Embedded database | Python standard library — no server, no extra dependency |
| `pytest` | Testing | Simple, widely used test runner; no elaborate setup needed for an MVP |

No agent framework (LangChain/LangGraph) is used. For an MVP with exactly two LLM calls and three deterministic tool functions, plain Python is simpler, more transparent, and easier to explain in an interview.

---

## Project Structure

```
sql-data-analyst-agent/
|
+-- app.py              # Streamlit UI entry point
+-- agent.py            # LLM orchestration: SQL generation + explanation + pipeline
+-- database.py         # get_schema(), execute_query(), connection handling
+-- sql_validator.py    # validate_sql(): safety gatekeeper
+-- create_db.py        # One-time script that builds sales.db with sample data
+-- sales.db            # Shipped SQLite database file
+-- requirements.txt
+-- .env.example
+-- .gitignore
+-- README.md
+-- tests/
    +-- test_agent.py   # 7 pytest checks
```

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/sql-data-analyst-agent.git
cd sql-data-analyst-agent

# 2. Create and activate a virtual environment
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Generate the database (sales.db is also shipped, but this makes it re-runnable)
python create_db.py
```

---

## Environment Setup

Copy `.env.example` to `.env` and add your Gemini API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

Get a free Gemini API key at: https://aistudio.google.com/app/apikey

> **Security:** `.env` is git-ignored. Never commit your real API key.

---

## Usage

```bash
# Start the Streamlit app
streamlit run app.py
```

Open http://localhost:8501 in your browser.

1. The **Database Overview** section shows the schema at the top.
2. Click any **Example Question** chip to pre-fill the input.
3. Type your own question or use an example, then click **Analyze**.
4. The app displays the **Generated SQL**, the **Query Result** table, and an **AI Explanation**.

---

## Example Questions

```
How many orders were placed?
What is the average order value?
Which customer spent the most?
Which product generated the most revenue?
What are the top 5 products by sales?
Show the 5 largest orders.
Which region has the highest revenue?
Which product category performs best?
How many customers are from each region?
Show monthly revenue.
```

---

## Example Generated SQL

**Question:** Which product generated the most revenue?

```sql
SELECT p.product_id, p.product_name,
       SUM(o.quantity * p.price) AS total_revenue
FROM products p
JOIN orders o ON p.product_id = o.product_id
GROUP BY p.product_id, p.product_name
ORDER BY total_revenue DESC
LIMIT 1;
```

---

## Example Output

**Question:** Which product generated the most revenue?

**Generated SQL:**
```sql
SELECT p.product_name, SUM(o.quantity * p.price) AS total_revenue
FROM products p JOIN orders o ON p.product_id = o.product_id
GROUP BY p.product_name ORDER BY total_revenue DESC LIMIT 1;
```

**Query Result:**

| product_name | total_revenue |
|---|---|
| Laptop Pro | 11699.91 |

**AI Explanation:**
> The product that generated the most revenue is the Laptop Pro, with total sales of $11,699.91.

---

## Security Considerations

- **Read-only database access** — SQLite connection opened with `?mode=ro` URI; writes are impossible at the OS level.
- **SQL validation gatekeeper** — `validate_sql()` is deterministic and independent of the LLM. It rejects all non-SELECT statements before `execute_query()` is ever called.
- **No bypass path** — `execute_query()` can only be reached through `run_agent()`, which always calls `validate_sql()` first. The Streamlit UI exposes no raw SQL input.
- **API key security** — loaded only from environment variables via `python-dotenv`; never hardcoded; `.env` is git-ignored.
- **Row cap** — results are always capped at 100 rows regardless of what the SQL requests.
- **No arbitrary code execution** — the LLM only produces text (SQL + explanations). It cannot execute Python or access the filesystem.

---

## Limitations

> **This is a portfolio / learning MVP. It is NOT production-ready.**

- **Read-only, single database** — only `sales.db` (SQLite) is supported. No Postgres, MySQL, or write access.
- **Small dataset** — 10 customers, 10 products, 50 orders. Not representative of production data volumes.
- **No authentication** — anyone with access to the URL can query the database.
- **No conversation history** — each question is independent; no follow-up question context.
- **Keyword-based SQL validation** — basic protection suitable for a demo; not a full SQL parser/AST.
- **Single-user** — no multi-tenancy, rate limiting, or session isolation.
- **No production hardening** — no logging, monitoring, error tracking, or CI/CD pipeline.
- **Gemini API dependency** — requires a valid API key and internet access; subject to rate limits.

---

## Future Improvements

- Support for additional SQL dialects / production databases (Postgres, MySQL)
- Query result caching and conversation-level memory (follow-up questions)
- Visualization of results (auto-generated charts for aggregation queries)
- User authentication and per-user query history
- More sophisticated SQL validation (AST-based parsing instead of keyword matching)
- Support for larger, multi-table, real-world datasets
- Automated evaluation harness for SQL generation accuracy
- Deployment guide (e.g., Streamlit Community Cloud) with production-hardening notes

---

## Screenshots

> _Screenshots will be added after first deployment._

| App view | Description |
|---|---|
| Main UI | Schema overview, example questions, input |
| Query result | Generated SQL + DataFrame + AI explanation |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

```
Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```
