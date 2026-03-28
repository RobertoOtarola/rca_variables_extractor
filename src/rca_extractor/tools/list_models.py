import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("--- Listando modelos disponibles (Exploración de Atributos) ---")

try:
    models = client.models.list()
    for m in models:
        # En la v1.0+, imprimimos el nombre y el ID para estar seguros
        print(f"ID: {m.name} | Display Name: {m.display_name}")
except Exception as e:
    print(f"❌ Error al listar modelos: {e}")
