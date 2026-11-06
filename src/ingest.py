"""
Pipeline de Ingesta en Pinecone.

Flujo:
    1. Cargar documentos (PDF, Markdown/TXT o JSON) desde data/raw/.
    2. Trocear (chunking) cada documento en fragmentos de ~650 tokens
       con RecursiveCharacterTextSplitter.
    3. Generar embeddings y subir cada chunk a Pinecone con metadatos
       (doc_id, source, page, category) y el TEXTO ORIGINAL dentro de la
       metadata (no hace falta otra base de datos para mostrar el chunk).
    4. Guardar una copia local de los chunks (artifacts/corpus_cache.json)
       que usa el recuperador BM25 y la evaluación.

Uso:
    python src/ingest.py            # ingesta (upsert idempotente)
    python src/ingest.py --reset    # borra el namespace antes de ingestar
"""

import argparse
import hashlib
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import tiktoken
from pinecone import Pinecone
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_pinecone import PineconeVectorStore

from config import (
    PINECONE_API_KEY,
    INDEX_NAME,
    NAMESPACE,
    CHUNK_SIZE_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    DATA_DIR,
    CORPUS_CACHE_PATH,
    CATEGORY_BY_DOC,
    require_env,
)
from setup_pinecone import ensure_index_exists
from embeddings import get_embeddings


# --- 1. Carga de documentos ---

def load_documents(data_dir: str) -> List[Document]:
    """
    Recorre data/raw y carga cada archivo soportado como uno o más Document.
    PyPDFLoader genera un Document por página (con metadata 'page').
    """
    documents: List[Document] = []

    for file_path in sorted(Path(data_dir).glob("*")):
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()
        file_documents: List[Document] = []

        if suffix == ".pdf":
            file_documents = PyPDFLoader(str(file_path)).load()

        elif suffix in (".md", ".txt"):
            file_documents = TextLoader(str(file_path), encoding="utf-8").load()

        elif suffix == ".json":
            # Formato esperado: [{"text": "...", "category": "...", ...}, ...]
            with open(file_path, "r", encoding="utf-8") as f:
                records = json.load(f)
            file_documents = [
                Document(
                    page_content=record["text"],
                    metadata={k: v for k, v in record.items() if k != "text"},
                )
                for record in records
            ]
        else:
            continue  # extensión no soportada (.gitkeep, etc.)

        # Siempre guardamos solo el NOMBRE del archivo como source (PyPDFLoader
        # y TextLoader ponen la ruta completa, que no queremos en la metadata).
        for doc in file_documents:
            doc.metadata["source"] = file_path.name
            if file_path.stem in CATEGORY_BY_DOC:
                doc.metadata.setdefault("category", CATEGORY_BY_DOC[file_path.stem])
            if suffix in (".md", ".txt"):
                doc.metadata.setdefault("page", 1)  # sin paginación: una sola "página"

        documents.extend(file_documents)

    return documents


# --- 2. Chunking ---

