import os
from openai import OpenAI
from swarm import Swarm, Agent
from deepgram import DeepgramClient, PrerecordedOptions, FileSource

from trace_scorer import analizar_toulmin_por_hablante, formatear_reporte_trace_por_hablante

# ==========================================
# 1. DEFINICIÓN DE LOS EXPERTOS (AGENTES)
# ==========================================

agente_argumentacion = Agent(
    name="Experto en Argumentación",
    instructions="""Eres un juez WSDC estricto. Evalúa la lógica, solidez y refutación de los argumentos.
    Recibirás un análisis estructural TRACE (basado en el modelo de Toulmin) de la transcripción,
    incluyendo un TRACE Score y el detalle de qué elementos argumentativos (Claim, Data/Evidence,
    Warrant, Backing, Qualifier, Rebuttal, Monitoring, Evaluation) aparecen en cada oración.
    Usa ese análisis como evidencia objetiva: cita transiciones lógicas sólidas o fallas de coherencia
    detectadas cuando sea relevante para tu evaluación.
    Genera un 'REPORTE DE ARGUMENTACIÓN' detallado y pásale la batuta al Juez Principal.""",
    model="gpt-4o"
)

agente_estilo = Agent(
    name="Experto en Estilo",
    instructions="Eres un juez WSDC. Evalúa la claridad, estructura y persuasión del discurso. Genera un 'REPORTE DE ESTILO' detallado y pásale la batuta al Juez Principal.",
    model="gpt-4o"
)

juez_principal = Agent(
    name="Juez Principal WSDC",
    instructions="""Eres el Presidente del Jurado WSDC. Tu deber es orquestar a tu equipo, aplicar la rúbrica y redactar el documento final mostrando TOTAL TRANSPARENCIA.

    REGLA ESTRICTA DE FORMATO: Es obligatorio que tu respuesta final NO omita ninguna de estas secciones:

    # 🔍 Auditoría del Enjambre (Transparencia IA)
    * **Rúbrica Confirmada:** [Menciona aquí qué rúbrica estás usando]

    ### 🧩 Reporte Interno: Análisis TRACE (Toulmin)
    [Resume el TRACE Score recibido, sus componentes (State Validity / Transition Coherence),
    y explica brevemente cómo esta evidencia estructural influyó en tu evaluación de Argumentación]

    ### 🧠 Reporte Interno: Experto en Argumentación
    [Pega el análisis del Experto en Argumentación]

    ### 🎭 Reporte Interno: Experto en Estilo
    [Pega el análisis del Experto en Estilo]

    ---

    # 🏆 Veredicto Oficial del Debate
    * **Tema del debate:** [Identifica el tema]
    * **Equipo Ganador:** [Nombre del equipo]
    * **Justificación:** [Resumen de por qué ganó]

    ## 📊 Desempeño por Equipos

    ### Equipo A: [Postura]
    #### Orador: [Nombre o ID]
    * **Cita textual:** "[Extrae una cita]"
    * **Argumento y Refutación:** [Análisis detallado]
    * **Contenido:** [Nota]/40
    * **Estilo:** [Nota]/40
    * **Estrategia:** [Nota]/20
    * **Justificación:** [Explicación]
    *(Repite la evaluación para cada orador distinto)*

    ---
    --- ANÁLISIS DE POSTURAS ---
    * Equipo A: [Resumen]
    * Equipo B: [Resumen]

    --- TABLA DE PUNTAJES ---
    Equipo A: Contenido (X/40) | Estilo (X/40) | Estrategia (X/20) = TOTAL: X/100
    Equipo B: Contenido (X/40) | Estilo (X/40) | Estrategia (X/20) = TOTAL: X/100

    --- VEREDICTO ---
    GANADOR: [Equipo]
    MARGEN: [X] pts
    RAZÓN PRINCIPAL: [Justificación corta]
    """,
    model="gpt-4o"
)

# ==========================================
# 2. DELEGACIONES (FUNCIONES CON NOMBRES VÁLIDOS PARA OPENAI)
# ==========================================
def transferir_a_juez_principal():
    return juez_principal

def transferir_a_argumentacion():
    return agente_argumentacion

def transferir_a_estilo():
    return agente_estilo

agente_argumentacion.functions = [transferir_a_juez_principal]
agente_estilo.functions = [transferir_a_juez_principal]
juez_principal.functions = [transferir_a_argumentacion, transferir_a_estilo]

