from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma


# Paths
BASE_DIR = Path(__file__).parent
VECTORSTORE_PATH = BASE_DIR / "vectorstore"


# 1. Load the same embedding model
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# 2. Connect to existing Chroma database
vectorstore = Chroma(
    collection_name="redis_knowledge",
    embedding_function=embeddings,
    persist_directory=str(VECTORSTORE_PATH)
)


# 3. Create retriever
retriever = vectorstore.as_retriever(
    search_kwargs={"k": 2}
)


# 4. Ask a question
query = input("Ask a question about Redis: ")


# 5. Retrieve relevant chunks
#results = retriever.invoke(query)
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
    print("\nNo sufficiently relevant information found.")
else:
    print("\n--- Relevant Documents ---")

    for i, (doc, score) in enumerate(relevant_results, start=1):
        print(f"\nResult {i}")
        print(f"Distance: {score:.4f}")
        print(f"Content: {doc.page_content}")


# 6. Display results
"""print("\n--- Retrieved Documents ---")

for i, (doc,score) in enumerate(results, start=1):
    print(f"\nResult {i}")
    print(f"Distance: {score:.4f}")
    print(f"Content: {doc.page_content}")"""