from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

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

print("Total records:", vectorstore._collection.count())