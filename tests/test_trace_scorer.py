"""
tests/test_trace_scorer.py

Pruebas unitarias para la lógica de cálculo de TRACE (trace_scorer.py).
No dependen del modelo TRACE-DeBERTa real ni de spaCy: las funciones
de bajo nivel (binarize_predictions, labels_to_states,
calculate_state_validity, calculate_transition_coherence,
calculate_trace_from_labels) son pura lógica determinista, así que se
prueban directamente con datos de entrada construidos a mano.

Ejecutar con: pytest tests/test_trace_scorer.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, "/root/juez-wsdc/trace-module/eval")

from calculate import (
    binarize_predictions,
    labels_to_states,
    calculate_state_validity,
    calculate_transition_coherence,
    calculate_trace_from_labels,
    ALLOWED_STATES,
)


# ==========================================
# binarize_predictions
# ==========================================

def test_binarize_predictions_umbral_basico():
    entrada = {"Claim": 0.8, "Warrant": 0.3, "Evaluation": 0.5}
    resultado = binarize_predictions(entrada)
    assert resultado == {"Claim": 1, "Warrant": 0, "Evaluation": 1}  # 0.5 pasa el umbral (>=)


def test_binarize_predictions_todo_cero():
    entrada = {"Claim": 0.1, "Warrant": 0.2}
    resultado = binarize_predictions(entrada)
    assert resultado == {"Claim": 0, "Warrant": 0}


def test_binarize_predictions_todo_uno():
    entrada = {"Claim": 0.99, "Warrant": 0.51}
    resultado = binarize_predictions(entrada)
    assert resultado == {"Claim": 1, "Warrant": 1}


# ==========================================
# labels_to_states
# ==========================================

def test_labels_to_states_orden_alfabetico():
    labels = [{"Warrant": 1, "Claim": 1, "Backing": 0}]
    estados = labels_to_states(labels)
    assert estados == ["Claim+Warrant"]  # alfabético, no orden de inserción


def test_labels_to_states_empty():
    labels = [{"Claim": 0, "Warrant": 0}]
    estados = labels_to_states(labels)
    assert estados == ["EMPTY"]


def test_labels_to_states_lista_vacia():
    assert labels_to_states([]) == []


# ==========================================
# calculate_state_validity
# ==========================================

def test_state_validity_estado_permitido_da_uno():
    estados = ["Claim"]
    assert calculate_state_validity(estados) == 1.0


def test_state_validity_estado_no_permitido_usa_jaccard():
    # "Qualifier" no está en ALLOWED_STATES; debe calcular Jaccard parcial
    estados = ["Qualifier"]
    resultado = calculate_state_validity(estados)
    assert 0.0 <= resultado < 1.0


def test_state_validity_lista_vacia_da_cero():
    assert calculate_state_validity([]) == 0.0


def test_state_validity_promedia_correctamente():
    # Una oración válida (1.0) + una oración EMPTY (0.0, no está en ALLOWED_STATES)
    estados = ["Claim", "EMPTY"]
    resultado = calculate_state_validity(estados)
    assert resultado == 0.5  # promedio exacto de 1.0 y 0.0


# ==========================================
# calculate_transition_coherence
# ==========================================

def test_transition_coherence_buena_transicion():
    estados = ["Data/Evidence", "Claim"]  # transición conocida como GOOD
    resultado = calculate_transition_coherence(estados)
    assert resultado == 1.0  # única transición, y es buena -> (1-0)/1 = 1.0


def test_transition_coherence_mala_transicion():
    estados = ["Monitoring", "Qualifier"]  # transición conocida como BAD
    resultado = calculate_transition_coherence(estados)
    assert resultado == -1.0  # única transición, y es mala -> (0-1)/1 = -1.0


def test_transition_coherence_menos_de_dos_estados():
    assert calculate_transition_coherence(["Claim"]) == 0.0
    assert calculate_transition_coherence([]) == 0.0


def test_transition_coherence_filtra_empty():
    # El EMPTY del medio debe ignorarse; la transición real es Data/Evidence -> Claim
    estados = ["Data/Evidence", "EMPTY", "Claim"]
    resultado = calculate_transition_coherence(estados)
    assert resultado == 1.0


# ==========================================
# calculate_trace_from_labels (integración de las fórmulas)
# ==========================================

def test_trace_score_combina_state_validity_y_transition_coherence():
    labels = [
        {"Data/Evidence": 1},
        {"Claim": 1},
    ]
    resultado = calculate_trace_from_labels(labels, alpha=0.7)

    # Cálculo esperado a mano:
    # state_validity: ambos estados están en ALLOWED_STATES -> 1.0
    # transition_coherence: Data/Evidence -> Claim es GOOD -> 1.0, normalizado a 1.0
    # trace = 0.7 * 1.0 + 0.3 * 1.0 = 1.0
    assert abs(resultado - 1.0) < 1e-9


def test_trace_score_lista_vacia_da_cero():
    assert calculate_trace_from_labels([]) == 0.0


def test_trace_score_rango_valido():
    labels = [
        {"Monitoring": 1},
        {"Qualifier": 1},
        {"Qualifier": 1},
    ]
    resultado = calculate_trace_from_labels(labels)
    assert 0.0 <= resultado <= 1.0  # el score final siempre debe quedar en [0,1]
