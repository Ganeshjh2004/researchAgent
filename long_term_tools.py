from langchain_core.tools import tool
from langgraph.runtime import get_runtime


@tool
def save_user_memory(
    user_id: str,
    key: str,
    value: str,
) -> str:

    """Save a long-term fact about a user."""

    runtime = get_runtime()

    runtime.store.put(
        ("users", user_id),
        key,
        {"value": value},
    )

    return f"Saved memory: {key} = {value}"


@tool
def get_user_memory(
    user_id: str,
    key: str,
) -> str:

    """Retrieve a long-term fact about a user."""

    runtime = get_runtime()

    memory = runtime.store.get(
        ("users", user_id),
        key,
    )

    if memory is None:
        return "No memory found."

    return str(memory.value)