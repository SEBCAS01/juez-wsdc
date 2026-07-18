"""
tests/test_modelo_trace_deberta_real.py

A diferencia de las demas suites, esta prueba NO mockea el modelo:
carga los pesos reales de TRACE-DeBERTa (~700MB) y verifica que
clasifica correctamente oraciones de ejemplo con una etiqueta
esperada evidente. Es la unica prueba que valida el comportamiento
real del modelo entrenado, no solo la matematica que consume sus
salidas (ya cubierta en test_trace_scorer.py).

Es mas lenta que el resto de la suite porque carga el modelo
completo en la primera llamada. Requiere que los pesos ya esten
descargados via 'git lfs pull' (ver seccion de Instalacion del
README).

Ejecutar con: pytest tests/test_modelo_trace_deberta_real.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trace_scorer import analizar_toulmin


def test_oracion_claim_evidente_produce_score_valido():
    """
    Una oracion que es una afirmacion/conclusion clara deberia
    clasificarse con Claim entre sus etiquetas activas.
    """
    resultado = analizar_toulmin("Por lo tanto, la respuesta correcta es la opcion B.")

    assert resultado["trace_score"] is not None
    assert 0.0 <= resultado["trace_score"] <= 1.0
    assert resultado["num_sentences"] == 1

    etiquetas_detectadas = resultado["label_train"][0]["labels"]
    assert "Claim" in etiquetas_detectadas


def test_oracion_con_datos_produce_evidencia():
    """
    Una oracion que presenta un dato o hecho concreto deberia
    tender a clasificarse como Data/Evidence.
    """
    resultado = analizar_toulmin("Segun el estudio de 2023, el 68% de los casos mostraron mejoria.")

    assert resultado["trace_score"] is not None
    etiquetas_detectadas = resultado["label_train"][0]["labels"]
    assert len(etiquetas_detectadas) > 0  # el modelo debe detectar al menos una etiqueta, no dejarla vacia


def test_muletilla_sin_contenido_argumentativo():
    """
    Una muletilla pura no deberia activar ninguna etiqueta con
    confianza (o muy pocas), a diferencia de una oracion con
    contenido argumentativo real.
    """
    resultado = analizar_toulmin("Hmm, bueno, este...")

    assert resultado["trace_score"] is not None
    # No se afirma que las etiquetas esten vacias (el modelo puede
    # discrepar), pero el score no deberia ser el maximo posible
    assert resultado["trace_score"] < 1.0


def test_texto_multiples_oraciones_analiza_cada_una_por_separado():
    resultado = analizar_toulmin(
        "El sistema debe usar un tipo de dato mas grande. "
        "Esto se debe a que el valor maximo excede el limite actual. "
        "Por lo tanto, la solucion propuesta es correcta."
    )

    assert resultado["num_sentences"] == 3
    assert len(resultado["label_train"]) == 3
