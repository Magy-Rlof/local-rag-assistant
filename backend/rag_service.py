import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from main import (  # noqa: E402
    CAREER_ANALYSIS_CANDIDATE_K,
    DEFAULT_TOP_K,
    ask_model_result,
    build_rag_prompt,
    create_embedding,
    get_api_key,
    is_career_analysis_question,
    search_qdrant,
    select_sections_for_question,
)


def ask_with_rag(question: str) -> dict:
    api_key = get_api_key()
    start_time = time.perf_counter()
    query_vector = create_embedding(api_key, question)
    retrieval_seconds = time.perf_counter() - start_time

    candidate_k = CAREER_ANALYSIS_CANDIDATE_K if is_career_analysis_question(question) else DEFAULT_TOP_K
    candidate_sections = search_qdrant(query_vector, top_k=candidate_k)
    retrieved_sections = select_sections_for_question(question, candidate_sections)
    if not retrieved_sections:
        raise RuntimeError("未检索到相关片段，请换一种问法。")

    prompt = build_rag_prompt(question, retrieved_sections, include_citations=False)
    generation_start = time.perf_counter()
    model_result = ask_model_result(api_key, prompt)
    generation_seconds = time.perf_counter() - generation_start

    return {
        "answer": model_result["content"],
        "truncated": model_result["truncated"],
        "sources": [
            {
                "source_file": section["source_file"],
                "title": section["title"],
                "score": section.get("score"),
            }
            for section in retrieved_sections
        ],
        "retrieval_seconds": retrieval_seconds,
        "generation_seconds": generation_seconds,
    }
