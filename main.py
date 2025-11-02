import streamlit as st
from langchain_ollama import ChatOllama
from langchain_community.utilities import SQLDatabase

def connect_database(username, password, host, port, database):
    uri = f"mysql+mysqlconnector://{username}:{password}@{host}:{port}/{database}"
    db = SQLDatabase.from_uri(uri)
    return db

def run_query(query):
    if "DB" in st.session_state and st.session_state.DB:
        return st.session_state.DB.run(query)
    else:
        return "Please connect to database"

def main():
    st.set_page_config(page_icon="🤖", page_title="Chat with MySQL DB", layout="centered")
    with st.sidebar:
        st.title("Connect to Database")
        host = st.text_input("Host", "localhost")
        port = st.text_input("Port", "3306")
        username = st.text_input("Username", "root")
        password = st.text_input("Password", type="password")
        database = st.text_input("Database", "dbname")

        if st.button("Connect"):
            try:
                st.session_state.DB = connect_database(username, password, host, port, database)
                st.success("Database connected!")
            except Exception as e:
                st.error(f"Failed to connect: {e}")

    question = st.chat_input("Ask a question about your database:")

    if question:
        if "DB" not in st.session_state or not st.session_state.DB:
            st.error("Please connect to the database first.")
            return

        llm = ChatOllama(model="llama3.2")  # or any small model
        db_schema = st.session_state.DB.get_table_info()

        # STRONGER PROMPT enforcing SQL-only answers
        prompt = (
            f"Below is the schema of my SQL database:\n{db_schema}\n"
            "Your job is to write ONLY a VALID SQL query to answer the user's question below. "
            "Do not explain. If you cannot answer, reply with NO_SQL ONLY and nothing else.\n"
            f"User question: {question}\n"
            "SQL:"
        )

        sql_query = llm.invoke(prompt).content.strip()

        # Validate the LLM's response looks like valid SQL
        valid_sql_starts = ("select", "insert", "update", "delete")
        if (
            "NO_SQL" in sql_query
            or not any(sql_query.lower().startswith(cmd) for cmd in valid_sql_starts)
        ):
            st.error("Sorry, I couldn't generate a valid SQL query for your question.")
            st.markdown(f"**LLM responded:**\n\n``````")
            return

        try:
            result = run_query(sql_query)
        except Exception as e:
            st.error(f"SQL execution failed: {e}")
            st.markdown(f"**Generated SQL was:**\n\n``````")
            return

        # Now, natural language the output for user
        response_prompt = (
            f"You are an AI assistant. The user's question was:\n{question}\n"
            f"The SQL answer result was:\n{result}\n"
            "Summarize the result for the user in one sentence."
        )
        response = llm.invoke(response_prompt).content.strip()

        st.chat_message("user").markdown(question)
        st.chat_message("assistant").markdown(response)
        st.markdown(f"**(Debug info – SQL issued):**\n\n``````")

if __name__ == "__main__":
    main()
