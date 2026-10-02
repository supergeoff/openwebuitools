#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from langfuse import Evaluation, EvaluatorInputs, Langfuse


# Langfuse v4: filters/system.py writes one root observation "owui-chat" per
# assistant message, with the overall input and output. The deprecated trace
# read endpoints (GET /api/public/traces) are gone once Langfuse runs the
# events_only write mode, so the judge reads the Observations API v2.
ROOT_OBSERVATION_NAME = "owui-chat"
OBSERVATION_FIELDS = "core,basic,io,metadata"
PAGE_SIZE = 50

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
    evaluations = [
        Evaluation(
            name=score_name,
            value=clamp_score(payload[source_name]),
            comment=comment,
            data_type="NUMERIC",
        )
        for source_name, score_name in SCORE_FIELDS
        if source_name in payload
    ]
    if not evaluations:
        raise ValueError("Judge response contained none of the expected score fields.")
    return evaluations


def parse_io(value: Any) -> Any:
    """The Observations API v2 returns input/output as raw strings; the system
    filter writes them as JSON objects."""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return value


def map_observation(observation) -> EvaluatorInputs:
    return EvaluatorInputs(
        input=parse_io(observation.input),
        output=parse_io(observation.output),
        expected_output=None,
        metadata=getattr(observation, "metadata", None),
    )


def lookback_start(now: datetime | None = None) -> datetime | None:
    """Optional JUDGE_LOOKBACK_DAYS limits the run to recent conversations."""
    raw = os.getenv("JUDGE_LOOKBACK_DAYS", "").strip()
    if not raw:
        return None
    now = now or datetime.now(timezone.utc)
    return now - timedelta(days=float(raw))


def iter_root_observations(
    langfuse: Langfuse, from_start_time: datetime | None = None, page_size: int = PAGE_SIZE
):
    cursor = None
    while True:
        response = langfuse.api.observations.get_many(
            name=ROOT_OBSERVATION_NAME,
            is_root_observation=True,
            fields=OBSERVATION_FIELDS,
            from_start_time=from_start_time,
            limit=page_size,
            cursor=cursor,
        )
        yield from response.data
        cursor = getattr(response.meta, "cursor", None)
        if not cursor:
            return


def judge_score_id(name: str, observation_id: str) -> str:
    # Deterministic id: a new run updates the previous judge score of the
    # observation instead of adding a duplicate that would skew averages.
    return f"judge:{name}:{observation_id}"


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


def compile_judge_prompt(langfuse: Langfuse, input: Any, output: Any, metadata: Any) -> str:
    prompt = langfuse.get_prompt(
        "evaluator_owui_judge",
        label=require_env("LANGFUSE_PROMPT_LABEL"),
        cache_ttl_seconds=0,
    )
    return prompt.compile(
        input=json.dumps(input, ensure_ascii=True),
        output=json.dumps(output, ensure_ascii=True),
        metadata=json.dumps(metadata or {}, ensure_ascii=True),
    )


def build_llm_evaluator(langfuse: Langfuse, openai_client, model: str):
    def evaluate(*, input, output, expected_output=None, metadata=None, **kwargs):
        judge_prompt = compile_judge_prompt(langfuse, input, output, metadata)
        response = openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": judge_prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return parse_judge_json(content)

    return evaluate


def run_judge(langfuse: Langfuse, evaluator, observations) -> dict:
    summary = {"items": 0, "scores": 0, "failed": 0}
    for observation in observations:
        summary["items"] += 1
        inputs = map_observation(observation)
        try:
            evaluations = evaluator(
                input=inputs.input,
                output=inputs.output,
                expected_output=None,
                metadata=inputs.metadata,
            )
        except Exception as exc:
            summary["failed"] += 1
            print(
                f"Evaluator failed on observation {observation.id} "
                f"(trace {observation.trace_id}): {exc}"
            )
            continue
        for evaluation in evaluations:
            langfuse.create_score(
                score_id=judge_score_id(evaluation.name, observation.id),
                name=evaluation.name,
                value=evaluation.value,
                trace_id=observation.trace_id,
                observation_id=observation.id,
                data_type=evaluation.data_type,
                comment=evaluation.comment,
            )
            summary["scores"] += 1
    langfuse.flush()
    return summary


def main() -> None:
    langfuse = build_langfuse_client()
    openai_client = build_openai_client()
    evaluator = build_llm_evaluator(
        langfuse,
        openai_client,
        model=require_env("JUDGE_MODEL"),
    )
    summary = run_judge(
        langfuse, evaluator, iter_root_observations(langfuse, lookback_start())
    )
    print(
        f"Judge run: {summary['items']} observations, "
        f"{summary['scores']} scores, {summary['failed']} failures."
    )
    if summary["items"] == 0:
        print(f"Warning: no '{ROOT_OBSERVATION_NAME}' root observation found.")
    if summary["failed"]:
        print("Error: the judge did not complete cleanly.")
        sys.exit(1)


if __name__ == "__main__":
    main()
