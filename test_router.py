from router import route_query

test_queries = [
    "Remember that my preferred backend language is Golang",
    "What is my preferred backend language?",
    "What are the Redis persistence mechanisms in my knowledge base?",
    "Save the findings to report.txt",
    "Search the web for the latest AI agent frameworks",
    "Explain what an AI agent is",
]

for query in test_queries:
    print(f"Query: {query}")
    print(f"Route: {route_query(query)}")
    print("-" * 40)