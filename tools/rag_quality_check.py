import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 140
MAX_HISTORY_MESSAGES = 8


@dataclass
class TestTurn:
    case_id: str
    turn_id: int
    question: str
    response: dict[str, Any] | None
    status_code: int | None
    elapsed_seconds: float
    error: str


SINGLE_TURN_CASES = [
    (
        "Q1",
        "根据项目资料，local-rag-assistant 解决了什么问题？",
    ),
    (
        "Q2",
        "根据项目资料，local-rag-assistant 的 RAG 流程是什么？",
    ),
    (
        "Q3",
        "根据项目资料，local-rag-assistant 适合写进 AI 应用开发简历吗？",
    ),
    (
        "Q4",
        "根据项目资料，如果面试官问 local-rag-assistant 的项目局限性，应该怎么回答？",
    ),
    (
        "Q5",
        "根据我的简历、项目资料和 AI 应用开发岗位资料，我的项目经历和 AI 应用开发岗位有哪些匹配点？",
    ),
    (
        "Q6",
        "根据我的简历和岗位资料，我更适合哪些岗位？请按优先推荐、可以尝试、暂不优先分类。",
    ),
    (
        "Q7",
        "针对 AI 应用开发岗位，根据我的当前简历和项目资料，这份简历应该怎么修改？请按优先修改项、修改原因、示例表达、对应岗位要求回答。",
    ),
    (
        "Q8",
        "LangChain 和 LlamaIndex 在 RAG 中有什么区别？请先基于资料回答，再补充模型通用知识。",
    ),
    (
        "Q9",
        "Dify 和手写 RAG 的区别是什么？请结合 local-rag-assistant 的项目资料说明。",
    ),
    (
        "Q10",
        "如果模型回答资料不足，我应该如何补充知识库？请结合 local-rag-assistant 的资料结构说明。",
    ),
]


MULTI_TURN_CASES = {
    "M1_project_interview_deep_dive": [
        "根据项目资料，local-rag-assistant 解决了什么问题？",
        "它的 RAG 流程是什么？",
        "这个项目适合写进 AI 应用开发简历吗？",
        "如果面试官追问项目局限性，我应该怎么回答？",
        "请把前面内容整合成一段 2 分钟面试口述，不要夸大项目能力。",
    ],
    "M2_resume_revision_pressure": [
        "根据我的简历和 AI 应用开发岗位资料，我的项目经历有哪些匹配点？",
        "针对这些匹配点，这份简历应该优先修改哪些地方？",
        "请给出每个修改点的示例表达。",
        "请把 Local RAG Assistant 项目经历改写成一段适合简历的项目描述。",
        "请再补充一段面试时解释这个项目的回答，要求包含局限性和后续改进方向。",
    ],
    "M3_technical_explanation_followup": [
        "LangChain 和 LlamaIndex 在 RAG 中有什么区别？请先基于资料回答，再补充模型通用知识。",
        "Dify 和手写 RAG 的区别是什么？请结合 local-rag-assistant 的项目资料说明。",
        "如果我要继续求职导向学习，什么时候该用 Dify，什么时候该手写 RAG？",
        "请总结成面试中可以说的 3 个要点。",
    ],
    "M4_knowledge_base_maintenance": [
        "如果模型回答资料不足，我应该如何补充知识库？请结合 local-rag-assistant 的资料结构说明。",
        "补充项目资料时，事实卡片应该包含哪些部分？",
        "补充或修改资料后，我应该如何更新索引？",
        "请给出一份适合 local-rag-assistant 项目资料的事实卡片模板。",
    ],
}


def ask(base_url: str, question: str, history: list[dict[str, str]], timeout: int) -> tuple[int | None, dict[str, Any] | None, str, float]:
    start = time.perf_counter()
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/rag/ask",
            json={"question": question, "history": history[-MAX_HISTORY_MESSAGES:]},
            timeout=timeout,
        )
        elapsed = time.perf_counter() - start
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response.status_code, None, response.text[:1000], elapsed
        data = response.json()
        if response.status_code >= 400:
            return response.status_code, data, data.get("detail", json.dumps(data, ensure_ascii=False)), elapsed
        return response.status_code, data, "", elapsed
    except requests.RequestException as exc:
        elapsed = time.perf_counter() - start
        return None, None, str(exc), elapsed


def run_single_turn(base_url: str, timeout: int) -> list[TestTurn]:
    results = []
    for case_id, question in SINGLE_TURN_CASES:
        status_code, data, error, elapsed = ask(base_url, question, [], timeout)
        results.append(TestTurn(case_id, 1, question, data, status_code, elapsed, error))
    return results


