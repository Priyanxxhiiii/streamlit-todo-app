from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Date, Boolean

TABLE_NAME = "todo_table"
engine = create_engine("sqlite:///todo_db.db")

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

# Create the database and table
metadata_obj.create_all(bind=engine)
print("✅ Database and table created!")
