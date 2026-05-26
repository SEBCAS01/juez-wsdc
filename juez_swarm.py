import os
from openai import OpenAI
from swarm import Swarm, Agent

# ==========================================
# 1. DEFINICIÓN DE LOS EXPERTOS (AGENTES)
# ==========================================

agente_argumentacion = Agent(
    name="Experto en Argumentación",
    instructions="Eres un juez WSDC estricto. Evalúa la lógica, solidez y refutación de los argumentos. Genera un 'REPORTE DE ARGUMENTACIÓN' detallado y pásale la batuta al Juez Principal.",
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

# DELEGACIONES
agente_argumentacion.functions = [lambda: juez_principal]
agente_estilo.functions = [lambda: juez_principal]
juez_principal.functions = [lambda: agente_argumentacion, lambda: agente_estilo]

# FUNCIÓN MAESTRA (LA QUE ORIGINALMENTE TENÍAS)
def ejecutar_evaluacion_swarm(ruta_audio, ruta_rubrica, api_key):
    os.environ["OPENAI_API_KEY"] = api_key
    client = OpenAI(api_key=api_key)
    swarm = Swarm(client=client)
    
    # 1. Transcribir con Whisper
    with open(ruta_audio, "rb") as f:
        transcripcion = client.audio.transcriptions.create(model="whisper-1", file=f)
    texto_debate = transcripcion.text
    
    # 2. Leer rúbrica
    with open(ruta_rubrica, "r", encoding="utf-8") as f:
        texto_rubrica = f.read()
    
    # 3. Ejecutar Swarm
    prompt = f"Rúbrica:\n{texto_rubrica}\n\nTranscripción:\n{texto_debate}\n\nGenera el reporte."
    res = swarm.run(agent=juez_principal, messages=[{"role": "user", "content": prompt}])
    
    veredicto = res.messages[-1]["content"]
    
    return f"# Transcripción (Whisper API)\n{texto_debate}\n\n---\n\n{veredicto}"
