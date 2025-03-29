from dotenv import load_dotenv
import streamlit as st
import os
import psycopg2
import google.generativeai as genai
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")

template_prompt = """
You are an expert in converting English questions to SQL query!
The SQL database has the name agent and has a table called my_table 
with the following columns: model, mpg, cyl, disp, hp, drat, wt, qsec, vs, am, gear, carb.

Important Rules:
1. Always enclose string values in single quotes ('), not double quotes ("").
2. Do NOT include ``` or the word "sql" in the output.

Example 1 - How many entries of records are present?
The SQL command will be: SELECT COUNT(*) FROM my_table;

Example 2 - Tell me all records where the model is 'Volvo 142E'?
The SQL command will be: SELECT * FROM my_table WHERE model = 'Volvo 142E';

Example 3 - Get all records where horsepower (hp) is greater than 100?
The SQL command will be: SELECT * FROM my_table WHERE hp > 100;

Example 4- Find the most fuel-efficient car (mpg) for each cyl category.
The SQL command will be: SELECT cyl, model, MAX(mpg) FROM my_table GROUP BY cyl;

Example 5- Retrieve cars that have both high horsepower (hp > 150) and good mileage (mpg > 20).
The SQL command will be: SELECT * FROM my_table WHERE hp > 150 AND mpg > 20;

Example 5- Find the average horsepower of automatic vs. manual cars.
The SQL command will be: SELECT am, AVG(hp) FROM my_table GROUP BY am;
"""

class GraphState(TypedDict):
    sql: str
    result: str

def generate_sql(state: GraphState) -> GraphState:
    """Generate SQL from user input using Gemini API."""
    question = state["sql"]
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content([template_prompt, question])
    return {"sql": response.text.strip(), "result": ""}

def execute_sql(state: GraphState) -> GraphState:
    """Execute SQL on PostgreSQL and return results."""
    sql = state["sql"]
    try:
        conn = psycopg2.connect(
            dbname=db_name, user=db_user, password=db_password, host=db_host, port=db_port
        )
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        conn.commit()
        conn.close()
        return {"sql": sql, "result": rows}
    except Exception as e:
        return {"sql": sql, "result": [("Error", str(e))]}

# Define LangGraph Workflow
graph = StateGraph(GraphState)
graph.add_node("generate_sql", generate_sql)
graph.add_node("execute_sql", execute_sql)
graph.set_entry_point("generate_sql")
graph.add_edge("generate_sql", "execute_sql")
graph.add_edge("execute_sql", END)
app_instance = graph.compile()

# Streamlit UI
st.set_page_config(page_title="Gemini-Powered SQL Query Generator & Executor")
st.header("PostgreSQL  Agent!!")

question = st.text_input("Enter your question:", key="input")
submit = st.button("Generate SQL & Execute Query")

if submit:
    state = {"sql": question, "result": ""}
    final_state = app_instance.invoke(state)
    
    st.subheader("Generated SQL Query")
    st.code(final_state["sql"], language="sql")
    
    st.subheader("Query Result")
    if final_state["result"] and "Error" not in final_state["result"][0]:
        for row in final_state["result"]:
            st.write(row)
    else:
        st.error(final_state["result"][0][1])

# LangGraph Visualization
st.sidebar.header("LangGraph Visualization")
if st.sidebar.button("Show LangGraph Image"):
    with st.spinner("Generating LangGraph visualization..."):
        st.image(app_instance.get_graph().draw_mermaid_png())
