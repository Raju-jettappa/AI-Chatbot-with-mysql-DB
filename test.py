import streamlit as st
from langchain_ollama import ChatOllama
from langchain_community.utilities import SQLDatabase

# -------------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------------
st.set_page_config(
    page_icon="⚡",
    page_title="AI + SQL Super Chat",
    layout="wide",
)

# -------------------------------------------------------------
# STYLES
# -------------------------------------------------------------
st.markdown("""
<style>
    .main-title { font-size: 34px; font-weight: 700; }
    .sub-title { color: #777; margin-bottom: 20px; }
    .sql-box {
        background: #1d1f21;
        color: #00FFBB;
        padding: 12px;
        border-radius: 6px;
        font-family: monospace;
        white-space: pre-wrap;
        border: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# SESSION
# -------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []

if "DB" not in st.session_state:
    st.session_state.DB = None


# -------------------------------------------------------------
# DATABASE CONNECTOR
# -------------------------------------------------------------
def connect_database(username, password, host, port, database):
    uri = f"mysql+mysqlconnector://{username}:{password}@{host}:{port}/{database}"
    return SQLDatabase.from_uri(uri)


def run_query(query):
    if st.session_state.DB:
        return st.session_state.DB.run(query)
    else:
        return "❌ Not connected to DB."


# -------------------------------------------------------------
# SQL SANITIZER (fixes your error)
# -------------------------------------------------------------
def clean_sql(sql: str) -> str:
    sql = sql.strip()

    # Remove markdown fences
    sql = sql.replace("```sql", "").replace("```", "").strip()

    # Remove accidental prefixes
    for prefix in ["sql ", "SQL ", "Sql ", "SQL:", "sql:", "query:", "Query:"]:
        if sql.lower().startswith(prefix.lower()):
            sql = sql[len(prefix):].strip()

    # Extra safety: remove leading "sql" alone
    if sql.lower().startswith("sql"):
        sql = sql[3:].strip()

    return sql


# -------------------------------------------------------------
# DECISION ENGINE
# -------------------------------------------------------------
def choose_mode(llm, user_msg, schema):
    decision_prompt = f"""
You decide whether the user message requires SQL.

DATABASE SCHEMA:
{schema}

USER MESSAGE:
{user_msg}

Return ONLY one word:
SQL → if database query / analytics / tables / filtering
CHAT → if general conversation
"""

    decision = llm.invoke(decision_prompt).content.strip().upper()
    return "SQL" if "SQL" in decision else "CHAT"


# -------------------------------------------------------------
# SQL GENERATION
# -------------------------------------------------------------
def generate_sql(llm, user_msg, schema):
    prompt = f"""
You MUST output ONLY a valid SQL query.

STRICT RULES:
- Output ONLY the SQL.
- Do NOT include backticks.
- Do NOT include ```sql.
- Do NOT explain.
- Do NOT add words like: SQL:, Query:, Here is, The SQL is, etc.
- If unsure, output ONLY: NO_SQL

DATABASE SCHEMA:
{schema}

USER QUESTION:
{user_msg}

SQL:
"""
    sql = llm.invoke(prompt).content.strip()
    return clean_sql(sql)


# -------------------------------------------------------------
# NORMAL CHAT
# -------------------------------------------------------------
def normal_chat(llm, user_msg):
    return llm.invoke(user_msg).content.strip()


# -------------------------------------------------------------
# MAIN UI
# -------------------------------------------------------------
st.markdown("<div class='main-title'>⚡ AI + SQL Super Chat</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Talk normally or ask database questions. AI automatically switches modes.</div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------
with st.sidebar:
    st.header("🧠 AI Settings")

    model_name = st.selectbox(
        "AI Model",
        ["deepseek-v3.1:671b-cloud","gpt-oss:120b-cloud", "llama3.2:latest", "llama3:latest"]
    )

    st.header("🗄 Database Connection")
    host = st.text_input("Host", "localhost")
    port = st.text_input("Port", "3306")
    username = st.text_input("Username", "root")
    password = st.text_input("Password", type="password")
    database = st.text_input("Database", "bagisto")

    if st.button("Connect Database"):
        try:
            st.session_state.DB = connect_database(username, password, host, port, database)
            st.success("✅ Connected!")
        except Exception as e:
            st.error(f"Failed to connect: {e}")


# -------------------------------------------------------------
# CHAT INPUT
# -------------------------------------------------------------
user_msg = st.chat_input("Ask anything — SQL or normal chat!")

if user_msg:
    st.session_state.history.append(("user", user_msg))

    llm = ChatOllama(model=model_name)

    schema = st.session_state.DB.get_table_info() if st.session_state.DB else "NO DATABASE"

    mode = choose_mode(llm, user_msg, schema)

    if mode == "CHAT" or not st.session_state.DB:
        result = normal_chat(llm, user_msg)

    else:  # SQL MODE
        sql_query = generate_sql(llm, user_msg, schema)

        if sql_query == "NO_SQL":
            result = "❌ I could not generate SQL for this question."
        else:
            try:
                sql_result = run_query(sql_query)

                # SQL shown to user
                st.markdown("### 🧠 Generated SQL:")
                st.markdown(f"<div class='sql-box'>{sql_query}</div>", unsafe_allow_html=True)

                summary = llm.invoke(
                    f"Summarize this SQL result in 1–2 sentences:\n{sql_result}"
                ).content.strip()

                result = f"### Result\n```\n{sql_result}\n```\n\n### Summary\n{summary}"

            except Exception as e:
                result = f"❌ SQL Error:\n```\n{e}\n```"

    st.session_state.history.append(("assistant", result))


# -------------------------------------------------------------
# SHOW CHAT HISTORY
# -------------------------------------------------------------
for speaker, message in st.session_state.history:
    st.chat_message(speaker).markdown(message)
