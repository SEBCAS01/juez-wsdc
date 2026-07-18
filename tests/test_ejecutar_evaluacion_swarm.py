"""
tests/test_ejecutar_evaluacion_swarm.py

Pruebas unitarias para la funcion maestra ejecutar_evaluacion_swarm()
de juez_swarm.py. Se mockean TODAS las dependencias externas
(Deepgram, OpenAI, Swarm, y el analisis TRACE que requiere cargar el
modelo real) para aislar unicamente la logica de orquestacion propia
del proyecto: construccion del prompt, y la "red de seguridad" que
busca el ultimo mensaje de rol assistant recorriendo la conversacion
hacia atras.

Ejecutar con: pytest tests/test_ejecutar_evaluacion_swarm.py -v
"""

import sys
import os
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import juez_swarm


def _mock_deepgram_basico():
    """Devuelve un mock de DeepgramClient que produce una transcripcion simple de 2 hablantes."""
    mock_client_class = MagicMock()
    mock_deepgram = MagicMock()

    palabra1 = MagicMock(word="Hola", speaker=0, punctuated_word="Hola.")
    palabra2 = MagicMock(word="Bien", speaker=1, punctuated_word="Bien.")

    alternativa = MagicMock()
    alternativa.words = [palabra1, palabra2]
    alternativa.transcript = "Hola Bien"

    canal = MagicMock()
    canal.alternatives = [alternativa]

    respuesta = MagicMock()
    respuesta.results.channels = [canal]

    mock_deepgram.listen.prerecorded.v.return_value.transcribe_file.return_value = respuesta
    mock_client_class.return_value = mock_deepgram
    return mock_client_class


# ==========================================
# Red de seguridad: encontrar el ultimo veredicto del juez
# ==========================================

@patch("juez_swarm.formatear_reporte_trace_por_hablante", return_value="Reporte TRACE simulado")
@patch("juez_swarm.analizar_toulmin_por_hablante", return_value={})
@patch("juez_swarm.Swarm")
@patch("juez_swarm.OpenAI")
@patch("juez_swarm.DeepgramClient")
def test_encuentra_veredicto_cuando_es_el_ultimo_mensaje(
    mock_dg_class, mock_openai_class, mock_swarm_class, mock_analizar, mock_formatear
):
    mock_dg_class.side_effect = _mock_deepgram_basico()

    mock_swarm_instance = MagicMock()
    mock_resultado = MagicMock()
    mock_resultado.messages = [
        {"role": "user", "content": "prompt inicial"},
        {"role": "assistant", "content": "VEREDICTO FINAL: Equipo A gana"},
    ]
    mock_swarm_instance.run.return_value = mock_resultado
    mock_swarm_class.return_value = mock_swarm_instance

    with patch("builtins.open", mock_open(read_data="contenido de la rubrica")):
        resultado = juez_swarm.ejecutar_evaluacion_swarm(
            "audio_falso.mp3", "rubrica_falsa.txt", "api_key_openai_falsa", "api_key_deepgram_falsa"
        )

    assert "VEREDICTO FINAL: Equipo A gana" in resultado


