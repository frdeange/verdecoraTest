"""Integration test: AI Foundry GPT-5 / GPT-5-mini inference (Issue #154).

Requires:
  - AZURE_AI_ENDPOINT env var (or uses default dev endpoint)
  - Azure CLI login (DefaultAzureCredential → get_bearer_token_provider)

Uses the OpenAI Python SDK with AzureOpenAI client, which is the correct
approach for Azure AI Services (kind: AIServices) resources.
"""

import json
import os
import sys

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

ENDPOINT = os.getenv(
    "AZURE_AI_ENDPOINT",
    "https://verdecora-ais-dev.cognitiveservices.azure.com/",
)
API_VERSION = "2025-01-01-preview"
MODELS = ["gpt-5", "gpt-5-mini"]


def get_client() -> AzureOpenAI:
    """Create an AzureOpenAI client with Entra ID auth."""
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version=API_VERSION,
    )


def test_model(model: str) -> dict:
    """Send a simple prompt and validate the response."""
    print(f"\n{'='*60}")
    print(f"Testing model: {model}")
    print(f"Endpoint: {ENDPOINT}")
    print(f"{'='*60}")

    client = get_client()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant for Verdecora garden centers."},
                {"role": "user", "content": "Responde en una frase: ¿Qué es un albarán de entrega?"},
            ],
            # GPT-5 uses ~128 internal reasoning tokens, so budget ≥500
            max_completion_tokens=1000,
        )
        content = response.choices[0].message.content
        usage = response.usage

        print(f"✅ Response: {content[:200]}")
        print(f"   Tokens — prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens}")
        return {"model": model, "status": "OK", "response": content, "tokens": usage.total_tokens}

    except Exception as e:
        print(f"❌ Error: {e}")
        return {"model": model, "status": "ERROR", "error": str(e)}


def test_structured_output(model: str) -> dict:
    """Test structured JSON output (needed for agents)."""
    print(f"\n{'='*60}")
    print(f"Testing structured output: {model}")
    print(f"{'='*60}")

    client = get_client()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You extract structured data from delivery notes. Always respond with valid JSON."},
                {"role": "user", "content": 'Extract the supplier name and total from this text: "Albarán de VIVEROS FERNÁNDEZ S.L. Total: 1.234,56 €". Return JSON with keys: supplier, total_eur'},
            ],
            # GPT-5 uses ~128 internal reasoning tokens, so budget ≥500
            max_completion_tokens=1000,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        parsed = json.loads(content)
        print(f"✅ Structured output: {json.dumps(parsed, ensure_ascii=False, indent=2)}")
        assert "supplier" in parsed, "Missing 'supplier' key"
        return {"model": model, "status": "OK", "parsed": parsed}

    except json.JSONDecodeError as e:
        print(f"⚠️  Invalid JSON: {content}")
        return {"model": model, "status": "JSON_ERROR", "raw": content, "error": str(e)}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"model": model, "status": "ERROR", "error": str(e)}


def main():
    print("🚀 AI Foundry Integration Test")
    print(f"Endpoint: {ENDPOINT}")
    results = []

    for model in MODELS:
        results.append(test_model(model))
        results.append(test_structured_output(model))

    print(f"\n{'='*60}")
    print("📊 Summary")
    print(f"{'='*60}")
    errors = [r for r in results if r["status"] != "OK"]
    for r in results:
        icon = "✅" if r["status"] == "OK" else "❌"
        print(f"  {icon} {r['model']}: {r['status']}")

    if errors:
        print(f"\n❌ {len(errors)} test(s) failed")
        sys.exit(1)
    else:
        print(f"\n✅ All {len(results)} tests passed")


if __name__ == "__main__":
    main()
