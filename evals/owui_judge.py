#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any

from langfuse import Evaluation, EvaluatorInputs, Langfuse


SCORE_FIELDS = [
    ("instruction_following", "judge_instruction_following"),
    ("tool_use", "judge_tool_use"),
    ("task_management", "judge_task_management"),
    ("complex_run_orchestration", "judge_complex_run_orchestration"),
    ("memory_policy", "judge_memory_policy"),
    ("research_policy", "judge_research_policy"),
    ("overall_quality", "judge_overall_quality"),
]


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is required.")
        sys.exit(1)
    return value


def clamp_score(value: Any) -> float:
    score = float(value)
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def extract_json_object(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Judge response did not contain a JSON object.")
    return json.loads(raw[start : end + 1])


def parse_judge_json(text: str) -> list[Evaluation]:
    payload = extract_json_object(text)
    comment = str(payload.get("comment", "") or "")[:240]
    return [
        Evaluation(
            name=score_name,
            value=clamp_score(payload[source_name]),
            comment=comment,
            data_type="NUMERIC",
        )
        for source_name, score_name in SCORE_FIELDS
    ]


def map_trace(*, item, **kwargs) -> EvaluatorInputs:
    return EvaluatorInputs(
        input=item.input,
        output=item.output,
        expected_output=None,
        metadata=getattr(item, "metadata", None),
    )


def build_langfuse_client() -> Langfuse:
    return Langfuse(
        public_key=require_env("LANGFUSE_PUBLIC_KEY"),
        secret_key=require_env("LANGFUSE_SECRET_KEY"),
        host=require_env("LANGFUSE_HOST").rstrip("/"),
    )


def build_openai_client():
    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package is required. Install it with: pip install openai")
        sys.exit(1)

    return OpenAI(
        api_key=require_env("JUDGE_OPENAI_API_KEY"),
        base_url=require_env("JUDGE_OPENAI_BASE_URL").rstrip("/"),
    )


def compile_judge_prompt(langfuse: Langfuse, evaluator_inputs: EvaluatorInputs) -> str:
    prompt = langfuse.get_prompt(
        "evaluator_owui_judge",
        label=require_env("LANGFUSE_PROMPT_LABEL"),
        cache_ttl_seconds=0,
    )
    return prompt.compile(
        input=json.dumps(evaluator_inputs.input, ensure_ascii=True),
        output=json.dumps(evaluator_inputs.output, ensure_ascii=True),
        metadata=json.dumps(evaluator_inputs.metadata or {}, ensure_ascii=True),
    )


def build_llm_evaluator(langfuse: Langfuse, openai_client, model: str):
    def evaluate(*, evaluator_inputs, **kwargs):
        judge_prompt = compile_judge_prompt(langfuse, evaluator_inputs)
        response = openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": judge_prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return parse_judge_json(content)

    return evaluate


def run_batch(langfuse: Langfuse, evaluator) -> Any:
    return langfuse.evaluate_batch(
        mapper=map_trace,
        evaluators={"owui_judge": evaluator},
        traces=True,
        filter={"tags": ["owui", "global-prompt"]},
    )


def main() -> None:
    langfuse = build_langfuse_client()
    openai_client = build_openai_client()
    evaluator = build_llm_evaluator(
        langfuse,
        openai_client,
        model=require_env("JUDGE_MODEL"),
    )
    result = run_batch(langfuse, evaluator)
    print(result)


if __name__ == "__main__":
    main()
