# Sistema RAG escalable con Pinecone (búsqueda híbrida BM25 + vectorial)

Módulo de recuperación en Python que ingesta documentos técnicos en un índice **Pinecone Serverless**, los recupera con **búsqueda híbrida** (similitud de vectores + BM25, fusionados con Reciprocal Rank Fusion) y mide la calidad con **Precision@k** y **Recall@k** sobre un *Golden Set*.

## Arquitectura

```
data/raw/*.md|pdf|json
        │  src/ingest.py  (chunks ~650 tokens, metadata + texto original)
        ├──────────────► Pinecone Serverless (namespace docs-v1)
        └──────────────► artifacts/corpus_cache.json  (corpus local para BM25)

pregunta ─► src/rag_system.py  (clase RAGSystem)
              └─ EnsembleRetriever (src/hybrid_retriever.py)
                    ├─ BM25Retriever    (léxico, peso 0.4)
                    └─ Pinecone vector  (semántico, peso 0.6)
                         └─ fusión RRF ─► top-5

src/evaluate.py + eval/golden_set.json ─► Precision@5, Recall@5, MRR
```

## Estructura del repo

```
├── .env.example            # plantilla de variables (se sube)
├── .gitignore              # excluye .env, venv, artifacts
├── requirements.txt
├── data/raw/               # documentos fuente (5 guías técnicas en Markdown)
├── eval/golden_set.json    # 5 preguntas con su documento esperado
├── artifacts/              # corpus_cache.json (se genera; no se sube)
└── src/
    ├── config.py           # constantes y carga del .env
    ├── setup_pinecone.py   # crea el índice Serverless si no existe
    ├── ingest.py           # pipeline de ingesta
    ├── hybrid_retriever.py # BM25 + vectorial + EnsembleRetriever
    ├── rag_system.py       # clase RAGSystem
    └── evaluate.py         # Precision@k / Recall@k / MRR
```

## Cómo replicar el índice (paso a paso)

**1. Clonar e instalar**
```bash
git clone git@github.com:ararrojas/RAG_escalable_con_pinecone.git
cd RAG_escalable_con_pinecone
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configurar variables de entorno**
```bash
cp .env.example .env            # Windows: copy .env.example .env
```
Editá `.env` con tus claves reales:

| Variable | Descripción |
|---|---|
| `PINECONE_API_KEY` | Clave de [Pinecone](https://app.pinecone.io) |
| `GOOGLE_API_KEY` | Clave de Gemini ([Google AI Studio](https://aistudio.google.com/apikey)); embeddings `gemini-embedding-001` fijados a 1536 dimensiones |
| `INDEX_NAME` | Nombre del índice (por defecto `rag-escalable`) |
| `PINECONE_NAMESPACE` | Opcional, por defecto `docs-v1` |

> El archivo `.env` está en `.gitignore`: **nunca lo subas**. Solo se versiona `.env.example`.

**3. Crear el índice (opcional, la ingesta lo hace sola si falta)**
```bash
python src/setup_pinecone.py
```
Crea un índice Serverless (AWS `us-east-1`, métrica coseno, **dimensión 1536**). Si el índice ya existe con otra dimensión, aborta con un error claro.

**4. Ingestar los documentos**
```bash
python src/ingest.py            # upsert idempotente
python src/ingest.py --reset    # opcional: vacía el namespace antes de ingestar
```

**5. Probar el recuperador**
```bash
python src/rag_system.py "¿Cómo uso Depends en FastAPI?"
```

**6. Evaluar**
```bash
python src/evaluate.py
```

Para usar tus propios documentos, copialos a `data/raw/` (PDF, `.md`, `.txt` o `.json` con formato `[{"text": "...", "category": "..."}]`), ajustá `eval/golden_set.json` (el `documento_id_esperado` es el nombre del archivo **sin extensión**) y volvé a correr la ingesta.

## Decisiones de diseño

- **Texto dentro de la metadata de Pinecone.** Cada vector guarda `text`, `doc_id`, `source`, `page` y `category`; al recuperar no hace falta otra base de datos.
- **Chunking por tokens.** `RecursiveCharacterTextSplitter` con `tiktoken` (`cl100k_base`): 650 tokens con 80 de solapamiento (rango recomendado 500-800).
- **IDs deterministas.** El `chunk_id` es un hash de `fuente|página|índice`: re-ingestar sobrescribe en vez de duplicar.
- **Categorías por documento.** `CATEGORY_BY_DOC` en `src/config.py` asigna una categoría a cada archivo (web, testing, datos, concurrencia, validacion); lo no listado usa `general`. Sirve para filtrar por categoría en Pinecone y BM25.
- **Namespace.** Los datos viven en `docs-v1`; las búsquedas se acotan a ese namespace.
- **BM25 local.** BM25 es un índice léxico en memoria (no vive en Pinecone), por eso la ingesta guarda `artifacts/corpus_cache.json`. El tokenizador pasa a minúsculas y quita tildes y puntuación.
- **Fusión híbrida.** `EnsembleRetriever` combina los rankings de BM25 y Pinecone con Reciprocal Rank Fusion ponderado (`score = peso / (60 + posición)`, sumado por documento). Se fusionan los rankings y no los scores porque BM25 y coseno tienen escalas distintas. Cada retriever aporta 10 candidatos y `RAGSystem` devuelve el top-5 final.

## Métricas de evaluación

- **Precision@5**: fracción de los 5 chunks recuperados que pertenece al documento esperado.
- **Recall@5**: 1 si el documento esperado aparece en el top-5, 0 si no (hay un único documento relevante por pregunta).
- **MRR** (extra): 1 / posición del primer acierto.

Notas para interpretar los números:
- Cada documento de ejemplo produce pocos chunks (~2), por eso la Precision@5 máxima posible ronda 0.4 aunque el retriever sea perfecto.
- Con un corpus de solo 5 documentos, el Recall@5 tiende a ser alto casi por construcción. Con un corpus más grande la evaluación es más exigente.

### Resultados

**Pendiente:** ejecutá `python src/evaluate.py` con tus claves reales y reemplazá `_completar_` por los valores impresos en consola (no se inventan; dependen de tu índice).

| Métrica | Valor |
|---|---|
| Precision@5 | _completar_ |
| Recall@5 | _completar_ |
| MRR | _completar_ |

## Problemas frecuentes

- **`Falta configurar el archivo .env`**: las claves todavía tienen el valor de ejemplo (`xxxx`).
- **Dimensión del índice incorrecta**: el índice existente no tiene 1536 dimensiones. Borralo en la consola de Pinecone o cambiá `INDEX_NAME`.
- **Recall bajo justo después de ingestar**: Pinecone es eventualmente consistente; esperá unos segundos y reevaluá.
- **`No existe artifacts/corpus_cache.json`**: corré primero `python src/ingest.py`.