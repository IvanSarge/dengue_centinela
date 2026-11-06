"""
Limpieza y preparación de datos - DengueCheck Pediátrico
=========================================================
Técnicas aplicadas (vistas en clase):
  1. Normalización de nombres de columnas (texto -> identificadores en español).
  2. Eliminación de columnas con valores constantes.
  3. Eliminación de registros duplicados.
  4. Conversión de códigos de texto/numéricos (1 = Sí, 2 = No ...) a variables binarias 0/1.
  5. Tratamiento de valores faltantes (imputación por mediana, dentro del pipeline).
  6. Eliminación de variables que provocan fuga de información (tratamientos) o con
     exceso de datos faltantes (ferritina).
  7. Creación de nuevas variables (ingeniería de características).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Diccionario de columnas originales -> nombres limpios
# --------------------------------------------------------------------------- #
RENOMBRAR = {
    "GROUPS: DENGUE FEVER OR COMPLICATED DENGUE": "grupo",
    "AGE": "edad",
    "GENDER": "sexo",
    "DURATION OF FEVER": "duracion_fiebre",
    "HEADACHE": "cefalea",
    "MYALGIA": "mialgia",
    "ABDOMINAL PAIN": "dolor_abdominal",
    "RASH": "exantema",
    "VOMITING": "vomito",
    "BREATHLESSNESS": "disnea",
    "BLEEDING": "sangrado",
    "BP AT ADMISSION": "presion_ingreso",
    "ORGANOMEGALY": "organomegalia",
    "HB": "hemoglobina",
    "PCV": "pcv",
    "LOWEST WBC": "leuco_min",
    "HIGHEST WBC": "leuco_max",
    "PLATELET COUNT": "plaquetas",
    "ALT": "alt",
    "CREATININE": "creatinina",
    "FERRITIN": "ferritina",
    "IV FLUIDS": "fluidos_iv",
    "ANTIBIOTICS": "antibioticos",
    "ANTIPYRETICS": "antipireticos",
    "STEROIDS": "esteroides",
}

# Variables de tratamiento: se deciden DESPUÉS de conocer la gravedad -> fuga de datos.
COLUMNAS_TRATAMIENTO = ["fluidos_iv", "antibioticos", "antipireticos", "esteroides"]
# Más de 1/3 de datos faltantes (el propio estudio la excluyó del modelo multivariable).
COLUMNAS_MUCHOS_FALTANTES = ["ferritina"]

# Variables binarias en que 1 = Sí, 2 = No
BINARIAS_SI_NO = ["cefalea", "mialgia", "dolor_abdominal", "exantema", "vomito",
                  "disnea", "sangrado", "organomegalia"]

# Variables originales que entran al modelo (todas disponibles al ingreso del paciente)
VARIABLES_BASE = [
    "edad_mayor_6", "sexo_masculino", "duracion_fiebre",
    "cefalea", "mialgia", "dolor_abdominal", "exantema", "vomito", "disnea",
    "sangrado", "hipotension", "organomegalia",
    "hemoglobina", "pcv", "leuco_min", "leuco_max", "plaquetas", "alt", "creatinina",
]

# Variables creadas
VARIABLES_NUEVAS = [
    "rango_leucocitos", "log_alt", "log_plaquetas",
    "fiebre_prolongada", "pcv_alto", "plaquetas_bajas", "leucocitos_altos", "alt_elevada",
    "n_sintomas", "signos_alarma", "puntaje_estudio",
]

VARIABLES_MODELO = VARIABLES_BASE + VARIABLES_NUEVAS

# Puntos de corte publicados por Bhaskar et al. (2022), F1000Research 11:446
CORTES = {"pcv": 42.0, "plaquetas": 75000.0, "leuco_max": 7000.0, "alt": 70.0, "fiebre": 6}


def crear_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Crea las variables derivadas. Se usa tanto en entrenamiento como en predicción."""
    d = df.copy()
    d["rango_leucocitos"] = d["leuco_max"] - d["leuco_min"]
    d["log_alt"] = np.log1p(d["alt"])
    d["log_plaquetas"] = np.log1p(d["plaquetas"])
    d["fiebre_prolongada"] = (d["duracion_fiebre"] >= CORTES["fiebre"]).astype(int)
    d["pcv_alto"] = (d["pcv"] >= CORTES["pcv"]).astype(int)
    d["plaquetas_bajas"] = (d["plaquetas"] <= CORTES["plaquetas"]).astype(int)
    d["leucocitos_altos"] = (d["leuco_max"] >= CORTES["leuco_max"]).astype(int)
    d["alt_elevada"] = (d["alt"] >= CORTES["alt"]).astype(int)
    d["n_sintomas"] = d[["cefalea", "mialgia", "dolor_abdominal", "exantema", "vomito", "disnea"]].sum(axis=1)
    d["signos_alarma"] = d[["sangrado", "organomegalia", "hipotension"]].sum(axis=1)
    # Puntaje clínico del estudio original (0-7): hipotensión = 3 puntos; los demás 1 punto
    d["puntaje_estudio"] = (3 * d["hipotension"] + d["pcv_alto"] + d["plaquetas_bajas"]
                            + d["leucocitos_altos"] + d["alt_elevada"])
    return d


