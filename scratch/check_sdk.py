from google import genai
from google.genai import types
import time

try:
    client = genai.Client(api_key="dummy", http_options=types.HttpOptions(timeout=1))
    print("Client created with 1s timeout")
    # We can't really test it without a real key easily, but we can check the docstring if possible or just guess based on common SDK patterns.
    # Actually, let's look at the installed package info.
except Exception as e:
    print(f"Error: {e}")
