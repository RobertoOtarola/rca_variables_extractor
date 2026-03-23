import subprocess
import os

def check_git_ignored_status():
    """
    Comprueba si los archivos locales están correctamente ignorados 
    según las reglas de Git.
    """
    print(f"--- Validando estructura en: {os.getcwd()} ---")
    
    try:
        # 1. Obtener lista de archivos que Git está siguiendo actualmente
        tracked_files = subprocess.check_output(
            ["git", "ls-files"], text=True
        ).splitlines()

        # 2. Verificar si alguno de esos archivos coincide con las reglas del .gitignore
        # 'git check-ignore' devuelve los archivos que coinciden con el .gitignore
        ignored_but_tracked = []
        
        # Usamos un proceso por lotes para eficiencia
        if tracked_files:
            process = subprocess.Popen(
                ["git", "check-ignore", "--stdin"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, _ = process.communicate(input="\n".join(tracked_files))
            ignored_but_tracked = stdout.splitlines()

        # 3. Reporte de resultados
        if not ignored_but_tracked:
            print("✅ ¡Perfecto! No hay archivos en el repo que deban estar ignorados.")
        else:
            print("⚠️  ATENCIÓN: Los siguientes archivos están en el repo pero tu .gitignore dice que deberían excluirse:")
            for file in ignored_but_tracked:
                print(f"   - {file}")
            print("\n💡 Tip: Usa 'git rm --cached <archivo>' para dejar de seguirlos sin borrarlos del disco.")

    except subprocess.CalledProcessError as e:
        print(f"❌ Error al ejecutar comandos de Git: {e}")
    except FileNotFoundError:
        print("❌ Error: No se encontró el comando 'git'. Asegúrate de tenerlo instalado.")

if __name__ == "__main__":
    check_git_ignored_status()
    