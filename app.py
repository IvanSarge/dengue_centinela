"""
DengueCheck Pediátrico - Centinela Analytics
Aplicación web (Flask) con dos modelos: Regresión Logística y Red Neuronal Artificial.

Ejecutar:   python app.py      ->  http://127.0.0.1:5000
"""
from __future__ import annotations

import json
import os
import warnings

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request

from src.limpieza import VARIABLES_BASE, VARIABLES_MODELO, crear_variables

warnings.filterwarnings("ignore")

RAIZ = os.path.dirname(os.path.abspath(__file__))
RUTA_MODELOS = os.path.join(RAIZ, "models")
NOMBRES_MODELOS = {"logistica": "Regresión logística", "rna": "Red neuronal artificial"}

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.json.ensure_ascii = False


# --------------------------------------------------------------------------- #
# Carga de modelos (si faltan o son incompatibles con la versión instalada
# de scikit-learn, se vuelven a entrenar automáticamente)
# --------------------------------------------------------------------------- #
def cargar_modelos():
    try:
        modelos = {n: joblib.load(os.path.join(RUTA_MODELOS, f"modelo_{n}.joblib")) for n in NOMBRES_MODELOS}
        with open(os.path.join(RUTA_MODELOS, "metadata.json"), encoding="utf-8") as f:
            meta = json.load(f)
        # prueba de humo
        modelos["logistica"].predict_proba(pd.DataFrame([{c: 0.0 for c in VARIABLES_MODELO}]))
        return modelos, meta
    except Exception as exc:  # noqa: BLE001
        print(f"[aviso] No se pudieron cargar los modelos guardados ({exc}). Entrenando de nuevo...")
        from src.entrenar import entrenar_todo
        return entrenar_todo(verbose=True)


MODELOS, META = cargar_modelos()

# --------------------------------------------------------------------------- #
# Validación de los datos del formulario
# --------------------------------------------------------------------------- #
BINARIAS = ["edad_mayor_6", "sexo_masculino", "cefalea", "mialgia", "dolor_abdominal", "exantema",
            "vomito", "disnea", "sangrado", "hipotension", "organomegalia"]
NUMERICAS = {  # variable: (mínimo, máximo, etiqueta)
    "duracion_fiebre": (1, 20, "Duración de la fiebre"),
    "hemoglobina": (4, 25, "Hemoglobina"),
    "pcv": (12, 70, "Hematocrito (PCV)"),
    "leuco_min": (300, 60000, "Leucocitos mínimos"),
    "leuco_max": (300, 60000, "Leucocitos máximos"),
    "plaquetas": (1000, 900000, "Plaquetas"),
    "alt": (1, 6000, "ALT"),
    "creatinina": (0.05, 15, "Creatinina"),
}


def validar(datos: dict):
    limpio, errores = {}, []
    for c in BINARIAS:
        v = datos.get(c)
        if v not in (0, 1, "0", "1", True, False):
            errores.append(f"Falta indicar: {c.replace('_', ' ')}.")
        else:
            limpio[c] = int(v)
    for c, (lo, hi, etiqueta) in NUMERICAS.items():
        try:
            v = float(datos.get(c))
        except (TypeError, ValueError):
            errores.append(f"{etiqueta}: ingrese un número válido.")
            continue
        if not (lo <= v <= hi):
            errores.append(f"{etiqueta}: el valor debe estar entre {lo:g} y {hi:g}.")
        limpio[c] = v
    if not errores and limpio["leuco_max"] < limpio["leuco_min"]:
        errores.append("Los leucocitos máximos no pueden ser menores que los mínimos.")
    return limpio, errores


def a_dataframe(fila: dict) -> pd.DataFrame:
    return crear_variables(pd.DataFrame([fila])[VARIABLES_BASE])[VARIABLES_MODELO]


def nivel_riesgo(prob: float, umbral: float):
    if prob >= umbral:
        return "alto", "Riesgo alto"
    if prob >= umbral * 0.5:
        return "moderado", "Riesgo moderado"
    return "bajo", "Riesgo bajo"


