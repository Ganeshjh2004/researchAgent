from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma


# Paths
BASE_DIR = Path(__file__).parent
DOCUMENT_PATH = BASE_DIR / "documents" / "redis_notes.txt"
VECTORSTORE_PATH = BASE_DIR / "vectorstore"


# 1. Load document
loader = TextLoader(
    str(DOCUMENT_PATH),
    encoding="utf-8"
)

documents = loader.load()

print(f"Loaded documents: {len(documents)}")


# 2. Split into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=30
)

chunks = text_splitter.split_documents(documents)

print(f"Total chunks: {len(chunks)}")


# Inspect chunks
for i, chunk in enumerate(chunks):
    print(f"\n--- Chunk {i + 1} ---")
    print(chunk.page_content)


# 3. Initialize embedding model
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# 4. Store chunks and embeddings
ids = [
    f"redis_notes_chunk_{i}"
    for i in range(len(chunks))
]

vectorstore = Chroma(
    collection_name="redis_knowledge",
    embedding_function=embeddings,
    persist_directory=str(VECTORSTORE_PATH)
)
vectorstore.reset_collection()

vectorstore.add_documents(
    documents=chunks,
    ids=ids
)

print("\nDocuments successfully indexed!")