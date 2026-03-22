# Plan de Correcciones para extractor_variables_rca

A continuación, presento los hallazgos tras revisar el código del proyecto y las correcciones necesarias sugeridas para que el código sea más robusto, asertivo y siga las mejores prácticas de Python.

## 1. Manejo de Configuración y Variables de Entorno
- **Problema**: El archivo [config.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/config.py) está vacío y existen varias rutas y nombres de archivos estáticos "hardcodeados" en [main.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/main.py) (como `PDF_FOLDER`, `OUTPUT_FILE`, `VARIABLES_FILE`). Además, [pdf_pipeline.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/pdf_pipeline.py) asume que `GEMINI_API_KEY` ya está definida en las variables de entorno sin intentar cargarla (por ejemplo, desde un archivo `.env`).
- **Solución**:
  - Utilizar la librería `python-dotenv` para cargar de forma segura la clave `GEMINI_API_KEY`.
  - Mover las constantes como rutas a [config.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/config.py) para centralizar la configuración.

## 2. Gestión de Archivos en la API de Gemini (Fuga de recursos)
- **Problema**: En [gemini_client.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/gemini_client.py) y [pdf_pipeline.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/pdf_pipeline.py), los archivos PDF se suben a la API de Gemini mediante `self.client.upload_pdf(pdf_path)`, pero **nunca se eliminan**. Esto puede provocar que se alcance rápidamente el límite de almacenamiento de la cuenta de Google.
- **Solución**: Implementar un bloque `try...finally` en [process_pdf](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/pdf_pipeline.py#15-28) para asegurar que el archivo subido se elimine del servidor de Gemini explícitamente usando `genai.delete_file(file_ref.name)`.

## 3. Uso de Variables y Parámetros ignorados
- **Problema**: En [main.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/main.py), se instancia el extractor de esta manera: [RCAExtractor(model="gemini-1.5-pro-latest", temperature=0)](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/pdf_pipeline.py#7-39). Sin embargo, en [pdf_pipeline.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/pdf_pipeline.py), dentro de [__init__](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/pdf_pipeline.py#9-14), se recibe `temperature` pero **nunca lo usa ni se le provee al cliente de Gemini**. Esto hace que las respuestas se generen con una temperatura errónea.
- **Solución**: En [gemini_client.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/gemini_client.py) y [pdf_pipeline.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/pdf_pipeline.py), aceptar el parámetro `temperature` y enviarlo a Gemini utilizando `genai.GenerationConfig`.

## 4. Manejo de Rutas Multiplataforma
- **Problema**: En [pdf_pipeline.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/pdf_pipeline.py), se extrae el nombre del archivo usando `.split("/")[-1]`. Esto fallará silenciosamente o devolverá resultados incorrectos en Windows debido a que usa la barra invertida `\`.
- **Solución**: Utilizar `pathlib.Path(pdf_path).name` o `os.path.basename` para extraer el nombre del archivo de forma correcta en cualquier Sistema Operativo.

## 5. Validaciones y Manejo de Errores
- **Problema**: Faltan validaciones clave. Por ejemplo, en [pdf_pipeline.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/pdf_pipeline.py), si no existe `GEMINI_API_KEY`, el programa falla de manera críptica en el interior del SDK. Además, `response.text` en [gemini_client.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/gemini_client.py) lanzaría un `ValueError` si el modelo bloqueara la salida por restricciones de seguridad, interrumpiendo todo el programa.
- **Solución**:
  - Levantar un `ValueError` explícito si `GEMINI_API_KEY` es nula.
  - Asegurarse de realizar un manejo adecuado en [gemini_client.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/gemini_client.py) si hay un error al acceder al texto de la respuesta.

## 6. Riesgo de pérdida de información (Persistencia)
- **Problema**: En [main.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/ChatGPT/extractor_variables_rca/main.py), se procesan sucesivamente todos los PDFs, y los resultados se almacenan en memoria y se guardan un DataFrame al final de todas las iteraciones. Si hubiese un error o cierre inesperado luego de procesar algunos archivos, todo el progreso se perderá.
- **Solución**: Aunque la implementación sea funcional, sería útil almacenar resultados parciales o por lo menos capturar el error individual sin cerrar el bucle principal.

---

## User Review Required
Por favor, revisa estas propuestas. Si estás de acuerdo, dímelo y procederé a aplicar todas estas correcciones al repositorio.
