from dotenv import load_dotenv

load_dotenv()
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate


# Paths
BASE_DIR = Path(__file__).parent
VECTORSTORE_PATH = BASE_DIR / "vectorstore"


# 1. Load embeddings
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# 2. Load existing vector store
vectorstore = Chroma(
    collection_name="redis_knowledge",
    embedding_function=embeddings,
    persist_directory=str(VECTORSTORE_PATH)
)


# 3. Create retriever
retriever = vectorstore.as_retriever(
    search_kwargs={"k": 2}
)


# 4. Initialize Groq
llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0
)


# 5. Create prompt
prompt = ChatPromptTemplate.from_template("""
You are a helpful technical assistant.

Answer the question using ONLY the provided context.

If the answer is not present in the context,
clearly say that you don't have enough information.

Context:
{context}

Question:
{question}

Answer:
""")


# 6. Ask user
question = input("Ask a question about your documents: ")


# 7. Retrieve relevant chunks
documents = retriever.invoke(question)


# 8. Combine retrieved text
context = "\n\n".join(
    doc.page_content for doc in documents
)


# 9. Build prompt
messages = prompt.invoke({
    "context": context,
    "question": question
})


# 10. Generate answer
response = llm.invoke(messages)


print("\n--- Retrieved Context ---")
print(context)

print("\n--- AI Answer ---")
print(response.content)