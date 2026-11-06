"""
Recuperador Híbrido (Hybrid Retriever).

Combina dos formas de buscar que se complementan:

- Búsqueda VECTORIAL (Pinecone): entiende significado y sinónimos.
- Búsqueda LÉXICA (BM25): entiende coincidencias EXACTAS de palabras;
  mejor para nombres propios, funciones, siglas y términos técnicos.

EnsembleRetriever corre ambas búsquedas y fusiona los rankings con
Reciprocal Rank Fusion ponderado por `weights`.
"""

import json
import re
import unicodedata
from typing import List, Optional

from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

# EnsembleRetriever: en LangChain 0.x vive en langchain.retrievers,
# en LangChain 1.x se movió a langchain_classic.retrievers.
try:
    from langchain.retrievers import EnsembleRetriever
except ImportError:  # LangChain 1.x
    from langchain_classic.retrievers import EnsembleRetriever

from config import (
    PINECONE_API_KEY,
    INDEX_NAME,
    NAMESPACE,
    CORPUS_CACHE_PATH,
    TOP_K,
    BM25_WEIGHT,
    VECTOR_WEIGHT,
)
from embeddings import get_embeddings


def tokenize(text: str) -> List[str]:
    """
    Tokenizador para BM25: minúsculas, sin tildes y sin puntuación.
    Por defecto BM25Retriever solo hace text.split(), y entonces
    "vacaciones?" y "vacaciones" serían palabras distintas.
    Conserva '_' y dígitos, útiles en identificadores técnicos (field_validator).
    """
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.findall(r"\w+", text)


def load_cached_corpus() -> List[Document]:
    """Reconstruye los Document desde artifacts/corpus_cache.json (generado por la ingesta)."""
    try:
        with open(CORPUS_CACHE_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"No existe {CORPUS_CACHE_PATH}. Corré primero: python src/ingest.py"
        ) from exc
    return [Document(page_content=r["page_content"], metadata=r["metadata"]) for r in raw]


def build_bm25_retriever(k: int = TOP_K, category_filter: Optional[str] = None) -> BM25Retriever:
    """Recuperador léxico sobre el corpus local (filtrado por categoría si se pide)."""
    corpus = load_cached_corpus()
    if category_filter:
        corpus = [d for d in corpus if d.metadata.get("category") == category_filter]
        if not corpus:
            raise ValueError(f"No hay chunks con category='{category_filter}'.")
    retriever = BM25Retriever.from_documents(corpus, preprocess_func=tokenize)
    retriever.k = k
    return retriever


def build_vector_retriever(k: int = TOP_K, category_filter: Optional[str] = None):
    """Recuperador vectorial sobre Pinecone, acotado al namespace (y a la categoría si se pide)."""
    pc = Pinecone(api_key=PINECONE_API_KEY)
    vector_store = PineconeVectorStore(
        index=pc.Index(INDEX_NAME),
        embedding=get_embeddings(),
        text_key="text",
        namespace=NAMESPACE,
    )
    search_kwargs = {"k": k}
    if category_filter:
        search_kwargs["filter"] = {"category": {"$eq": category_filter}}
    return vector_store.as_retriever(search_kwargs=search_kwargs)


def build_hybrid_retriever(k: int = TOP_K, category_filter: Optional[str] = None) -> EnsembleRetriever:
    """
    BM25 + Pinecone en un único retriever. `k` es la cantidad de candidatos
    que trae CADA uno; el Ensemble devuelve la unión deduplicada (hasta 2k),
    por eso RAGSystem recorta al top-k final.
    """
    return EnsembleRetriever(
        retrievers=[
            build_bm25_retriever(k=k, category_filter=category_filter),
            build_vector_retriever(k=k, category_filter=category_filter),
        ],
        weights=[BM25_WEIGHT, VECTOR_WEIGHT],
    )
