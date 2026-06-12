import streamlit as st
import sqlite3
import plotly.express as px
import pandas as pd
import os
from groq import Groq

# Secure API key using Streamlit secrets
os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
client = Groq()

st.set_page_config(page_title="Insight-SQL", layout="wide")
st.title("🤖 LLM-Powered Text-to-SQL Analytics Agent")

def get_schema():
    conn = sqlite3.connect("business_analytics.db")
    cursor = conn.cursor()
    schema = ""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    for table in tables:
        table_name = table[0]
        cursor.execute("PRAGMA table_info(" + table_name + ")")
        columns = cursor.fetchall()
        cols = ", ".join([col[1] + " (" + col[2] + ")" for col in columns])
        schema += "Table: " + table_name + "\nColumns: " + cols + "\n\n"
    conn.close()
    return schema

def execute_sql(sql):
    conn = sqlite3.connect("business_analytics.db")
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df

def text_to_sql(question, max_retries=3):
    schema = get_schema()
    messages = [
        {"role": "system", "content": "You are a SQL expert. Convert natural language to SQL.\nSchema:\n" + schema + "\nReturn ONLY SQL, no explanation."},
        {"role": "user", "content": question}
    ]
    for attempt in range(max_retries):
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        sql = response.choices[0].message.content.strip()
        sql = sql.replace("```sql","").replace("```","").strip()
        try:
            df = execute_sql(sql)
            return sql, df, None
        except Exception as e:
            messages.append({"role": "assistant", "content": sql})
            messages.append({"role": "user", "content": "Error: " + str(e) + ". Fix and return only SQL."})
    return None, None, "Failed after 3 retries"

def recommend_chart(df):
    if df is None or df.empty:
        return None
    if len(df.columns) == 2:
        col1, col2 = df.columns
        if pd.api.types.is_numeric_dtype(df[col2]):
            if len(df) <= 5:
                return px.pie(df, names=col1, values=col2, title="Distribution")
            return px.bar(df, x=col1, y=col2, title="Results")
    return None

with st.sidebar:
    st.header("📊 Schema Explorer")
    schema = get_schema()
    for line in schema.split("\n"):
        if line.startswith("Table:"):
            st.subheader(line)
        elif line.startswith("Columns:"):
            st.caption(line)
    st.divider()
    st.header("📝 Query History")
    if "history" not in st.session_state:
        st.session_state.history = []
    for h in st.session_state.history[-5:]:
        st.caption("• " + h)

question = st.text_input("💬 Ask a question about your data:", placeholder="e.g. What is the total revenue by region?")

col1, col2 = st.columns([1, 4])
with col1:
    run = st.button("🚀 Run Query", use_container_width=True)
with col2:
    if st.button("🔄 Clear History", use_container_width=True):
        st.session_state.history = []

if run and question:
    with st.spinner("🤔 Generating SQL..."):
        sql, df, error = text_to_sql(question)
    if error:
        st.error("❌ " + error)
    else:
        st.session_state.history.append(question)
        with st.expander("🔍 Generated SQL", expanded=True):
            st.code(sql, language="sql")
        st.subheader("📋 Results")
        st.dataframe(df, use_container_width=True)
        chart = recommend_chart(df)
        if chart:
            st.subheader("📈 Auto Chart")
            st.plotly_chart(chart, use_container_width=True)
        with st.spinner("📝 Summarizing..."):
            summary = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Summarize this data in one sentence: " + df.to_string()}]
            )
            st.info("💡 " + summary.choices[0].message.content)