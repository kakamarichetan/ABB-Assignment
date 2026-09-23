from rag.retrieval.service import RAGService
import os
RAGService(os.getenv("RAG_INDEX_PATH","rag/index/index.joblib"),os.getenv("RAG_DOCUMENT_PATH","rag/documents")).ingest()
print("RAG index created")
