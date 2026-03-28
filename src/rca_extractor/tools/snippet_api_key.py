import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Configuración del cliente
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    # Usamos el ID exacto que obtuvimos del listado: gemini-2.0-flash
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Hola Gemini, confirma conexión para el proyecto de extracción de RCA.",
    )

    print("✅ ¡Conexión Exitosa!")
    print(f"Respuesta del modelo: {response.text}")

except Exception as e:
    print(f"❌ Error persistente: {e}")
