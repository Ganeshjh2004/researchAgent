def route_query(query: str) -> str:
    query = query.lower().strip()

    # Memory
    memory_keywords = [
        "remember that",
        "remember this",
        "save my preference",
        "what is my preferred",
        "what do you remember about me",
        "recall my",
    ]

    if any(keyword in query for keyword in memory_keywords):
        return "memory"

    # RAG
    rag_keywords = [
        "knowledge base",
        "redis persistence",
        "redis caching",
        "according to my documents",
        "according to my knowledge base",
    ]

    if any(keyword in query for keyword in rag_keywords):
        return "rag"

    # File operations
    file_keywords = [
        "save to",
        "save the findings",
        "write to file",
        "save the research",
    ]

    if any(keyword in query for keyword in file_keywords):
        return "file"

    # General research
    research_keywords = [
        "search the web",
        "latest",
        "current news",
        "research",
    ]

    if any(keyword in query for keyword in research_keywords):
        return "research"

    return "general"