import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import verify_token_counts


def fake_baseline(tokens: int) -> dict[str, object]:
    return {
        "kind": "provider_count_tokens",
        "tokenizer_or_api": "test",
        "tokens": tokens,
        "exactness": "test",
        "error": None,
    }


class VerifyThirdModelTests(unittest.TestCase):
    def test_counts_only_result_includes_opus_4_6(self) -> None:
        def fake_provider_counts(model_specs, text, anthropic_api_key, openai_api_key):
            return {
                spec.key: fake_baseline(
                    {
                        "claude": 150,
                        "claude_opus_4_6": 120,
                        "openai": 100,
                    }[spec.key]
                )
                for spec in model_specs
            } | {
                "openai_tiktoken_secondary": fake_baseline(94),
                "openai_provider_vs_tiktoken": {
                    "status": "fail",
                    "delta": 6,
                    "within_tolerance": False,
                },
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = root / "fixtures"
            fixtures.mkdir()
            (fixtures / "01.txt").write_text("hello world", encoding="utf-8")

            with (
                patch.object(verify_token_counts, "load_project_env", return_value={}),
                patch.object(verify_token_counts, "provider_counts_for_text", fake_provider_counts),
            ):
                result = verify_token_counts.verify(
                    fixtures,
                    None,
                    root / "verification.json",
                    tolerance=0,
                    counts_only=True,
                )

        self.assertEqual(result["models"]["claude_opus_4_6"], "claude-opus-4-6")
        counts = result["cases"][0]["controlled_text"]["counts"]
        self.assertEqual(counts["claude"]["tokens"], 150)
        self.assertEqual(counts["claude_opus_4_6"]["tokens"], 120)
        self.assertEqual(counts["openai"]["tokens"], 100)


if __name__ == "__main__":
    unittest.main()
