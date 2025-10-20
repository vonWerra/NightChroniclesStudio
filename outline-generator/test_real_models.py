from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Test modelů, které tvrdíte, že existují
models = [
    "gpt-4.1",
    "gpt-4-turbo-preview",
    "gpt-4",
    "gpt-3.5-turbo"
]

print("Testing OpenAI models...")
print("-" * 40)

for model_name in models:
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        print(f"✅ {model_name}: FUNGUJE")
    except Exception as e:
        error = str(e)
        if "does not exist" in error or "not found" in error:
            print(f"❌ {model_name}: NEEXISTUJE")
        else:
            print(f"⚠️ {model_name}: {error[:60]}")
