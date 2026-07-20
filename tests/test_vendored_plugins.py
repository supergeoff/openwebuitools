"""Content contracts for plugins vendored from Classic298/open-webui-plugins.

These lock in the local modifications applied on top of upstream. When
re-vendoring a newer upstream version, re-apply the changes until this
suite passes again:

- inline-visualizer-v2: skill renamed `visualize` -> `inline_visualizer`,
  and every `view_skill("visualize")` reference in the tool updated to match.
- vision-bridge: filter valve `skip_if_vision_capable` defaults to True,
  because deploy-filters.py installs every filter with `is_global: True`.
"""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

VISUALIZER_TOOL = ROOT / "tools" / "inline_visualizer.py"
VISUALIZER_SKILL = ROOT / "skills" / "inline-visualizer" / "SKILL.md"
VISION_TOOL = ROOT / "tools" / "vision_bridge.py"
VISION_FILTER = ROOT / "filters" / "vision_bridge.py"

UPSTREAM = "https://github.com/Classic298/open-webui-plugins"


class InlineVisualizerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool_text = VISUALIZER_TOOL.read_text(encoding="utf-8")
        cls.skill_text = VISUALIZER_SKILL.read_text(encoding="utf-8")

    def test_skill_frontmatter_uses_explicit_name(self):
        self.assertIn("name: inline_visualizer", self.skill_text)
        self.assertNotIn("name: visualize\n", self.skill_text)

    def test_tool_references_renamed_skill(self):
        self.assertIn('view_skill("inline_visualizer")', self.tool_text)
        self.assertNotIn('view_skill("visualize")', self.tool_text)

    def test_tool_exposes_visualize_function(self):
        # The LLM-facing function name is upstream's `visualize`; only the
        # skill id was renamed.
        self.assertIn("async def visualize(", self.tool_text)

    def test_provenance_recorded(self):
        self.assertIn(UPSTREAM, self.tool_text)
        self.assertIn(UPSTREAM, self.skill_text)

    def test_skill_dir_has_no_extra_assets(self):
        # deploy-skills.py flattens every file in the skill dir into the
        # payload; the upstream README must not be vendored next to SKILL.md.
        entries = [p.name for p in VISUALIZER_SKILL.parent.iterdir()]
        self.assertEqual(entries, ["SKILL.md"])


class VisionBridgeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool_text = VISION_TOOL.read_text(encoding="utf-8")
        cls.filter_text = VISION_FILTER.read_text(encoding="utf-8")

    def test_tool_exposes_analyze_image(self):
        self.assertIn("async def analyze_image(", self.tool_text)

    def test_filter_and_tool_share_marker_contract(self):
        # The filter injects the marker the tool's docstring teaches the
        # model to look for.
        self.assertIn("[Image attached — file_id:", self.filter_text)
        self.assertIn('"[Image attached — file_id: ...]"', self.tool_text)

    def test_filter_skips_vision_models_by_default(self):
        # Local change: deploy-filters.py installs filters globally, so the
        # filter must no-op on vision-capable models out of the box.
        valve = self.filter_text.split("skip_if_vision_capable: bool = Field(", 1)[1]
        self.assertIn("default=True", valve.split("description=", 1)[0])

    def test_provenance_recorded(self):
        self.assertIn(UPSTREAM, self.tool_text)
        self.assertIn(UPSTREAM, self.filter_text)


if __name__ == "__main__":
    unittest.main()
