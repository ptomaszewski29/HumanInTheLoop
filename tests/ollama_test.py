from services.ollama_service import (
    OllamaService,
)

service = OllamaService(model="qwen3")

result = service.generate_code("Create a TypeScript email validator")

print()
print("=" * 80)
print("RESULT")
print("=" * 80)
print(repr(result))
print("=" * 80)
