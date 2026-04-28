from google import genai
from google.genai import types
import inspect

options = types.HttpOptions(timeout=300)
print(f"Options: {options}")
print(f"Type of timeout: {type(options.timeout)}")

# Try to find the docstring for HttpOptions
print("\nDocstring:")
print(types.HttpOptions.__doc__)