@patch("juez_swarm.formatear_reporte_trace_por_hablante", return_value="Reporte TRACE simulado")
@patch("juez_swarm.analizar_toulmin_por_hablante", return_value={})
@patch("juez_swarm.Swarm")
@patch("juez_swarm.OpenAI")
@patch("juez_swarm.DeepgramClient")
def test_encuentra_veredicto_recorriendo_hacia_atras_si_no_es_el_ultimo(
    mock_dg_class, mock_openai_class, mock_swarm_class, mock_analizar, mock_formatear
):
    """
    Caso clave: la conversacion NO termina con el veredicto del juez,
    sino con un mensaje de transferencia de control (rol distinto a
    assistant, o assistant sin contenido). La funcion debe recorrer
    hacia atras y encontrar el ultimo mensaje real del juez.
    """
    mock_dg_class.side_effect = _mock_deepgram_basico()

    mock_swarm_instance = MagicMock()
    mock_resultado = MagicMock()
    mock_resultado.messages = [
        {"role": "user", "content": "prompt inicial"},
        {"role": "assistant", "content": "VEREDICTO REAL DEL JUEZ"},
        {"role": "tool", "content": None},  # mensaje de transferencia sin contenido util
        {"role": "assistant", "content": None},  # ultimo mensaje, pero vacio
    ]
    mock_swarm_instance.run.return_value = mock_resultado
    mock_swarm_class.return_value = mock_swarm_instance

    with patch("builtins.open", mock_open(read_data="contenido de la rubrica")):
        resultado = juez_swarm.ejecutar_evaluacion_swarm(
            "audio_falso.mp3", "rubrica_falsa.txt", "api_key_openai_falsa", "api_key_deepgram_falsa"
        )

    assert "VEREDICTO REAL DEL JUEZ" in resultado


@patch("juez_swarm.formatear_reporte_trace_por_hablante", return_value="Reporte TRACE simulado")
@patch("juez_swarm.analizar_toulmin_por_hablante", return_value={})
@patch("juez_swarm.Swarm")
@patch("juez_swarm.OpenAI")
@patch("juez_swarm.DeepgramClient")
def test_mensaje_de_error_si_no_hay_ningun_veredicto(
    mock_dg_class, mock_openai_class, mock_swarm_class, mock_analizar, mock_formatear
):
    """Si ningun agente produjo contenido, debe devolver el mensaje de error por defecto, sin lanzar excepcion."""
    mock_dg_class.side_effect = _mock_deepgram_basico()

    mock_swarm_instance = MagicMock()
    mock_resultado = MagicMock()
    mock_resultado.messages = [
        {"role": "user", "content": "prompt inicial"},
        {"role": "assistant", "content": None},
    ]
    mock_swarm_instance.run.return_value = mock_resultado
    mock_swarm_class.return_value = mock_swarm_instance

    with patch("builtins.open", mock_open(read_data="contenido de la rubrica")):
        resultado = juez_swarm.ejecutar_evaluacion_swarm(
            "audio_falso.mp3", "rubrica_falsa.txt", "api_key_openai_falsa", "api_key_deepgram_falsa"
        )

    assert "Error" in resultado or "error" in resultado


# ==========================================
# Construccion del prompt e inclusion de contexto
# ==========================================

@patch("juez_swarm.formatear_reporte_trace_por_hablante", return_value="REPORTE_TRACE_MARCADOR")
@patch("juez_swarm.analizar_toulmin_por_hablante", return_value={})
@patch("juez_swarm.Swarm")
@patch("juez_swarm.OpenAI")
@patch("juez_swarm.DeepgramClient")
def test_prompt_incluye_rubrica_transcripcion_y_reporte_trace(
    mock_dg_class, mock_openai_class, mock_swarm_class, mock_analizar, mock_formatear
):
    mock_dg_class.side_effect = _mock_deepgram_basico()

    mock_swarm_instance = MagicMock()
    mock_resultado = MagicMock()
    mock_resultado.messages = [{"role": "assistant", "content": "veredicto"}]
    mock_swarm_instance.run.return_value = mock_resultado
    mock_swarm_class.return_value = mock_swarm_instance

    with patch("builtins.open", mock_open(read_data="RUBRICA_MARCADOR_UNICO")):
        juez_swarm.ejecutar_evaluacion_swarm(
            "audio_falso.mp3", "rubrica_falsa.txt", "api_key_openai_falsa", "api_key_deepgram_falsa"
        )

    prompt_enviado = mock_swarm_instance.run.call_args.kwargs["messages"][0]["content"]
    assert "RUBRICA_MARCADOR_UNICO" in prompt_enviado
    assert "REPORTE_TRACE_MARCADOR" in prompt_enviado
