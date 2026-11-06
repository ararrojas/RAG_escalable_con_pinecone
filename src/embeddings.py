"""
Fábrica de embeddings (Google Gemini).

gemini-embedding-001 produce 3072 dimensiones por defecto, pero admite
`output_dimensionality` (Matryoshka). Lo fijamos en 1536 para que coincida con
el índice de Pinecone (EMBEDDING_DIMENSION) y con lo pedido en la consigna.
"""

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from config import EMBEDDING_MODEL, EMBEDDING_DIMENSION, GOOGLE_API_KEY


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
        output_dimensionality=EMBEDDING_DIMENSION,
    )
