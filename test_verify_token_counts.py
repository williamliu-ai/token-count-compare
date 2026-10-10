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
            "gpt-5.6-sol": 101,
            "gpt-5.6-terra": 102,
            "gpt-5.6-luna": 103,
            "gpt-6-astra": 104,
            "gpt-6-sol": 105,
            "gpt-6-luna": 106,
            "claude-opus-5-5": 190,
            "claude-opus-5": 185,
            "claude-fable-5-1": 180,
            "claude-fable-5": 170,
            "claude-opus-4-8": 165,
            "claude-opus-4-7": 150,
            "claude-opus-4-6": 120,
            "muse-spark-1.3": 130,
        }

        def fake_provider_counts(specs, text, anthropic_api_key, openai_api_key, meta_api_key=None):
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


class MetaCountTests(unittest.TestCase):
    def test_missing_key_is_unavailable(self):
        result = verify_token_counts.meta_input_tokens_count("muse-spark-1.3", "hello", None)
        self.assertIsNone(result.tokens)
        self.assertIn("MUSE_API_KEY missing", result.error)

    def test_meta_count_uses_meta_endpoint_and_raw_text(self):
        with patch("openai.OpenAI") as factory:
            factory.return_value.post.return_value = {"input_tokens": 42}
            result = verify_token_counts.meta_input_tokens_count("muse-spark-1.3", "hello", "test-key")
        factory.assert_called_once_with(api_key="test-key", base_url="https://api.meta.ai/v1")
        factory.return_value.post.assert_called_once_with(
            "/responses/input_tokens", body={"model": "muse-spark-1.3", "input": "hello"}, cast_to=object)
        self.assertEqual(result.tokens, 42)
        self.assertIsNone(result.error)

    def test_meta_count_parses_real_sdk_json_response(self):
        import httpx
        from openai import OpenAI

        client = OpenAI(
            api_key="test-key", base_url="https://api.meta.ai/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 166}))),
        )
        with client, patch("openai.OpenAI", return_value=client):
            result = verify_token_counts.meta_input_tokens_count("muse-spark-1.3", "hello world", "test-key")
        self.assertEqual(result.tokens, 166)
        self.assertIsNone(result.error)

    def test_invalid_meta_count_is_unavailable(self):
        with patch("openai.OpenAI") as factory:
            factory.return_value.post.return_value = {"input_tokens": -1}
            result = verify_token_counts.meta_input_tokens_count("muse-spark-1.3", "hello", "test-key")
        self.assertIsNone(result.tokens)
        self.assertIn("invalid input_tokens", result.error)

    def test_counts_only_ignores_historical_report_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = root / "fixtures"
            fixtures.mkdir()
            report = root / "old.json"
            report.write_text('{"models":["gpt-5.5"],"baseline":"gpt-5.5"}')
            with patch.object(verify_token_counts, "load_project_env", return_value={}):
                result = verify_token_counts.verify(fixtures, report, root / "out.json", 0, True)
        self.assertIn("muse-spark-1.3", result["models"])
        self.assertIsNone(result["report_compared"])


if __name__ == "__main__":
    unittest.main()
