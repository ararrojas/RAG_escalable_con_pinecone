"""
RAGSystem: encapsula el EnsembleRetriever (BM25 + Pinecone).

Recibe una consulta y devuelve los top-k documentos (por defecto 5)
combinando resultados léxicos y semánticos.

Uso:
    python src/rag_system.py "¿Cómo uso Depends en FastAPI?"
"""

import sys
from typing import List, Optional

from langchain_core.documents import Document

from config import TOP_K, CANDIDATES_PER_RETRIEVER, require_env
from hybrid_retriever import build_hybrid_retriever


class RAGSystem:
    def __init__(
        self,
        k: int = TOP_K,
        candidates_per_retriever: int = CANDIDATES_PER_RETRIEVER,
        category_filter: Optional[str] = None,
    ):
        self.k = k
        # Cada retriever trae más candidatos que k: la fusión elige mejor
        # con más material y después cortamos al top-k final.
        self.retriever = build_hybrid_retriever(
            k=max(candidates_per_retriever, k), category_filter=category_filter
        )

    def query(self, question: str) -> List[Document]:
        """Devuelve exactamente (hasta) k documentos, ya fusionados y ordenados."""
        return self.retriever.invoke(question)[: self.k]


if __name__ == "__main__":
    require_env()
    question = " ".join(sys.argv[1:]) or "¿Cómo reemplazo una dependencia en los tests de FastAPI?"
    rag = RAGSystem()
    print(f"Pregunta: {question}\n")
    for i, doc in enumerate(rag.query(question), 1):
        meta = doc.metadata
        print(f"{i}. [{meta.get('doc_id')}] ({meta.get('source')}) {doc.page_content[:120].strip()}...")
