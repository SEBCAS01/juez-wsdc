import os
from openai import OpenAI
from swarm import Swarm, Agent

# ==========================================
# 1. DEFINICIÓN DE LOS EXPERTOS (AGENTES)
# ==========================================

# NUEVO AGENTE: Se encarga exclusivamente de resolver el problema de Whisper
agente_diarizador = Agent(
    name="Agente Diarizador",
    instructions="Eres un experto lingüista. Recibirás un bloque de texto crudo de un debate sin separaciones. Tu ÚNICA tarea es leerlo, deducir lógicamente los cambios de turno basándote en la conversación y reescribir todo el texto usando viñetas por orador (Ej: * **Orador 1 (Proposición):** 'texto...'). NO resumas, preserva cada palabra original, solo dale formato de guion teatral.",
    model="gpt-4o"
)

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

# ==========================================
# 2. FUNCIONES DE DELEGACIÓN (HANDOFFS)
# ==========================================
def transferir_a_argumentacion():
    return agente_argumentacion

def transferir_a_estilo():
    return agente_estilo

def transferir_a_juez_principal():
    return juez_principal

agente_argumentacion.functions = [transferir_a_juez_principal]
agente_estilo.functions = [transferir_a_juez_principal]
juez_principal.functions = [transferir_a_argumentacion, transferir_a_estilo]

# ==========================================
# 3. FUNCIÓN MAESTRA: TRANSCRIBIR Y EVALUAR
# ==========================================
def ejecutar_evaluacion_swarm(ruta_audio, ruta_rubrica, api_key):
    os.environ["OPENAI_API_KEY"] = api_key
    openai_client = OpenAI(api_key=api_key)
    swarm_client = Swarm(client=openai_client)
    
    with open(ruta_rubrica, "r", encoding="utf-8") as f:
        texto_rubrica = f.read()
        nombre_archivo_rubrica = os.path.basename(ruta_rubrica)

    # 3.1 Transcribir (Whisper API - Texto Crudo)
    with open(ruta_audio, "rb") as audio_file:
        transcripcion = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    texto_crudo = transcripcion.text

    # 3.2 Fase de Limpieza: Diarización Lógica (Agente Independiente)
    respuesta_diarizador = swarm_client.run(
        agent=agente_diarizador,
        messages=[{"role": "user", "content": f"Por favor diariza lógicamente este texto sin resumirlo:\n{texto_crudo}"}],
        debug=False
    )
    
    texto_diarizado = "⚠️ Error en la diarización."
    for mensaje in reversed(respuesta_diarizador.messages):
        if mensaje.get("role") == "assistant" and mensaje.get("content"):
            texto_diarizado = mensaje["content"]
            break

    # 3.3 Evaluación Multi-Agente (El Jurado)
    prompt_inicial = f"ESTA ES LA RÚBRICA QUE DEBES APLICAR (Archivo: {nombre_archivo_rubrica}):\n{texto_rubrica}\n\nESTE ES EL DEBATE DIARIZADO PREVIAMENTE:\n{texto_diarizado}\n\nPor favor, coordina con tu equipo de expertos, recolecta sus reportes y genera el veredicto final siguiendo ESTRICTAMENTE el formato de markdown que se te pidió."
    
    respuesta_juez = swarm_client.run(
        agent=juez_principal,
        messages=[{"role": "user", "content": prompt_inicial}],
        debug=False 
    )
    
    # 3.4 Red de Seguridad del Juez
    veredicto_final = "⚠️ Error: Los agentes no lograron generar un veredicto en texto."
    for mensaje in reversed(respuesta_juez.messages):
        if mensaje.get("role") == "assistant" and mensaje.get("content"):
            veredicto_final = mensaje["content"]
            break

    # 3.5 Ensamblaje Final del Documento (Inyección Forzada)
    documento_completo = f"""# 📝 Transcripción (Diarización Lógica por IA)
*Nota Arquitectónica: Whisper API no cuenta con diarizador acústico. Para emular el comportamiento de Langflow, el sistema Swarm delegó la tarea a un Agente Lingüista que dedujo los cambios de orador basándose puramente en la inferencia del texto.*

{texto_diarizado}

---

{veredicto_final}
"""
            
    return documento_completo