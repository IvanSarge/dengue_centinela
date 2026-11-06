# DengueCheck Pediátrico · Centinela Analytics

Aplicación web en español que estima el riesgo de **complicaciones en dengue pediátrico** con dos modelos de analítica de datos:

1. **Regresión logística** (regularizada, interpretable)
2. **Red neuronal artificial** (perceptrón multicapa)

Dataset: `data/MASTER_CHART_F1000Research.xlsx` (Bhaskar et al., F1000Research 2022, 11:446).

## Cómo ejecutarlo en Visual Studio Code

1. Abra la carpeta del proyecto: **Archivo → Abrir carpeta…** → `dengue_centinela`.
2. Abra la terminal: **Terminal → Nueva terminal**.
3. Cree y active un entorno virtual:

   **Windows (PowerShell)**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
   Si PowerShell bloquea el script: `Set-ExecutionPolicy -Scope Process Bypass` y repita el paso.

   **macOS / Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. Instale las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
5. Inicie la aplicación:
   ```bash
   python app.py
   ```
6. Abra en el navegador: **http://127.0.0.1:5000**

Para detener el servidor: `Ctrl + C`.

## Reentrenar los modelos (opcional)

Los modelos ya vienen entrenados en `models/`. Si lo desea, vuelva a generarlos con:

```bash
python -m src.entrenar
```

Si la versión de scikit-learn instalada no puede leer los modelos guardados, la aplicación los **reentrena automáticamente** al iniciar (tarda ~1 minuto).

## Estructura del proyecto

```
dengue_centinela/
├── app.py                  # Servidor Flask + API de predicción
├── requirements.txt        # Dependencias
├── Procfile                # Para publicar en la web (gunicorn)
├── data/
│   └── MASTER_CHART_F1000Research.xlsx
├── src/
│   ├── limpieza.py         # Limpieza y creación de variables
│   └── entrenar.py         # Entrenamiento y evaluación de los 2 modelos
├── models/
│   ├── modelo_logistica.joblib
│   ├── modelo_rna.joblib
│   └── metadata.json       # Métricas, curvas ROC, coeficientes, informe de limpieza
├── templates/index.html    # Página web
└── static/
    ├── css/estilos.css
    ├── js/app.js
    └── img/                # Logo y favicon
```

## Limpieza de datos aplicada

1. Normalización de nombres de columnas (a español).
2. Eliminación de columnas constantes (se verifican; en este dataset no hay).
3. Eliminación de duplicados (1 registro idéntico).
4. Conversión de códigos/texto a números 0/1 (Sí/No, sexo, edad, presión).
5. Eliminación de tratamientos (fuga de información) y de ferritina (37 % faltantes).
6. Imputación por mediana de los faltantes restantes (dentro del pipeline).
7. Creación de 11 variables nuevas (cortes clínicos, logaritmos, conteos, puntaje del estudio).

## Publicar en la web (Render)

Comando de compilación: `pip install -r requirements.txt` · Comando de inicio: `gunicorn app:app --timeout 120`.

- **Render / Railway / PythonAnywhere:** suba la carpeta, comando de inicio `gunicorn app:app`.
- Ya incluye `Procfile` y lee el puerto de la variable de entorno `PORT`.

> Proyecto académico. Las estimaciones son orientativas y no reemplazan el criterio médico.
