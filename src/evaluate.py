"""
Script de Evaluación del retriever.

Usa un Golden Set (eval/golden_set.json): preguntas junto con el documento
donde SABEMOS que está la respuesta. Evalúa SOLO la recuperación, no la
calidad de un texto generado.

Métricas (por pregunta, luego promediadas):
- Precision@k: de los k chunks recuperados, qué fracción pertenece al
  documento esperado. Mide el "ruido".
- Recall@k: hay un único documento relevante por pregunta, así que vale 1.0
  si ese documento aparece en el top-k y 0.0 si no (equivale a hit rate).
- MRR (extra): 1 / posición del primer chunk correcto.

Ojo: Precision@k está acotada por la cantidad de chunks que tiene el documento
esperado. Si un documento tiene 3 chunks, la precisión máxima posible con k=5
es 3/5 = 0.6.

Uso:  python src/evaluate.py
"""

import json
from typing import Dict, List

from config import GOLDEN_SET_PATH, TOP_K, require_env
from rag_system import RAGSystem


def load_golden_set(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_single_query(retrieved_doc_ids: List[str], expected_doc_id: str, k: int) -> Dict[str, float]:
    """Precision@k, Recall@k y reciprocal rank para UNA pregunta."""
    top_k_ids = retrieved_doc_ids[:k]
    relevant_hits = sum(1 for doc_id in top_k_ids if doc_id == expected_doc_id)

    precision_at_k = relevant_hits / k if k > 0 else 0.0
    recall_at_k = 1.0 if expected_doc_id in top_k_ids else 0.0
    reciprocal_rank = 0.0
    for position, doc_id in enumerate(top_k_ids, start=1):
        if doc_id == expected_doc_id:
            reciprocal_rank = 1.0 / position
            break

    return {"precision_at_k": precision_at_k, "recall_at_k": recall_at_k, "rr": reciprocal_rank}


def run_evaluation(k: int = TOP_K) -> Dict[str, float]:
    require_env()
    golden_set = load_golden_set(GOLDEN_SET_PATH)
    rag = RAGSystem(k=k)

    precisions, recalls, rrs = [], [], []
    print(f"Evaluando {len(golden_set)} preguntas del Golden Set (k={k})\n")

    for item in golden_set:
        pregunta = item["pregunta"]
        expected_doc_id = item["documento_id_esperado"]

        resultados = rag.query(pregunta)
        retrieved_doc_ids = [doc.metadata.get("doc_id") for doc in resultados]
        m = evaluate_single_query(retrieved_doc_ids, expected_doc_id, k)

        precisions.append(m["precision_at_k"])
        recalls.append(m["recall_at_k"])
        rrs.append(m["rr"])

        icono = "✅" if m["recall_at_k"] == 1.0 else "❌"
        print(f"{icono} '{pregunta}'\n   esperado: {expected_doc_id}\n   recuperado: {retrieved_doc_ids}\n"
              f"   precision@{k}={m['precision_at_k']:.2f}  recall@{k}={m['recall_at_k']:.2f}  rr={m['rr']:.2f}\n")

    n = len(golden_set) or 1
    summary = {
        "precision_at_k": sum(precisions) / n,
        "recall_at_k": sum(recalls) / n,
        "mrr": sum(rrs) / n,
    }

    print("--- Resultado agregado ---")
    print(f"Precision@{k} promedio: {summary['precision_at_k']:.3f}")
    print(f"Recall@{k} promedio:    {summary['recall_at_k']:.3f}")
    print(f"MRR:                   {summary['mrr']:.3f}")
    return summary


if __name__ == "__main__":
    run_evaluation()
