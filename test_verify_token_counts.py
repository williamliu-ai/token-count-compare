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


class VerifyModelListTests(unittest.TestCase):
    def test_counts_only_result_covers_every_model_and_baseline(self) -> None:
        token_by_model = {
            "gpt-5.5": 100,
            "claude-opus-4-8": 165,
            "claude-opus-4-7": 150,
            "claude-opus-4-6": 120,
        }

        def fake_provider_counts(specs, text, anthropic_api_key, openai_api_key):
            return {spec.model: fake_baseline(token_by_model[spec.model]) for spec in specs} | {
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

        self.assertEqual(result["models"], list(token_by_model))
        self.assertEqual(result["baseline"], "gpt-5.5")
        counts = result["cases"][0]["controlled_text"]["counts"]
        for model, tokens in token_by_model.items():
            self.assertEqual(counts[model]["tokens"], tokens)


if __name__ == "__main__":
    unittest.main()
