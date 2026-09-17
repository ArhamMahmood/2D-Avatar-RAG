import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Parse model lists from environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
GROQ_MODELS = [
    m.strip()
    for m in os.getenv(
        "GROQ_MODELS", "openai/gpt-oss-20b,groq/compound-mini,qwen/qwen3.8-27b"
    ).split(",")
    if m.strip()
]

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
).strip()
OPENROUTER_MODELS = [
    m.strip()
    for m in (
        os.getenv("OPENROUTER_MODELS", "")
        or os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
    ).split(",")
    if m.strip()
]

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL", "http://localhost:11434/v1"
).strip()
OLLAMA_MODELS = [
    m.strip()
    for m in os.getenv("OLLAMA_CHAT_MODELS", "qwen2.5:1.5b,llama3.2:1b").split(
        ","
    )
    if m.strip()
]

# Configure OpenAI-compatible providers
targets = []

if GROQ_API_KEY:
  targets.append((
      "Groq",
      OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL),
      GROQ_MODELS,
  ))

if OPENROUTER_API_KEY:
  targets.append((
      "OpenRouter",
      OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL),
      OPENROUTER_MODELS,
  ))

targets.append((
    "Ollama",
    OpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL),
    OLLAMA_MODELS,
))


def run_model_benchmark(question: str):
  print(f"\n{'='*80}")
  print(f"BENCHMARK QUESTION: {question}")
  print(f"{'='*80}\n")

  for provider_name, client, models in targets:
    for model in models:
      print(f"▶ Provider: {provider_name:<10} | Model: {model}")
      start_time = time.perf_counter()

      try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant. Keep responses"
                        " concise and clear."
                    ),
                },
                {"role": "user", "content": question},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        output = (response.choices[0].message.content or "").strip()

        print(f"✔ SUCCESS ({elapsed_ms:.0f} ms)")
        print(f"Response:\n{output}\n")

      except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        print(f"✖ FAILED ({elapsed_ms:.0f} ms)")
        print(f"Error: {exc}\n")

      print("-" * 80)


if __name__ == "__main__":
  test_prompt = (
      "Briefly summarize the key benefits of Retrieval-Augmented Generation"
      " (RAG) in 2-3 sentences."
  )
  run_model_benchmark(test_prompt)