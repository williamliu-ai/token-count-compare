import unittest

from compare_tokens import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_CLAUDE_OPUS_46_MODEL,
    DEFAULT_OPENAI_MODEL,
    UsageResult,
    build_comparisons,
    model_specs_from_env,
)


class ModelConfigurationTests(unittest.TestCase):
    def test_default_model_specs_include_opus_4_6_as_third_model(self) -> None:
        specs = model_specs_from_env({})

        self.assertEqual(
            [(spec.key, spec.provider, spec.model) for spec in specs],
            [
                ("claude", "anthropic", DEFAULT_CLAUDE_MODEL),
                ("claude_opus_4_6", "anthropic", DEFAULT_CLAUDE_OPUS_46_MODEL),
                ("openai", "openai", DEFAULT_OPENAI_MODEL),
            ],
        )

    def test_model_specs_allow_overriding_opus_4_6_model(self) -> None:
        specs = model_specs_from_env({"CLAUDE_OPUS_46_MODEL": "claude-opus-4-6[1m]"})

        self.assertEqual(specs[1].key, "claude_opus_4_6")
        self.assertEqual(specs[1].model, "claude-opus-4-6[1m]")


class ComparisonTests(unittest.TestCase):
    def test_build_comparisons_includes_each_cross_model_pair(self) -> None:
        results = {
            "claude": UsageResult("claude-opus-4-7", 150, 1, 151, "."),
            "claude_opus_4_6": UsageResult("claude-opus-4-6", 120, 1, 121, "."),
            "openai": UsageResult("gpt-5.5", 100, 1, 101, "."),
        }

        comparisons = build_comparisons(results)

        self.assertEqual(comparisons["openai_minus_claude"]["input_tokens_delta"], -50)
        self.assertEqual(comparisons["openai_minus_claude_opus_4_6"]["input_tokens_delta"], -20)
        self.assertEqual(comparisons["claude_minus_claude_opus_4_6"]["input_tokens_delta"], 30)


if __name__ == "__main__":
    unittest.main()
