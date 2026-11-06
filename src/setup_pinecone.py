"""
Setup de Pinecone.

Verifica si el índice Serverless existe y lo crea si hace falta.
Si ya existe, valida que su dimensión coincida con la del modelo de
embeddings (error típico: índice de 512/768 vs. vectores de 1536).

Uso:  python src/setup_pinecone.py
"""

import time
from typing import Optional

from pinecone import Pinecone, ServerlessSpec

from config import (
    PINECONE_API_KEY,
    INDEX_NAME,
    PINECONE_CLOUD,
    PINECONE_REGION,
    EMBEDDING_DIMENSION,
    require_env,
)


def ensure_index_exists(pc: Optional[Pinecone] = None) -> None:
    """Crea el índice Serverless solo si no existe; si existe, valida la dimensión."""
    pc = pc or Pinecone(api_key=PINECONE_API_KEY)

    if INDEX_NAME not in pc.list_indexes().names():
        print(f"[SETUP] Creando índice Serverless '{INDEX_NAME}' "
              f"(dim={EMBEDDING_DIMENSION}, cosine, {PINECONE_CLOUD}/{PINECONE_REGION})...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )
        while not pc.describe_index(INDEX_NAME).status["ready"]:
            time.sleep(1)
        print("[SETUP] Índice listo.")
        return

    existing_dim = pc.describe_index(INDEX_NAME).dimension
    if existing_dim != EMBEDDING_DIMENSION:
        raise ValueError(
            f"El índice '{INDEX_NAME}' existe con dimensión {existing_dim}, pero el modelo "
            f"de embeddings genera {EMBEDDING_DIMENSION}. Borrá el índice o usá otro INDEX_NAME."
        )
    print(f"[SETUP] El índice '{INDEX_NAME}' ya existe (dim={existing_dim}). Nada que crear.")


if __name__ == "__main__":
    require_env()
    ensure_index_exists()
