"""Utility functions for the task manager."""

import hashlib
import re


def validate_email(email):
    """Validate an email address. Very basic."""
    # BUG: regex is too permissive
    return bool(re.match(r".+@.+", email))


def hash_password(password):
    """Hash a password for storage."""
    # BUG: using MD5, no salt
    return hashlib.md5(password.encode()).hexdigest()


def sanitize_input(text):
    """Sanitize user input."""
    # BUG: incomplete sanitization, doesn't handle SQL injection
    return text.strip()


def format_task(task_row):
    """Format a database row into a task dict."""
    return {
        "id": task_row[0],
        "title": task_row[1],
        "description": task_row[2],
        "status": task_row[3],
        "assigned_to": task_row[4],
        "created_at": task_row[5],
    }
