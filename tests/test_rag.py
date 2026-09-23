from rag.retrieval.service import RAGService
def test_rag_returns_procedure(tmp_path):
 s=RAGService(str(tmp_path/"index.joblib"),"rag/documents");s.ingest()
 hits=s.search("BFP-101 high discharge pressure operating procedure",["BFP-101"])
 assert hits and "High Discharge Pressure" in hits[0]["section"]
