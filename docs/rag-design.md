# RAG Design

The workflow uses retrieved alarm evidence to construct the retrieval query. Markdown procedures are sectioned into chunks and indexed with a persisted TF-IDF representation. Asset identifiers are preserved as metadata and used for filtering, while n-gram matching handles exact equipment/alarm terminology.

Every returned chunk has a document and section citation. Empty retrieval lowers response confidence and produces a warning. Retrieved documents are treated as untrusted reference data and cannot override application controls.

The retrieval abstraction is deliberately isolated so an enterprise deployment can replace the local index with a dense embedding store plus BM25/hybrid retrieval without changing the copilot/MCP contract.
