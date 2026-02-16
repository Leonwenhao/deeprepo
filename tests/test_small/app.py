"""
A simple task management API.
Has several intentional issues for testing the RLM analyzer.
"""
from flask import Flask, request, jsonify
import sqlite3
import os

app = Flask(__name__)
DB_PATH = "tasks.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            assigned_to TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


@app.route("/tasks", methods=["GET"])
def list_tasks():
    conn = get_db()
    # BUG: SQL injection vulnerability
    status = request.args.get("status", "")
    if status:
        query = f"SELECT * FROM tasks WHERE status = '{status}'"
        tasks = conn.execute(query).fetchall()
    else:
        tasks = conn.execute("SELECT * FROM tasks").fetchall()
    # BUG: connection never closed
    return jsonify(tasks)


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.json
    # BUG: no validation of required fields
    conn = get_db()
    conn.execute(
        "INSERT INTO tasks (title, description, assigned_to) VALUES (?, ?, ?)",
        (data["title"], data.get("description"), data.get("assigned_to"))
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    # BUG: doesn't check if task existed
    # BUG: connection never closed
    return jsonify({"status": "deleted"})


@app.route("/tasks/<int:task_id>/assign", methods=["PUT"])
def assign_task(task_id):
    data = request.json
    user = data["user"]  # BUG: KeyError if user not in body
    conn = get_db()
    conn.execute(
        "UPDATE tasks SET assigned_to = ? WHERE id = ?",
        (user, task_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "assigned"})


# BUG: secret key hardcoded
app.secret_key = "super_secret_key_123"

if __name__ == "__main__":
    init_db()
    # BUG: debug mode in production
    app.run(debug=True, host="0.0.0.0", port=5000)
