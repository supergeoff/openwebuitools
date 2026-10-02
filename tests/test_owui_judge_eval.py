import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "evals" / "owui_judge.py"


def load_eval_module():
    if "langfuse" not in sys.modules:
        langfuse = types.ModuleType("langfuse")

        class Evaluation:
            def __init__(self, name, value, comment=None, data_type=None):
                self.name = name
                self.value = value
                self.comment = comment
                self.data_type = data_type

        class EvaluatorInputs:
            def __init__(self, input=None, output=None, expected_output=None, metadata=None):
                self.input = input
                self.output = output
                self.expected_output = expected_output
                self.metadata = metadata

        langfuse.Evaluation = Evaluation
        langfuse.EvaluatorInputs = EvaluatorInputs
        langfuse.Langfuse = object
        sys.modules["langfuse"] = langfuse

    spec = importlib.util.spec_from_file_location("owui_judge", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OwuiJudgeEvalTest(unittest.TestCase):
    def test_parse_judge_json_returns_expected_scores(self):
        module = load_eval_module()

        scores = module.parse_judge_json(
            json.dumps(
                {
                    "instruction_following": 0.8,
                    "tool_use": 0.7,
                    "task_management": 0.9,
                    "complex_run_orchestration": 0.5,
                    "memory_policy": 1,
                    "research_policy": 0.4,
                    "overall_quality": 0.6,
                    "comment": "Bonne reponse, recherche faible.",
                }
            )
        )

        self.assertEqual([score.name for score in scores], [
            "judge_instruction_following",
            "judge_tool_use",
            "judge_task_management",
            "judge_complex_run_orchestration",
            "judge_memory_policy",
            "judge_research_policy",
            "judge_overall_quality",
        ])
        self.assertEqual(
            [score.value for score in scores],
            [0.8, 0.7, 0.9, 0.5, 1.0, 0.4, 0.6],
        )
        self.assertTrue(all(score.data_type == "NUMERIC" for score in scores))
        self.assertTrue(all(score.comment == "Bonne reponse, recherche faible." for score in scores))

    def test_mapper_keeps_observation_input_output_and_metadata(self):
        module = load_eval_module()
        observation = types.SimpleNamespace(
            input='{"last_user_message": "Question"}',
            output={"assistant_message": "Answer"},
            metadata={"prompt_label": "production"},
        )

        mapped = module.map_observation(observation)

        self.assertEqual(mapped.input, {"last_user_message": "Question"})
        self.assertEqual(mapped.output, {"assistant_message": "Answer"})
        self.assertIsNone(mapped.expected_output)
        self.assertEqual(mapped.metadata, observation.metadata)

    def test_root_observations_are_read_page_by_page_from_observations_v2(self):
        module = load_eval_module()
        calls = []
        pages = {
            None: (["obs-1", "obs-2"], "cursor-2"),
            "cursor-2": (["obs-3"], None),
        }

        class Observations:
            def get_many(self, **kwargs):
                calls.append(kwargs)
                data, cursor = pages[kwargs["cursor"]]
                return types.SimpleNamespace(
                    data=data, meta=types.SimpleNamespace(cursor=cursor)
                )

        langfuse = types.SimpleNamespace(
            api=types.SimpleNamespace(observations=Observations())
        )

        observations = list(module.iter_root_observations(langfuse, page_size=2))

        self.assertEqual(observations, ["obs-1", "obs-2", "obs-3"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["name"], "owui-chat")
        self.assertTrue(calls[0]["is_root_observation"])
        self.assertEqual(calls[0]["fields"], "core,basic,io,metadata")
        self.assertNotIn("parse_io_as_json", calls[0])
        self.assertEqual(calls[1]["cursor"], "cursor-2")

    def test_run_judge_scores_trace_and_root_observation_with_stable_ids(self):
        module = load_eval_module()
        scores = []
        flushed = []

        class Langfuse:
            def create_score(self, **kwargs):
                scores.append(kwargs)

            def flush(self):
                flushed.append(True)

        observation = types.SimpleNamespace(
            id="root-1",
            trace_id="trace-1",
            input='{"last_user_message": "Question"}',
            output='{"assistant_message": "Answer"}',
            metadata={},
        )

        def evaluator(**kwargs):
            self.assertEqual(kwargs["input"], {"last_user_message": "Question"})
            return module.parse_judge_json(
                json.dumps({"overall_quality": 0.6, "comment": "ok"})
            )

        summary = module.run_judge(Langfuse(), evaluator, [observation])

        self.assertEqual(summary, {"items": 1, "scores": 1, "failed": 0})
        self.assertEqual(flushed, [True])
        self.assertEqual(scores[0]["trace_id"], "trace-1")
        self.assertEqual(scores[0]["observation_id"], "root-1")
        self.assertEqual(scores[0]["name"], "judge_overall_quality")
        self.assertEqual(scores[0]["value"], 0.6)
        self.assertEqual(scores[0]["score_id"], "judge:judge_overall_quality:root-1")

    def test_run_judge_counts_evaluator_failures(self):
        module = load_eval_module()

        class Langfuse:
            def create_score(self, **kwargs):
                raise AssertionError("no score expected")

            def flush(self):
                pass

        observation = types.SimpleNamespace(
            id="root-1", trace_id="trace-1", input={}, output={}, metadata={}
        )

        def failing_evaluator(**kwargs):
            raise RuntimeError("Invalid model name")

        summary = module.run_judge(Langfuse(), failing_evaluator, [observation])

        self.assertEqual(summary, {"items": 1, "scores": 0, "failed": 1})

    def test_lookback_is_optional(self):
        module = load_eval_module()
        from datetime import datetime, timezone
        from unittest import mock

        now = datetime(2026, 10, 2, tzinfo=timezone.utc)
        with mock.patch.dict("os.environ", {"JUDGE_LOOKBACK_DAYS": ""}):
            self.assertIsNone(module.lookback_start(now))
        with mock.patch.dict("os.environ", {"JUDGE_LOOKBACK_DAYS": "7"}):
            self.assertEqual(
                module.lookback_start(now), datetime(2026, 9, 25, tzinfo=timezone.utc)
            )

    def test_manual_eval_workflow_is_present(self):
        workflow = ROOT / ".github" / "workflows" / "run-langfuse-judge.yml"
        source = workflow.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch", source)
        self.assertIn("LANGFUSE_HOST", source)
        self.assertIn("JUDGE_MODEL", source)
        self.assertIn("python evals/owui_judge.py", source)


if __name__ == "__main__":
    unittest.main()
