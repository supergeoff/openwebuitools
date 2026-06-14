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

    def test_mapper_keeps_trace_input_output_and_metadata(self):
        module = load_eval_module()
        trace = types.SimpleNamespace(
            input={"last_user_message": "Question"},
            output={"assistant_message": "Answer"},
            metadata={"prompt_label": "production"},
        )

        mapped = module.map_trace(item=trace)

        self.assertEqual(mapped.input, trace.input)
        self.assertEqual(mapped.output, trace.output)
        self.assertIsNone(mapped.expected_output)
        self.assertEqual(mapped.metadata, trace.metadata)

    def test_batch_eval_filters_system_traces(self):
        module = load_eval_module()
        calls = []

        class Langfuse:
            def evaluate_batch(self, **kwargs):
                calls.append(kwargs)
                return {"ok": True}

        result = module.run_batch(Langfuse(), evaluator=lambda **kwargs: [])

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls[0]["filter"], {"tags": ["owui", "system"]})

    def test_manual_eval_workflow_is_present(self):
        workflow = ROOT / ".github" / "workflows" / "run-langfuse-judge.yml"
        source = workflow.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch", source)
        self.assertIn("LANGFUSE_HOST", source)
        self.assertIn("JUDGE_MODEL", source)
        self.assertIn("python evals/owui_judge.py", source)


if __name__ == "__main__":
    unittest.main()
