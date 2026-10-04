from openai import OpenAI
from config import NVIDIA_API_KEY, NVIDIA_MODEL, NVIDIA_BASE_URL

client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key="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", timeout=30.0)

print("Enviando requisição...", flush=True)
r = client.chat.completions.create(
    model=NVIDIA_MODEL,
    messages=[{"role": "user", "content": "Diga apenas: OK"}],
    max_tokens=500,
)

msg = r.choices[0].message
print("=== message.content ===")
print(repr(msg.content))
print()
print("=== attrs do message ===")
print(msg.model_dump())