def limpiar_dataset(ruta_excel: str):
    """Devuelve (DataFrame limpio, informe de limpieza)."""
    informe = []
    df = pd.read_excel(ruta_excel)
    informe.append({"paso": "Carga del archivo Excel",
                    "detalle": f"{df.shape[0]} filas y {df.shape[1]} columnas originales.",
                    "filas": int(df.shape[0]), "columnas": int(df.shape[1])})

    # 1. Nombres de columnas
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns=RENOMBRAR)
    informe.append({"paso": "Normalización de nombres",
                    "detalle": "Se eliminaron espacios y se tradujeron las 25 columnas a nombres claros en español.",
                    "filas": int(df.shape[0]), "columnas": int(df.shape[1])})

    # 2. Columnas constantes
    constantes = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
    df = df.drop(columns=constantes)
    informe.append({"paso": "Eliminación de columnas constantes",
                    "detalle": (f"Se eliminaron: {', '.join(constantes)}." if constantes
                                else "Se revisaron las 25 columnas: ninguna tiene un valor único (no hubo que eliminar)."),
                    "filas": int(df.shape[0]), "columnas": int(df.shape[1])})

    # 3. Duplicados
    n_dup = int(df.duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)
    informe.append({"paso": "Eliminación de registros duplicados",
                    "detalle": f"Se eliminó {n_dup} registro idéntico en las 25 variables (posible doble digitación).",
                    "filas": int(df.shape[0]), "columnas": int(df.shape[1])})

    # 4. Variable objetivo y conversión de códigos a 0/1
    df["complicado"] = (df["grupo"] == 2).astype(int)           # 2 = dengue complicado
    df["edad_mayor_6"] = (df["edad"] == 2).astype(int)          # 1 = ≤6 años, 2 = >6 años
    df["sexo_masculino"] = (df["sexo"] == 1).astype(int)        # 1 = masculino
    for c in BINARIAS_SI_NO:
        df[c] = (df[c] == 1).astype(int)                        # 1 = Sí, 2 = No
    df["hipotension"] = (df["presion_ingreso"] == 2).astype(int)  # 2 = hipotensión (verificado con el artículo: 38 casos)
    informe.append({"paso": "Conversión de texto/códigos a números",
                    "detalle": "Los códigos 1/2 (Sí/No, Masculino/Femenino, ≤6/>6 años, Presión normal/Hipotensión) "
                               "se convirtieron a variables binarias 0/1. Variable objetivo: complicado (1) vs. dengue sin complicaciones (0).",
                    "filas": int(df.shape[0]), "columnas": int(df.shape[1])})

    # 5. Fuga de información y datos faltantes
    n_falt_ferritina = int(df["ferritina"].isna().sum())
    df = df.drop(columns=COLUMNAS_TRATAMIENTO + COLUMNAS_MUCHOS_FALTANTES + ["grupo", "edad", "sexo", "presion_ingreso"])
    informe.append({"paso": "Eliminación de variables no utilizables",
                    "detalle": ("Se descartaron los 4 tratamientos (fluidos IV, antibióticos, antipiréticos, esteroides) porque se "
                                "indican después de conocer la gravedad (fuga de información), y la ferritina por tener "
                                f"{n_falt_ferritina} valores faltantes ({n_falt_ferritina/len(df):.0%})."),
                    "filas": int(df.shape[0]), "columnas": int(df.shape[1])})

    # 6. Faltantes restantes
    faltantes = df[VARIABLES_BASE].isna().sum()
    faltantes = faltantes[faltantes > 0]
    informe.append({"paso": "Valores faltantes restantes",
                    "detalle": (f"Se detectaron faltantes en {', '.join(faltantes.index)} (1 registro). "
                                "Se imputan con la mediana dentro del pipeline de entrenamiento (sin filtrar información del conjunto de prueba)."
                                if len(faltantes) else "No quedan valores faltantes."),
                    "filas": int(df.shape[0]), "columnas": int(df.shape[1])})

    # 7. Variables nuevas
    df = crear_variables(df)
    informe.append({"paso": "Creación de nuevas variables",
                    "detalle": ("Se crearon 11 variables: rango de leucocitos, log(ALT), log(plaquetas), fiebre prolongada (≥6 días), "
                                "PCV alto, plaquetas bajas, leucocitosis, ALT elevada, n.º de síntomas, n.º de signos de alarma "
                                "y el puntaje clínico del estudio original (0-7)."),
                    "filas": int(df.shape[0]), "columnas": int(df.shape[1])})

    df = df[VARIABLES_MODELO + ["complicado"]]
    informe.append({"paso": "Dataset final para modelado",
                    "detalle": f"{len(VARIABLES_MODELO)} variables predictoras ({len(VARIABLES_BASE)} originales + {len(VARIABLES_NUEVAS)} nuevas) y 1 variable objetivo.",
                    "filas": int(df.shape[0]), "columnas": int(df.shape[1])})
    return df, informe
