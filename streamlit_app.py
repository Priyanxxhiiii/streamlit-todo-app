import time 
import streamlit as st

from dataclasses import dataclass
from datetime import date
from typing import Dict

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Integer,
    MetaData,
    String,
    Table,
)

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ✅ Detect correct DB path for Streamlit Cloud vs Local
DB_FOLDER = "/mount/src" if os.getenv("STREAMLIT_RUNTIME") else os.getcwd()
DB_PATH = os.path.join(DB_FOLDER, "todo_db.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ✅ Set up SQLAlchemy
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()

# ✅ Fake connection object for compatibility
class Connection:
    def __init__(self, engine, session):
        self.engine = engine
        self.session = session

conn = Connection(engine, session)

# ✅ Data model
@dataclass
class Todo:
    id: int
    title: str
    description: str
    created_at: date
    due_at: date
    done: bool

    @staticmethod
    def from_row(row):
        return Todo(
            id=row.id,
            title=row.title,
            description=row.description,
            created_at=row.created_at,
            due_at=row.due_at,
            done=row.done
        )

# Constants
TABLE_NAME = "todo_table"
SESSION_STATE_TODO_KEY = "todos_data"

@st.cache_resource
def connect_table():
    metadata_obj = MetaData()
    todo_table = Table(
        TABLE_NAME,
        metadata_obj,
        Column("id", Integer, primary_key=True),
        Column("title", String),
        Column("description", String),
        Column("created_at", Date),
        Column("due_at", Date),
        Column("done", Boolean),
    )
    metadata_obj.create_all(conn.engine)
    return metadata_obj, todo_table

def load_all_todos(connection, table) -> Dict[int, Todo]:
    stmt = sa.select(table).order_by(table.c.id)
    with connection.session as session:
        result = session.execute(stmt)
        all_todos = [Todo.from_row(row) for row in result]
        return {todo.id: todo for todo in all_todos}

def load_todo(connection, table, todo_id):
    stmt = sa.select(table).where(table.c.id == todo_id)
    with connection.session as sess:
        result = sess.execute(stmt)
        row = result.first()
        return Todo.from_row(row)

def create_todo_callback(connection, table):
    title = st.session_state.new_todo_form__title
    description = st.session_state.new_todo_form__description
    due_date = st.session_state.new_todo_form__due_date 
    if not title.strip():
        st.warning("Title cannot be empty.")
        return
    new_todo = {
        "title": title,
        "description": description,
        "created_at": date.today(),
        "due_at": due_date,
        "done": False
    }
    stmt = table.insert().values(**new_todo)
    with connection.session as session:
        session.execute(stmt)
        session.commit()
    st.session_state[SESSION_STATE_TODO_KEY] = load_all_todos(connection, table)
    st.success("✅ Todo created successfully!")

def mark_done_callback(connection, table, todo_id):
    done_status = st.session_state[SESSION_STATE_TODO_KEY][todo_id].done
    stmt = table.update().where(table.c.id == todo_id).values(done=not done_status)
    with connection.session as session:
        session.execute(stmt)
        session.commit()
    st.session_state[SESSION_STATE_TODO_KEY][todo_id] = load_todo(connection, table, todo_id)

def switch_edit_callback(todo_id: int):
    key = f"currently_editing_{todo_id}"
    st.session_state[key] = not st.session_state.get(key, False)

def delete_todo_callback(connection, table, todo_id):
    stmt = table.delete().where(table.c.id == todo_id)
    with connection.session as session:
        session.execute(stmt)
        session.commit()
    st.session_state[SESSION_STATE_TODO_KEY] = load_all_todos(connection, table)

@st.fragment
def view_todo(todo_id: int):
    if f"currently_editing_{todo_id}" not in st.session_state:
        st.session_state[f"currently_editing_{todo_id}"] = False

    todo: Todo = st.session_state[SESSION_STATE_TODO_KEY][todo_id]
    currently_editing = st.session_state[f"currently_editing_{todo_id}"]

    if not currently_editing:
        with st.container(border=True):
            st.subheader(todo.title)
            st.markdown(todo.description)
            st.markdown(f"Due: {todo.due_at}")
            st.markdown(f"Done: {'✅' if todo.done else '❌'}")

            done_col, edit_col, delete_col = st.columns(3)
            done_col.button(
                "Done", 
                key=f"view_todo_{todo_id}__done",
                use_container_width=True,
                icon=":material/check_circle:",
                type="primary",
                on_click=mark_done_callback,
                args=(conn, todo_table, todo_id),
            )
            edit_col.button(
                "Edit",
                key=f"view_todo_{todo_id}__edit",
                icon=":material/edit:",
                use_container_width=True,
                on_click=switch_edit_callback,
                args=(todo_id,)
            )
            if delete_col.button(
                "Delete",
                key=f"view_todo_{todo_id}__delete",
                icon=":material/delete:",
                use_container_width=True,
            ):
                delete_todo_callback(conn, todo_table, todo_id)
                st.rerun(scope="app")
    else:
        with st.form(f"update_{todo_id}"):
            st.subheader(f":material/edit: Editing Todo - {todo.title}")
            title = st.text_input("Todo Title", value=todo.title, key=f"edit_todo_form_{todo_id}__title")
            description = st.text_area("Todo Description", value=todo.description, key=f"edit_todo_form_{todo_id}__description")
            due_at = st.date_input("Due Date", value=todo.due_at, key=f"edit_todo_form_{todo_id}__due_date")
            submit_col, cancel_col = st.columns(2)
            submit = submit_col.form_submit_button("Edit Todo", type="primary", use_container_width=True)
            cancel = cancel_col.form_submit_button("Cancel", use_container_width=True)

            if cancel:
                switch_edit_callback(todo_id)
                st.rerun()
            if submit:
                updated_todo = {
                    "title": title,
                    "description": description,
                    "due_at": due_at
                }
                stmt = todo_table.update().where(todo_table.c.id == todo_id).values(**updated_todo)
                with conn.session as session:
                    session.execute(stmt)
                    session.commit()
                st.session_state[SESSION_STATE_TODO_KEY][todo_id] = load_todo(conn, todo_table, todo_id)
                switch_edit_callback(todo_id)
                st.rerun()

# ✅ MAIN APP VIEW
st.title("Todo App")
metadata, todo_table = connect_table()

if SESSION_STATE_TODO_KEY not in st.session_state:
    st.session_state[SESSION_STATE_TODO_KEY] = load_all_todos(conn, todo_table)

with st.sidebar:
    st.subheader("Configuration")
    show_completed = st.checkbox("Show Completed Todos", value=False)

# Show only todos depending on checkbox
for todo_id, todo in st.session_state[SESSION_STATE_TODO_KEY].items():
    if show_completed or not todo.done:
        view_todo(todo_id)

with st.form("add_todo", clear_on_submit=True):
    st.subheader(":material/add_circle: Create todo")
    st.text_input("Todo Title", key="new_todo_form__title")
    st.text_area("Todo Description", key="new_todo_form__description")
    st.date_input("Due Date", key="new_todo_form__due_date")
    st.form_submit_button(
        "Create Todo",
        type="primary",
        on_click=create_todo_callback,
        args=(conn, todo_table)
    )