def build_text_splitter() -> RecursiveCharacterTextSplitter:
    """
    Mide la longitud en TOKENS (tiktoken cl100k_base, el tokenizador de
    OpenAI; aproxima bien el conteo de Gemini), porque mide el tamaño del chunk.
    """
    encoding = tiktoken.get_encoding("cl100k_base")

    def token_length(text: str) -> int:
        return len(encoding.encode(text))

    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
        length_function=token_length,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pinecone solo acepta str, int, float, bool o lista de str en la metadata.
    Descartamos los None (rompen el upsert) y convertimos lo demás a str.
    """
    clean: Dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def make_chunk_id(source: str, page: Any, index: int) -> str:
    """ID DETERMINISTA: re-ingestar el mismo contenido sobrescribe, no duplica."""
    return hashlib.md5(f"{source}|{page}|{index}".encode("utf-8")).hexdigest()


def chunk_documents(
    documents: List[Document],
    splitter: RecursiveCharacterTextSplitter = None,
    category: str = "general",
) -> List[Document]:
    """
    Trocea cada documento y agrega metadata a cada chunk:
    - doc_id:   documento lógico de origen (lo usa el golden set). Por defecto
                es el nombre del archivo sin extensión; un JSON puede traer
                su propio "doc_id" por registro.
    - chunk_id: identificador único y determinista del fragmento.
    - source, page, category: trazabilidad y filtrado.
    - text:     contenido original del chunk, guardado en la metadata.
    """
    splitter = splitter or build_text_splitter()
    chunks: List[Document] = []
    per_source_counter: Dict[str, int] = defaultdict(int)

    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        doc_id = doc.metadata.get("doc_id", Path(source).stem)

        page = doc.metadata.get("page")
        if page is not None and source.lower().endswith(".pdf"):
            page = int(page) + 1  # PyPDFLoader cuenta desde 0; guardamos página humana

        extra = {k: v for k, v in doc.metadata.items()
                 if k not in ("source", "page", "doc_id", "category")}

        for split_text in splitter.split_text(doc.page_content):
            index = per_source_counter[source]
            per_source_counter[source] += 1

            chunk_metadata = {
                **extra,
                "doc_id": doc_id,
                "chunk_id": make_chunk_id(source, page, index),
                "source": source,
                "category": doc.metadata.get("category", category),
                "text": split_text,
            }
            if page is not None:
                chunk_metadata["page"] = page

            chunks.append(Document(page_content=split_text,
                                   metadata=sanitize_metadata(chunk_metadata)))

    return chunks


# --- 3. Subida a Pinecone ---

def reset_namespace(pc: Pinecone) -> None:
    """Borra todos los vectores del namespace (útil para reconstruir el índice limpio)."""
    try:
        pc.Index(INDEX_NAME).delete(delete_all=True, namespace=NAMESPACE)
        print(f"[RESET] Namespace '{NAMESPACE}' vaciado.")
    except Exception as exc:  # namespace inexistente en la primera corrida
        print(f"[RESET] Nada que borrar ({exc.__class__.__name__}).")


def wait_until_indexed(pc: Pinecone, expected: int, timeout: int = 60) -> None:
    """Pinecone es eventualmente consistente: esperamos a que los vectores sean consultables."""
    index = pc.Index(INDEX_NAME)
    deadline = time.time() + timeout
    while time.time() < deadline:
        stats = index.describe_index_stats()
        summary = (stats.namespaces or {}).get(NAMESPACE)
        if summary is None:
            count = 0
        elif isinstance(summary, dict):
            count = summary.get("vector_count", 0)
        else:
            count = getattr(summary, "vector_count", 0)
        if count >= expected:
            return
        time.sleep(2)
    print("[WARN] El índice aún no refleja todos los vectores; si el recall da bajo, "
          "esperá unos segundos y volvé a evaluar.")


def upsert_chunks(chunks: List[Document], reset: bool = False) -> None:
    """
    Sube los chunks con PineconeVectorStore: genera cada embedding, arma el
    vector (id, values, metadata) y hace upsert() en el namespace.
    """
    pc = Pinecone(api_key=PINECONE_API_KEY)
    ensure_index_exists(pc)
    if reset:
        reset_namespace(pc)

    vector_store = PineconeVectorStore(
        index=pc.Index(INDEX_NAME),
        embedding=get_embeddings(),
        text_key="text",  # el texto vive en metadata["text"]
    )
    ids = [chunk.metadata["chunk_id"] for chunk in chunks]
    vector_store.add_documents(chunks, ids=ids, namespace=NAMESPACE)
    wait_until_indexed(pc, expected=len(chunks))


def cache_corpus_locally(chunks: List[Document]) -> None:
    """
    Guarda los chunks en JSON. BM25 es un índice léxico en memoria (no vive en
    Pinecone), así que necesita este corpus para reconstruirse.
    """
    os.makedirs(os.path.dirname(CORPUS_CACHE_PATH), exist_ok=True)
    serializable = [{"page_content": c.page_content, "metadata": c.metadata} for c in chunks]
    with open(CORPUS_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def run_ingestion_pipeline(category: str = "general", reset: bool = False) -> int:
    """Orquesta todo el flujo y devuelve la cantidad de chunks procesados."""
    require_env()

    raw_documents = load_documents(DATA_DIR)
    if not raw_documents:
        print(f"[WARN] No se encontraron documentos en {DATA_DIR}")
        return 0

    chunks = chunk_documents(raw_documents, category=category)
    upsert_chunks(chunks, reset=reset)
    cache_corpus_locally(chunks)

    print(f"[OK] {len(chunks)} chunks de {len(raw_documents)} documento(s) subidos "
          f"al índice '{INDEX_NAME}' (namespace='{NAMESPACE}').")
    return len(chunks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta de documentos en Pinecone")
    parser.add_argument("--category", default="general", help="categoría por defecto de los chunks")
    parser.add_argument("--reset", action="store_true", help="vaciar el namespace antes de ingestar")
    args = parser.parse_args()
    run_ingestion_pipeline(category=args.category, reset=args.reset)
