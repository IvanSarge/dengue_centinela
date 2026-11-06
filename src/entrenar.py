"""
Entrenamiento de los dos modelos de DengueCheck Pediátrico
==========================================================
  - Regresión logística (con regularización, hiperparámetros por validación cruzada)
  - Red neuronal artificial (perceptrón multicapa, hiperparámetros por validación cruzada)

Uso:  python -m src.entrenar
Genera: models/modelo_logistico.joblib, models/modelo_rna.joblib, models/metadata.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, roc_auc_score, roc_curve
from sklearn.model_selection import (GridSearchCV, RepeatedStratifiedKFold,
                                     StratifiedKFold, cross_val_predict,
                                     train_test_split)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Permite ejecutar tanto como módulo como script
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from src.limpieza import VARIABLES_MODELO, limpiar_dataset  # noqa: E402

RUTA_DATOS = os.path.join(RAIZ, "data", "MASTER_CHART_F1000Research.xlsx")
RUTA_MODELOS = os.path.join(RAIZ, "models")
SEMILLA = 42

ETIQUETAS = {
    "edad_mayor_6": "Edad > 6 años", "sexo_masculino": "Sexo masculino",
    "duracion_fiebre": "Duración de la fiebre (días)", "cefalea": "Cefalea",
    "mialgia": "Mialgia", "dolor_abdominal": "Dolor abdominal", "exantema": "Exantema",
    "vomito": "Vómito", "disnea": "Disnea", "sangrado": "Sangrado",
    "hipotension": "Hipotensión", "organomegalia": "Organomegalia",
    "hemoglobina": "Hemoglobina", "pcv": "Hematocrito (PCV)", "leuco_min": "Leucocitos (mínimo)",
    "leuco_max": "Leucocitos (máximo)", "plaquetas": "Plaquetas", "alt": "ALT",
    "creatinina": "Creatinina", "rango_leucocitos": "Rango de leucocitos",
    "log_alt": "ALT (log)", "log_plaquetas": "Plaquetas (log)",
    "fiebre_prolongada": "Fiebre ≥ 6 días", "pcv_alto": "PCV ≥ 42 %",
    "plaquetas_bajas": "Plaquetas ≤ 75 000", "leucocitos_altos": "Leucocitos ≥ 7 000",
    "alt_elevada": "ALT ≥ 70 U/L", "n_sintomas": "N.º de síntomas",
    "signos_alarma": "N.º de signos de alarma", "puntaje_estudio": "Puntaje clínico (0-7)",
}


def construir_pipeline(clasificador):
    pre = ColumnTransformer([("num", Pipeline([
        ("imputar", SimpleImputer(strategy="median")),
        ("escalar", StandardScaler()),
    ]), VARIABLES_MODELO)])
    return Pipeline([("pre", pre), ("clf", clasificador)])


def metricas(y, prob, umbral):
    pred = (prob >= umbral).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    div = lambda a, b: float(a / b) if b else 0.0  # noqa: E731
    return {
        "auc": float(roc_auc_score(y, prob)),
        "sensibilidad": div(tp, tp + fn), "especificidad": div(tn, tn + fp),
        "vpp": div(tp, tp + fp), "vpn": div(tn, tn + fn),
        "exactitud": div(tp + tn, len(y)), "f1": float(f1_score(y, pred)),
        "matriz": {"vn": int(tn), "fp": int(fp), "fn": int(fn), "vp": int(tp)},
    }


def umbral_youden(y, prob):
    fpr, tpr, thr = roc_curve(y, prob)
    j = tpr - fpr
    return float(thr[int(np.argmax(j))])


def curva_roc(y, prob, n=60):
    fpr, tpr, _ = roc_curve(y, prob)
    # reducir puntos para el JSON
    grid = np.linspace(0, 1, n)
    tpr_i = np.interp(grid, fpr, tpr)
    return {"fpr": [round(float(x), 4) for x in grid], "tpr": [round(float(x), 4) for x in tpr_i]}


def entrenar_todo(verbose=True):
    log = print if verbose else (lambda *a, **k: None)
    os.makedirs(RUTA_MODELOS, exist_ok=True)

    df, informe = limpiar_dataset(RUTA_DATOS)
    X, y = df[VARIABLES_MODELO], df["complicado"]
    log(f"Dataset limpio: {X.shape[0]} pacientes, {X.shape[1]} variables, prevalencia {y.mean():.1%}")

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=SEMILLA)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA)

    definiciones = {
        "logistica": (
            LogisticRegression(max_iter=5000, class_weight="balanced", penalty="l2", solver="lbfgs", random_state=SEMILLA),
            {"clf__C": [0.01, 0.03, 0.1, 0.3, 1, 3]},
        ),
        "rna": (
            MLPClassifier(max_iter=3000, random_state=SEMILLA, solver="adam"),
            {"clf__hidden_layer_sizes": [(8,), (16,), (32,), (16, 8)],
             "clf__activation": ["relu", "tanh"],
             "clf__alpha": [0.01, 0.1, 1.0, 3.0]},
        ),
    }

    meta = {
        "version_sklearn": sklearn.__version__,
        "fecha_entrenamiento": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_pacientes": int(len(df)), "n_variables": len(VARIABLES_MODELO),
        "n_entrenamiento": int(len(X_tr)), "n_prueba": int(len(X_te)),
        "prevalencia": float(y.mean()),
        "n_complicados": int(y.sum()), "n_no_complicados": int((1 - y).sum()),
        "informe_limpieza": informe, "modelos": {},
        "etiquetas": {k: ETIQUETAS[k] for k in VARIABLES_MODELO},
    }

    modelos_finales = {}
    for nombre, (clf, grilla) in definiciones.items():
        log(f"\n=== {nombre.upper()} ===")
        busqueda = GridSearchCV(construir_pipeline(clf), grilla, scoring="roc_auc", cv=cv, n_jobs=-1)
        busqueda.fit(X_tr, y_tr)
        mejor = busqueda.best_estimator_
        log("Mejores hiperparámetros:", busqueda.best_params_, f"| AUC CV = {busqueda.best_score_:.3f}")

        # Umbral óptimo (índice de Youden) con predicciones fuera de muestra del entrenamiento
        prob_oof = cross_val_predict(mejor, X_tr, y_tr, cv=cv, method="predict_proba")[:, 1]
        umbral = umbral_youden(y_tr, prob_oof)

        prob_te = mejor.predict_proba(X_te)[:, 1]
        m_te = metricas(y_te, prob_te, umbral)
        m_cv = metricas(y_tr, prob_oof, umbral)

        # Estabilidad: validación cruzada repetida (5 x 3) sobre todo el conjunto
        rcv = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=SEMILLA)
        aucs = []
        for tr, va in rcv.split(X, y):
            m = construir_pipeline(clf.__class__(**{**clf.get_params(), **{k.replace("clf__", ""): v for k, v in busqueda.best_params_.items()}}))
            m.fit(X.iloc[tr], y.iloc[tr])
            aucs.append(roc_auc_score(y.iloc[va], m.predict_proba(X.iloc[va])[:, 1]))
        log(f"AUC prueba = {m_te['auc']:.3f} | sens = {m_te['sensibilidad']:.2f} | esp = {m_te['especificidad']:.2f} | "
            f"AUC CV repetida = {np.mean(aucs):.3f} ± {np.std(aucs):.3f}")

        info = {
            "umbral": umbral,
            "hiperparametros": {k.replace("clf__", ""): (list(v) if isinstance(v, tuple) else v)
                                for k, v in busqueda.best_params_.items()},
            "metricas_prueba": m_te, "metricas_cv": m_cv,
            "auc_cv_media": float(np.mean(aucs)), "auc_cv_desv": float(np.std(aucs)),
            "roc_prueba": curva_roc(y_te, prob_te), "roc_cv": curva_roc(y_tr, prob_oof),
        }

        if nombre == "logistica":
            clf_f = mejor.named_steps["clf"]
            coefs = clf_f.coef_[0]
            filas = [{"variable": v, "etiqueta": ETIQUETAS[v], "coef": float(c), "odds_ratio": float(np.exp(c))}
                     for v, c in zip(VARIABLES_MODELO, coefs)]
            filas.sort(key=lambda r: abs(r["coef"]), reverse=True)
            info["coeficientes"] = filas
            info["intercepto"] = float(clf_f.intercept_[0])
            info["n_variables_activas"] = int((np.abs(coefs) > 1e-9).sum())
        else:
            clf_f = mejor.named_steps["clf"]
            info["arquitectura"] = {
                "entrada": len(VARIABLES_MODELO), "ocultas": list(clf_f.hidden_layer_sizes) if isinstance(clf_f.hidden_layer_sizes, tuple) else [clf_f.hidden_layer_sizes],
                "salida": 1, "activacion": clf_f.activation, "iteraciones": int(clf_f.n_iter_),
            }
            info["curva_perdida"] = [round(float(x), 4) for x in clf_f.loss_curve_[:: max(1, len(clf_f.loss_curve_) // 80)]]
            imp = permutation_importance(mejor, X_te, y_te, scoring="roc_auc", n_repeats=30, random_state=SEMILLA)
            filas = [{"variable": v, "etiqueta": ETIQUETAS[v], "importancia": float(m)}
                     for v, m in zip(VARIABLES_MODELO, imp.importances_mean)]
            filas.sort(key=lambda r: r["importancia"], reverse=True)
            info["importancia"] = filas[:12]

        meta["modelos"][nombre] = info
        modelos_finales[nombre] = mejor

    # Línea base: puntaje clínico del artículo original
    meta["puntaje_estudio"] = {
        "auc": float(roc_auc_score(y, df["puntaje_estudio"])),
        "sensibilidad_corte2": float(((df["puntaje_estudio"] >= 2) & (y == 1)).sum() / (y == 1).sum()),
        "especificidad_corte2": float(((df["puntaje_estudio"] < 2) & (y == 0)).sum() / (y == 0).sum()),
    }

    # Estadísticas descriptivas para la sección de datos
    meta["descriptivos"] = {
        "hipotension": {"no_comp": float(df.loc[y == 0, "hipotension"].mean()), "comp": float(df.loc[y == 1, "hipotension"].mean())},
        "plaquetas_bajas": {"no_comp": float(df.loc[y == 0, "plaquetas_bajas"].mean()), "comp": float(df.loc[y == 1, "plaquetas_bajas"].mean())},
        "pcv_alto": {"no_comp": float(df.loc[y == 0, "pcv_alto"].mean()), "comp": float(df.loc[y == 1, "pcv_alto"].mean())},
        "leucocitos_altos": {"no_comp": float(df.loc[y == 0, "leucocitos_altos"].mean()), "comp": float(df.loc[y == 1, "leucocitos_altos"].mean())},
        "alt_elevada": {"no_comp": float(df.loc[y == 0, "alt_elevada"].mean()), "comp": float(df.loc[y == 1, "alt_elevada"].mean())},
        "vomito": {"no_comp": float(df.loc[y == 0, "vomito"].mean()), "comp": float(df.loc[y == 1, "vomito"].mean())},
        "fiebre_prolongada": {"no_comp": float(df.loc[y == 0, "fiebre_prolongada"].mean()), "comp": float(df.loc[y == 1, "fiebre_prolongada"].mean())},
    }
    meta["rangos"] = {c: [float(df[c].min()), float(df[c].median()), float(df[c].max())]
                      for c in ["duracion_fiebre", "hemoglobina", "pcv", "leuco_min", "leuco_max", "plaquetas", "alt", "creatinina"]}

    for nombre, modelo in modelos_finales.items():
        joblib.dump(modelo, os.path.join(RUTA_MODELOS, f"modelo_{nombre}.joblib"))
    with open(os.path.join(RUTA_MODELOS, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    log("\nModelos y metadatos guardados en /models")
    return modelos_finales, meta


if __name__ == "__main__":
    entrenar_todo()
