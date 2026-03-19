# 📡 Proyecto CNABF: Automatización de Análisis del Reglamento de Radiocomunicaciones

Este repositorio contiene el pipeline de datos y automatización mediante Inteligencia Artificial diseñado para comparar e identificar las diferencias sustanciales entre las distintas ediciones del **Reglamento de Radiocomunicaciones (RR) de la UIT**. 

El objetivo principal es reducir la carga operativa y mitigar el error humano en la actualización del Cuadro Nacional de Atribución de Bandas de Frecuencias (CNABF).

## 🌳 Treefile del repo

Aquí puedes ver la estructura principal del proyecto y dónde debe ir cada archivo:

```text
ane-cnabf-comparador-rr/
│
├── data/
│   ├── 01_originales_rr/         # PDFs originales (Edición 2020 y 2024)
│   ├── 02_draftable_outputs/     # Salidas directas de Draftable (Word "Changes Report" y PDF Side-by-Side)
│   ├── 03_procesados/            # Resultado del script de limpieza (Reporte_Limpio_RR.docx)
│   └── 04_informes_finales/      # Resultado de la IA (Informe_Ejecutivo_Cambios_RR.docx)
│
├── src/                          # Código fuente modularizado
│   ├── __init__.py
│   ├── cleaner.py                # Lógica de limpieza de filas (Regex y manipulación XML)
│   └── analyzer.py               # Lógica de conexión con Gemini y generación de Word
│
├── .env.example                  # Plantilla de variables de entorno
├── .gitignore                    # Archivos a ignorar en Git (ej. .env, carpetas __pycache__)
├── main.py                       # Orquestador: El único archivo que el usuario debe ejecutar
├── requirements.txt              # Dependencias actualizadas
└── README.md                     # Documentación profesional del proyecto
```

## 🗂 Estructura de Datos (`/data`)

El flujo de trabajo requiere que los archivos se ubiquen en carpetas específicas:
* `01_originales_rr/`: Contiene los PDFs oficiales de la UIT (Ej. Volumen 1 2020 y 2024). *Usados solo como referencia.*
* `02_draftable_outputs/`: **(Tu Input)** Aquí debes colocar el reporte de Word exportado por la herramienta Draftable.
* `03_procesados/`: Almacena el reporte intermedio limpio de ruido de formato (`Reporte_Limpio_RR.docx`).
* `04_informes_finales/`: Directorio de salida del `Informe_Ejecutivo_Cambios_RR.docx` generado por la IA.

## ⚙️ Flujo de Trabajo (Instrucciones de Uso)

El sistema está diseñado para ser de ejecución sencilla. Sigue estos 3 pasos:

### 1. Extracción Inicial (Vía Draftable)
1. Ingresa a Draftable y carga los dos volúmenes en PDF del RR que deseas comparar.
2. Selecciona como *Comparison Type* la opción **"Side by Side in Draftable"** para visualizar los cambios.
3. Exporta la tabla de desviaciones en formato Word (Changes Report).
4. Renombra ese archivo exportado a `2020-RR-Vol1 vs 2024-RR-Vol1 - Changes_Report_Raw.docx` y guárdalo en la carpeta `data/02_draftable_outputs/`.

### 2. Configuración del Entorno
Instala las dependencias y configura tu clave de API:
```bash
# Instalar requerimientos
pip install -r requirements.txt

# Copia el ejemplo de variables de entorno y agrega tu API Key de Gemini
cp .env.example .env
```

### 3. Ejecución del Pipeline
Ejecuta el orquestador principal. El script se encargará automáticamente de limpiar el documento (reduciendo miles de filas de ruido) y de redactar el informe final.
```bash
python main.py
```
> **Nota:** Revisa la carpeta `data/04_informes_finales/` para obtener tu documento final en formato institucional (Arial 12).

## 🔄 Mantenibilidad y Actualizaciones Futuras

Este proyecto está diseñado para ser escalable para futuras Conferencias Mundiales de Radiocomunicaciones (ej. CMR-27). Para adaptar el código a nuevas ediciones:

1. **Actualizar Años:** En el archivo `main.py`, modifica las variables globales `AÑO_ANTIGUO` y `AÑO_RECIENTE`.
2. **Ajustar Criterios de Limpieza (Opcional):** Si en el futuro la UIT cambia sus marcadores, puedes actualizar la expresión regular (`Regex`) ubicada en `src/cleaner.py` para incluir nuevas palabras clave técnicas.
3. **Actualización de API:** El proyecto utiliza el SDK moderno `google-genai`. Si hay cambios en los modelos de Google, la actualización se gestiona centralizadamente en `src/analyzer.py`.