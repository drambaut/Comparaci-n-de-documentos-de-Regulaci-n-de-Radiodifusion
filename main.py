import os
from dotenv import load_dotenv
from src.cleaner import limpiar_documento_draftable
from src.analyzer import extraer_datos_limpios, analizar_con_experto_ia, generar_informe_word

# Cargar variables de entorno
load_dotenv()

# Configuración de variables del proyecto
AÑO_ANTIGUO = "2020"
AÑO_RECIENTE = "2024"

# Definición de rutas relativas (hace que funcione en cualquier PC)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_INPUT_DRAFTABLE = os.path.join(BASE_DIR, "data", "02_draftable_outputs", f"{AÑO_ANTIGUO}-RR-Vol1 vs {AÑO_RECIENTE}}-RR-Vol1 - Changes_Report_Raw.docx")
RUTA_OUTPUT_LIMPIO = os.path.join(BASE_DIR, "data", "03_procesados", "Reporte_Limpio_RR.docx")
RUTA_OUTPUT_FINAL = os.path.join(BASE_DIR, "data", "04_informes_finales", "Informe_Ejecutivo_Cambios_RR.docx")

def main():
    print("Iniciando Pipeline de Análisis del Reglamento de Radiocomunicaciones...")
    
    # 1. Verificar input
    if not os.path.exists(RUTA_INPUT_DRAFTABLE):
        print(f"No se encontró el archivo de entrada en: {RUTA_INPUT_DRAFTABLE}")
        print("Asegúrate de colocar el archivo generado por Draftable en esa ruta.")
        return

    # 2. Limpieza determinística
    exito_limpieza = limpiar_documento_draftable(RUTA_INPUT_DRAFTABLE, RUTA_OUTPUT_LIMPIO)
    
    if not exito_limpieza:
        return

    # 3. Análisis cognitivo
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Falla crítica: No se encontró GEMINI_API_KEY en el archivo .env")
        return

    print("Extrayendo datos limpios para la IA...")
    filas = extraer_datos_limpios(RUTA_OUTPUT_LIMPIO)
    
    if filas:
        resultado_json = analizar_con_experto_ia(filas, api_key, AÑO_ANTIGUO, AÑO_RECIENTE)
        
        # 4. Generación de informe
        if resultado_json:
            generar_informe_word(resultado_json, RUTA_OUTPUT_FINAL, AÑO_ANTIGUO, AÑO_RECIENTE)
    else:
        print("El documento procesado no arrojó cambios significativos.")

if __name__ == "__main__":
    main()