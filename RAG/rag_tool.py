from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.tools import tool

BASE_DIR = Path(__file__).parent
VECTORSTORE_PATH = BASE_DIR / "vectorstore"

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore = Chroma(
    collection_name="redis_knowledge",
    embedding_function=embeddings,
    persist_directory=str(VECTORSTORE_PATH)
)

@tool
def search_redis_knowledge(query: str) -> str:
    """Search the private Redis knowledge base for information about Redis, caching, persistence, and related backend concepts."""

    results = vectorstore.similarity_search_with_score(
        query,
        k=3
    )

    threshold = 1.2

    relevant_results = [
        (doc, score)
        for doc, score in results
        if score <= threshold
    ]

    if not relevant_results:
        return "No sufficiently relevant information was found in the Redis knowledge base."

    context = "\n\n".join(
        doc.page_content
        for doc, score in relevant_results
    )

    return f"Retrieved information from the knowledge base:\n{context}"