"""
tests/test_juez_swarm.py

Pruebas unitarias para juez_swarm.py, enfocadas en la logica propia
del proyecto (reconstruccion de turnos de hablante a partir de la
lista plana de palabras que devuelve Deepgram), no en el SDK de
Deepgram en si. La llamada real a la API se reemplaza (mock) por un
objeto falso con la misma forma que la respuesta real.

Ejecutar con: pytest tests/test_juez_swarm.py -v
"""

import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import juez_swarm


class PalabraFalsa:
    """Simula un objeto 'word' de la respuesta de Deepgram."""
    def __init__(self, word, speaker, punctuated_word=None):
        self.word = word
        self.speaker = speaker
        self.punctuated_word = punctuated_word


def _construir_respuesta_falsa(lista_palabras):
    """
    Arma un objeto falso con la misma forma que
    respuesta.results.channels[0].alternatives[0].words
    """
    alternativa = MagicMock()
    alternativa.words = lista_palabras
    alternativa.transcript = " ".join(p.word for p in lista_palabras)

    canal = MagicMock()
    canal.alternatives = [alternativa]

    respuesta = MagicMock()
    respuesta.results.channels = [canal]
    return respuesta


# ==========================================
# Reconstruccion de turnos por hablante
# ==========================================

@patch("juez_swarm.DeepgramClient")
def test_agrupa_palabras_consecutivas_del_mismo_hablante(mock_client_class):
    palabras = [
        PalabraFalsa("Hola", 0),
        PalabraFalsa("mundo", 0),
        PalabraFalsa("Que", 1),
        PalabraFalsa("tal", 1),
    ]
    mock_deepgram = MagicMock()
    mock_deepgram.listen.prerecorded.v.return_value.transcribe_file.return_value = _construir_respuesta_falsa(palabras)
    mock_client_class.return_value = mock_deepgram

    with patch("builtins.open", MagicMock()):
        texto_diarizado, texto_por_hablante = juez_swarm._transcribir_con_deepgram("audio_falso.mp3", "key_falsa")

    assert "SPEAKER_0" in texto_por_hablante
    assert "SPEAKER_1" in texto_por_hablante
    assert texto_por_hablante["SPEAKER_0"] == "Hola mundo"
    assert texto_por_hablante["SPEAKER_1"] == "Que tal"


@patch("juez_swarm.DeepgramClient")
def test_corta_turno_cuando_cambia_el_hablante_y_vuelve(mock_client_class):
    # SPEAKER_0 habla, luego SPEAKER_1, luego SPEAKER_0 de nuevo (interrupcion)
    palabras = [
        PalabraFalsa("Primero", 0),
        PalabraFalsa("interrumpo", 1),
        PalabraFalsa("continuo", 0),
    ]
    mock_deepgram = MagicMock()
    mock_deepgram.listen.prerecorded.v.return_value.transcribe_file.return_value = _construir_respuesta_falsa(palabras)
    mock_client_class.return_value = mock_deepgram

    with patch("builtins.open", MagicMock()):
        texto_diarizado, texto_por_hablante = juez_swarm._transcribir_con_deepgram("audio_falso.mp3", "key_falsa")

    # SPEAKER_0 debe tener DOS turnos separados fusionados por el join final:
    # "Primero" y "continuo" -> "Primero continuo" (se concatenan, no se mezclan con SPEAKER_1)
    assert texto_por_hablante["SPEAKER_0"] == "Primero continuo"
    assert texto_por_hablante["SPEAKER_1"] == "interrumpo"

    # El texto diarizado (para mostrar en pantalla) SI debe reflejar el orden cronologico real,
    # con el turno de SPEAKER_1 en medio
    assert texto_diarizado.index("SPEAKER_0") < texto_diarizado.index("SPEAKER_1")


@patch("juez_swarm.DeepgramClient")
def test_usa_punctuated_word_si_esta_disponible(mock_client_class):
    palabras = [
        PalabraFalsa("hola", 0, punctuated_word="Hola,"),
        PalabraFalsa("mundo", 0, punctuated_word="mundo."),
    ]
    mock_deepgram = MagicMock()
    mock_deepgram.listen.prerecorded.v.return_value.transcribe_file.return_value = _construir_respuesta_falsa(palabras)
    mock_client_class.return_value = mock_deepgram

    with patch("builtins.open", MagicMock()):
        texto_diarizado, texto_por_hablante = juez_swarm._transcribir_con_deepgram("audio_falso.mp3", "key_falsa")

    # Debe preferir la version puntuada, no la palabra cruda
    assert texto_por_hablante["SPEAKER_0"] == "Hola, mundo."


@patch("juez_swarm.DeepgramClient")
def test_sin_palabras_devuelve_texto_plano_de_fallback(mock_client_class):
    respuesta_vacia = _construir_respuesta_falsa([])
    mock_deepgram = MagicMock()
    mock_deepgram.listen.prerecorded.v.return_value.transcribe_file.return_value = respuesta_vacia
    mock_client_class.return_value = mock_deepgram

    with patch("builtins.open", MagicMock()):
        texto_diarizado, texto_por_hablante = juez_swarm._transcribir_con_deepgram("audio_falso.mp3", "key_falsa")

    # Sin palabras, no debe lanzar excepcion; el diccionario de hablantes queda vacio
    assert texto_por_hablante == {}