# Valores de referencia ("paciente típico sin hallazgos") para explicar cada predicción
def referencia():
    ref = {c: 0 for c in BINARIAS}
    for c in NUMERICAS:
        ref[c] = META["rangos"][c][1]  # mediana
    return ref


REF = referencia()
ETIQUETAS_FACTORES = {
    "edad_mayor_6": "Edad > 6 años", "sexo_masculino": "Sexo masculino", "cefalea": "Cefalea",
    "mialgia": "Mialgia", "dolor_abdominal": "Dolor abdominal", "exantema": "Exantema", "vomito": "Vómito",
    "disnea": "Disnea", "sangrado": "Sangrado", "hipotension": "Hipotensión", "organomegalia": "Organomegalia",
    "duracion_fiebre": "Duración de la fiebre", "hemoglobina": "Hemoglobina", "pcv": "Hematocrito (PCV)",
    "leuco_min": "Leucocitos mínimos", "leuco_max": "Leucocitos máximos", "plaquetas": "Plaquetas",
    "alt": "ALT", "creatinina": "Creatinina",
}


def factores(modelo, fila: dict, prob_base: float):
    """Impacto de cada dato: cuánto cambia la probabilidad al sustituirlo por un valor de referencia."""
    filas = []
    for c in ETIQUETAS_FACTORES:
        alt = dict(fila)
        alt[c] = REF[c]
        p = float(modelo.predict_proba(a_dataframe(alt))[0, 1])
        filas.append((c, prob_base - p))
    filas.sort(key=lambda t: abs(t[1]), reverse=True)
    return [{"variable": c, "etiqueta": ETIQUETAS_FACTORES[c], "impacto": round(d * 100, 1)}
            for c, d in filas[:6] if abs(d) >= 0.002]


RECOMENDACIONES = {
    "bajo": "El perfil clínico del paciente se asemeja al de los casos de dengue sin complicaciones del estudio. "
            "Se sugiere vigilancia de signos de alarma y control clínico según el criterio médico.",
    "moderado": "El perfil presenta algunos hallazgos asociados a complicaciones. Se sugiere observación estrecha, "
                "repetir hemograma y evaluar la necesidad de hospitalización según el criterio médico.",
    "alto": "El perfil se asemeja al de los casos de dengue complicado del estudio. Se sugiere valoración médica prioritaria, "
            "monitoreo hemodinámico y seguimiento de laboratorio frecuente.",
}


# --------------------------------------------------------------------------- #
# Rutas
# --------------------------------------------------------------------------- #
@app.route("/")
def inicio():
    return render_template("index.html", meta=META)


@app.route("/api/metadatos")
def api_metadatos():
    return jsonify(META)


@app.route("/salud")
def salud():
    return jsonify({"estado": "ok", "modelos": list(MODELOS)})


@app.route("/api/predecir", methods=["POST"])
def api_predecir():
    datos = request.get_json(silent=True) or {}
    fila, errores = validar(datos)
    if errores:
        return jsonify({"ok": False, "errores": errores}), 400

    X = a_dataframe(fila)
    puntaje = int(X["puntaje_estudio"].iloc[0])
    resultados = {}
    for nombre, modelo in MODELOS.items():
        prob = float(modelo.predict_proba(X)[0, 1])
        umbral = float(META["modelos"][nombre]["umbral"])
        clave, texto = nivel_riesgo(prob, umbral)
        resultados[nombre] = {
            "nombre": NOMBRES_MODELOS[nombre],
            "probabilidad": round(prob * 100, 1),
            "umbral": round(umbral * 100, 1),
            "nivel": clave, "nivel_texto": texto,
            "complicado": bool(prob >= umbral),
            "factores": factores(modelo, fila, prob),
            "recomendacion": RECOMENDACIONES[clave],
        }
    acuerdo = resultados["logistica"]["complicado"] == resultados["rna"]["complicado"]
    return jsonify({
        "ok": True, "resultados": resultados, "puntaje_estudio": puntaje,
        "puntaje_alto": puntaje >= 2, "modelos_coinciden": bool(acuerdo),
    })


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto, debug=False)
