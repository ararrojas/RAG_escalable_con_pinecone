"""
Configuración central del sistema RAG.

Centralizar estos valores evita "números mágicos" repetidos en cada script
y asegura que, por ejemplo, la dimensión del embedding usada en la ingesta
sea EXACTAMENTE la misma que la usada en la recuperación (el error más común:
mismatch de dimensiones entre el índice y los vectores que se le envían).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Raíz del repo (carpeta que contiene src/, data/, eval/, .env)
BASE_DIR = Path(__file__).resolve().parent.parent

# Lee BASE_DIR/.env sin pisar variables ya definidas en el entorno
load_dotenv(BASE_DIR / ".env")

# --- Claves y nombres (vienen del .env) ---
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # clave de Gemini (Google AI Studio)
INDEX_NAME = os.getenv("INDEX_NAME", "rag-escalable")

# --- Pinecone Serverless ---
PINECONE_CLOUD = "aws"
PINECONE_REGION = "us-east-1"

# Namespace: aísla lógicamente los datos dentro del mismo índice (distintos
# proyectos, clientes o versiones de la base) sin crear índices nuevos.
NAMESPACE = os.getenv("PINECONE_NAMESPACE", "docs-v1")

# --- Embeddings ---
# gemini-embedding-001 se configura para devolver 1536 dimensiones
# (ver src/embeddings.py). Esta constante DEBE coincidir con la del índice.
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSION = 1536

# --- Chunking (en TOKENS, no caracteres) ---
# ~500-800 tokens: ni tan chico que pierda contexto, ni tan grande que
# diluya la precisión del embedding.
CHUNK_SIZE_TOKENS = 650
CHUNK_OVERLAP_TOKENS = 80

# --- Rutas ---
# Los documentos fuente viven SOLOS en data/raw. Los archivos generados
# (cache) y el golden set van en carpetas aparte para que la ingesta
# nunca intente leerlos como si fueran documentos.
DATA_DIR = str(BASE_DIR / "data" / "raw")
CORPUS_CACHE_PATH = str(BASE_DIR / "artifacts" / "corpus_cache.json")
GOLDEN_SET_PATH = str(BASE_DIR / "eval" / "golden_set.json")

# Categoría por documento (clave = nombre de archivo sin extensión). Permite
# filtrar por categoría en Pinecone y en BM25. Lo no listado usa "general".
CATEGORY_BY_DOC = {
    "fastapi_dependencies": "web",
    "pytest_fixtures": "testing",
    "pandas_merge_groupby": "datos",
    "asyncio_tasks": "concurrencia",
    "pydantic_validation": "validacion",
}

# --- Recuperación ---
TOP_K = 5                      # documentos finales que devuelve RAGSystem
CANDIDATES_PER_RETRIEVER = 10  # candidatos que trae cada retriever antes de fusionar

# Pesos del Ensemble: cuánto pesa BM25 (léxico) vs. vectorial (semántico).
BM25_WEIGHT = 0.4
VECTOR_WEIGHT = 0.6


def require_env() -> None:
    """Falla temprano y con mensaje claro si faltan claves o siguen los placeholders."""
    problems = []
    for name in ("PINECONE_API_KEY", "GOOGLE_API_KEY"):
        value = os.getenv(name)
        if not value:
            problems.append(f"- {name} no está definida")
        elif value.strip().lower().startswith("xxxx"):
            problems.append(f"- {name} todavía tiene el valor de ejemplo (xxxx)")
    if problems:
        raise RuntimeError(
            "Falta configurar el archivo .env:\n" + "\n".join(problems)
            + f"\nEditá {BASE_DIR / '.env'} con tus claves reales."
        )
