import unittest

from compare_tokens import (
    DEFAULT_BASELINE_MODEL,
    MODELS,
    UsageResult,
    build_comparisons,
    model_specs_from_env,
    provider_for_model,
    resolve_baseline,
)


class ModelConfigurationTests(unittest.TestCase):
    def test_default_specs_cover_every_model_with_inferred_provider(self) -> None:
        specs = model_specs_from_env({})

        self.assertEqual([spec.model for spec in specs], MODELS)
        self.assertEqual(
            [(spec.provider, spec.is_baseline) for spec in specs],
            [(provider_for_model(m), m == DEFAULT_BASELINE_MODEL) for m in MODELS],
        )

    def test_exactly_one_baseline_and_it_is_gpt_5_5_by_default(self) -> None:
        specs = model_specs_from_env({})
        baselines = [spec.model for spec in specs if spec.is_baseline]

        self.assertEqual(baselines, ["gpt-5.5"])

    def test_baseline_override_via_env(self) -> None:
        specs = model_specs_from_env({"BASELINE_MODEL": "claude-opus-4-8"})
        baselines = [spec.model for spec in specs if spec.is_baseline]

        self.assertEqual(baselines, ["claude-opus-4-8"])

    def test_unknown_baseline_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_baseline({"BASELINE_MODEL": "not-a-real-model"})

    def test_provider_inference(self) -> None:
        self.assertEqual(provider_for_model("claude-opus-4-8"), "anthropic")
        self.assertEqual(provider_for_model("gpt-5.5"), "openai")
        with self.assertRaises(ValueError):
            provider_for_model("mistral-large")


class ComparisonTests(unittest.TestCase):
    def test_each_model_compared_against_baseline(self) -> None:
        results = {
            "gpt-5.5": UsageResult("gpt-5.5", 100, 1, 101, "."),
            "claude-opus-4-8": UsageResult("claude-opus-4-8", 160, 1, 161, "."),
            "claude-opus-4-7": UsageResult("claude-opus-4-7", 150, 1, 151, "."),
            "claude-opus-4-6": UsageResult("claude-opus-4-6", 120, 1, 121, "."),
        }

        comparisons = build_comparisons(results, baseline="gpt-5.5")

        # baseline itself is never a comparison entry
        self.assertNotIn("gpt-5.5", comparisons)
        self.assertEqual(set(comparisons), {"claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6"})
        # delta is model minus baseline
        self.assertEqual(comparisons["claude-opus-4-8"]["input_tokens_delta"], 60)
        self.assertEqual(comparisons["claude-opus-4-7"]["input_tokens_delta"], 50)
        self.assertEqual(comparisons["claude-opus-4-6"]["input_tokens_delta"], 20)
        self.assertEqual(comparisons["claude-opus-4-8"]["baseline"], "gpt-5.5")

    def test_comparisons_follow_a_non_default_baseline(self) -> None:
        results = {
            "gpt-5.5": UsageResult("gpt-5.5", 100, 1, 101, "."),
            "claude-opus-4-8": UsageResult("claude-opus-4-8", 160, 1, 161, "."),
        }

        comparisons = build_comparisons(results, baseline="claude-opus-4-8")

        self.assertNotIn("claude-opus-4-8", comparisons)
        # gpt-5.5 has fewer tokens than the claude baseline -> negative delta
        self.assertEqual(comparisons["gpt-5.5"]["input_tokens_delta"], -60)


if __name__ == "__main__":
    unittest.main()