# ==========================================
# 3. TRANSCRIPCIÓN + DIARIZACIÓN CON DEEPGRAM
# ==========================================
def _transcribir_con_deepgram(ruta_audio, deepgram_api_key):
    """
    Transcribe y diariza el audio con Deepgram, devolviendo:
    - texto_diarizado: transcripción con marcadores **SPEAKER_X:** por turno, en orden cronológico
    - texto_por_hablante: dict {"SPEAKER_0": "texto completo...", "SPEAKER_1": "texto completo...", ...}
    """
    deepgram = DeepgramClient(deepgram_api_key)

    with open(ruta_audio, "rb") as f:
        buffer_data = f.read()

    payload: FileSource = {"buffer": buffer_data}

    options = PrerecordedOptions(
        model="nova-2",
        smart_format=True,
        diarize=True,
        language="es",  # ajusta a "en" si tus debates son en inglés
    )

    respuesta = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)

    canal = respuesta.results.channels[0]
    alternativa = canal.alternatives[0]

    # La diarización vive en las palabras individuales, no en el transcript plano.
    # Reconstruimos turnos agrupando palabras consecutivas del mismo hablante,
    # en el mismo orden en que Deepgram las devuelve (orden cronológico).
    palabras = alternativa.words

    if not palabras:
        # Fallback: si por algún motivo no hay word-level data, usamos el texto plano
        return alternativa.transcript, {}

    turnos = []  # lista de (speaker_id, [palabras...])
    speaker_actual = None
    buffer_palabras = []

    for palabra in palabras:
        speaker_id = f"SPEAKER_{palabra.speaker}"
        if speaker_id != speaker_actual:
            if buffer_palabras:
                turnos.append((speaker_actual, buffer_palabras))
            speaker_actual = speaker_id
            buffer_palabras = []
        buffer_palabras.append(palabra.punctuated_word if hasattr(palabra, "punctuated_word") and palabra.punctuated_word else palabra.word)

    if buffer_palabras:
        turnos.append((speaker_actual, buffer_palabras))

    # Texto diarizado en formato legible, igual al patrón que usa tu componente
    # de Langflow: **SPEAKER_X:** "texto del turno"
    lineas_diarizadas = []
    texto_por_hablante = {}

    for speaker_id, lista_palabras in turnos:
        texto_turno = " ".join(lista_palabras)
        lineas_diarizadas.append(f'**{speaker_id}:** "{texto_turno}"')
        texto_por_hablante.setdefault(speaker_id, [])
        texto_por_hablante[speaker_id].append(texto_turno)

    texto_diarizado = "\n\n".join(lineas_diarizadas)
    texto_por_hablante = {
        speaker: " ".join(turnos_texto) for speaker, turnos_texto in texto_por_hablante.items()
    }

    return texto_diarizado, texto_por_hablante


# ==========================================
# 4. FUNCIÓN MAESTRA
# ==========================================
def ejecutar_evaluacion_swarm(ruta_audio, ruta_rubrica, api_key, deepgram_api_key):
    os.environ["OPENAI_API_KEY"] = api_key
    client = OpenAI(api_key=api_key)
    swarm = Swarm(client=client)

    # 1. Transcribir y diarizar con Deepgram
    texto_debate, texto_por_hablante = _transcribir_con_deepgram(ruta_audio, deepgram_api_key)

    # 2. Leer rúbrica
    with open(ruta_rubrica, "r", encoding="utf-8") as f:
        texto_rubrica = f.read()

    # 3. Ejecutar análisis TRACE (Toulmin) por hablante
    resultado_trace_por_hablante = analizar_toulmin_por_hablante(texto_por_hablante)
    reporte_trace_md = formatear_reporte_trace_por_hablante(resultado_trace_por_hablante)

    # 4. Ejecutar Swarm, incluyendo el análisis TRACE como contexto adicional
    prompt = f"""Rúbrica:
{texto_rubrica}

Transcripción (diarizada por hablante):
{texto_debate}

Análisis Estructural TRACE (Toulmin) por hablante:
{reporte_trace_md}

Genera el reporte, asegurándote de incluir la sección de Auditoría TRACE tal como lo indican tus instrucciones."""

    res = swarm.run(
        agent=juez_principal,
        messages=[{"role": "user", "content": prompt}]
    )

    # Red de seguridad
    veredicto = "⚠️ Error: No se generó un veredicto."
    for m in reversed(res.messages):
        if m.get("role") == "assistant" and m.get("content"):
            veredicto = m["content"]
            break

    # 5. Sección TRACE independiente y garantizada en el output final
    #    (no depende de que el modelo la reproduzca correctamente)
    seccion_trace = f"""
# 🧬 Análisis TRACE (Toulmin) por Hablante — Reporte Técnico Independiente

{reporte_trace_md}

---
"""

    return f"# Transcripción (Deepgram, diarizada)\n{texto_debate}\n\n---\n\n{seccion_trace}\n{veredicto}"
