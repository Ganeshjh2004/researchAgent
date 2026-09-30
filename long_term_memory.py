from langgraph.store.memory import InMemoryStore


store = InMemoryStore()


# Save a long-term memory
store.put(
    ("users", "ganesh"),
    "learning",
    {
        "topic": "AI agents",
        "language": "Python",
    },
)


# Retrieve the memory
memory = store.get(
    ("users", "ganesh"),
    "learning",
)


print(memory.value)