def run_multi_turn(base_url: str, timeout: int) -> list[TestTurn]:
    results = []
    for case_id, questions in MULTI_TURN_CASES.items():
        history: list[dict[str, str]] = []
        for index, question in enumerate(questions, start=1):
            status_code, data, error, elapsed = ask(base_url, question, history, timeout)
            results.append(TestTurn(case_id, index, question, data, status_code, elapsed, error))
            history.append({"role": "user", "content": question})
            if data and isinstance(data.get("answer"), str):
                history.append({"role": "assistant", "content": data["answer"]})
            else:
                history.append({"role": "assistant", "content": f"[ERROR] {error}"})
    return results


def source_summary(response: dict[str, Any] | None) -> str:
    if not response:
        return ""
    sources = response.get("sources") or []
    if not sources:
        return "无"
    labels = []
    for source in sources[:5]:
        labels.append(f"{source.get('source_file', '?')} / {source.get('title', '?')}")
    if len(sources) > 5:
        labels.append(f"...共 {len(sources)} 条")
    return "; ".join(labels)


def answer_preview(response: dict[str, Any] | None, max_chars: int = 180) -> str:
    if not response:
        return ""
    answer = response.get("answer") or ""
    answer = " ".join(str(answer).split())
    if len(answer) <= max_chars:
        return answer
    return answer[:max_chars].rstrip() + "..."


def warning_summary(turn: TestTurn) -> str:
    warnings = []
    if turn.error:
        warnings.append("error")
    if turn.status_code != 200:
        warnings.append(f"status={turn.status_code}")
    if turn.response and turn.response.get("truncated"):
        warnings.append("truncated")
    if turn.response and not turn.response.get("sources") and turn.response.get("mode") == "rag":
        warnings.append("rag_no_sources")
    if turn.response and turn.elapsed_seconds >= 60:
        warnings.append("slow")
    return ", ".join(warnings) if warnings else "ok"


def render_markdown(results: list[TestTurn], scenario: str, base_url: str) -> str:
    lines = [
        "# RAG Quality Check Report",
        "",
        f"- Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Scenario: `{scenario}`",
        f"- Base URL: `{base_url}`",
        "",
        "## Summary",
        "",
    ]

    total = len(results)
    errors = sum(1 for item in results if item.error or item.status_code != 200)
    truncated = sum(1 for item in results if item.response and item.response.get("truncated"))
    slow = sum(1 for item in results if item.elapsed_seconds >= 60)
    lines.extend(
        [
            f"- Total turns: {total}",
            f"- Error turns: {errors}",
            f"- Truncated turns: {truncated}",
            f"- Slow turns (>=60s): {slow}",
            "",
            "## Turns",
            "",
            "| Case | Turn | Mode | Truncated | Answer chars | Elapsed | Generation | Retrieval | Warnings |",
            "|---|---:|---|---|---:|---:|---:|---:|---|",
        ]
    )

    for item in results:
        response = item.response or {}
        answer = response.get("answer") or ""
        lines.append(
            "| {case} | {turn} | {mode} | {truncated} | {chars} | {elapsed:.1f}s | {generation:.1f}s | {retrieval:.1f}s | {warnings} |".format(
                case=item.case_id,
                turn=item.turn_id,
                mode=response.get("mode", "-"),
                truncated=response.get("truncated", "-"),
                chars=len(answer),
                elapsed=item.elapsed_seconds,
                generation=float(response.get("generation_seconds") or 0),
                retrieval=float(response.get("retrieval_seconds") or 0),
                warnings=warning_summary(item),
            )
        )

    lines.extend(["", "## Details", ""])
    for item in results:
        response = item.response
        lines.extend(
            [
                f"### {item.case_id} Turn {item.turn_id}",
                "",
                f"Question: {item.question}",
                "",
                f"Status: {item.status_code}",
                f"Warnings: {warning_summary(item)}",
                f"Sources: {source_summary(response)}",
                "",
            ]
        )
        if item.error:
            lines.extend(["Error:", "", "```text", item.error, "```", ""])
        else:
            lines.extend(["Answer preview:", "", "```text", answer_preview(response), "```", ""])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Local RAG Assistant quality checks.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"API base URL. Default: {DEFAULT_BASE_URL}")
    parser.add_argument(
        "--scenario",
        choices=["single", "multi", "all"],
        default="all",
        help="Which test scenario to run. Default: all",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Request timeout seconds.")
    parser.add_argument("--output", help="Optional markdown report path.")
    args = parser.parse_args()

    results: list[TestTurn] = []
    if args.scenario in {"single", "all"}:
        results.extend(run_single_turn(args.base_url, args.timeout))
    if args.scenario in {"multi", "all"}:
        results.extend(run_multi_turn(args.base_url, args.timeout))

    report = render_markdown(results, args.scenario, args.base_url)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Wrote report: {output_path}")
    else:
        print(report)

    has_error = any(item.error or item.status_code != 200 for item in results)
    has_truncated = any(item.response and item.response.get("truncated") for item in results)
    return 1 if has_error or has_truncated else 0


if __name__ == "__main__":
    raise SystemExit(main())
