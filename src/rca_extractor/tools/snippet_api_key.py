import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL = "gemini-2.5-flash"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    model_info = client.models.get(model=MODEL)

    response = client.models.generate_content(
        model=MODEL,
        contents="Confirma conexión para el proyecto de extracción de RCA. Responde en una línea.",
    )

    print("✅ ¡Conexión Exitosa!")
    print(f"Modelo:            {model_info.name}")
    print(f"Nombre completo:   {model_info.display_name}")
    print(f"Respuesta:         {response.text.strip()}")

except Exception as e:
    print(f"❌ Error: {e}")
