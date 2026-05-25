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

# ==========================================
# 2. FUNCIONES DE DELEGACIÓN (HANDOFFS)
# ==========================================
def transferir_a_argumentacion(): return agente_argumentacion
def transferir_a_estilo(): return agente_estilo
def transferir_a_juez_principal(): return juez_principal

agente_argumentacion.functions = [transferir_a_juez_principal]
agente_estilo.functions = [transferir_a_juez_principal]
juez_principal.functions = [transferir_a_argumentacion, transferir_a_estilo]

# ==========================================
# 3. FUNCIÓN MAESTRA (SISTEMA HÍBRIDO)
# ==========================================
def ejecutar_evaluacion_swarm_con_texto(texto_diarizado, texto_rubrica, api_key):
    os.environ["OPENAI_API_KEY"] = api_key
    openai_client = OpenAI(api_key=api_key)
    swarm_client = Swarm(client=openai_client)

    prompt_inicial = f"ESTA ES LA RÚBRICA QUE DEBES APLICAR:\n{texto_rubrica}\n\nESTE ES EL DEBATE YA DIARIZADO ACÚSTICAMENTE:\n{texto_diarizado}\n\nPor favor, coordina con tu equipo de expertos, recolecta sus reportes y genera el veredicto final siguiendo ESTRICTAMENTE el formato de markdown que se te pidió."
    
    respuesta_juez = swarm_client.run(
        agent=juez_principal,
        messages=[{"role": "user", "content": prompt_inicial}],
        debug=False 
    )
    
    veredicto_final = "⚠️ Error: Los agentes no lograron generar un veredicto en texto."
    for mensaje in reversed(respuesta_juez.messages):
        if mensaje.get("role") == "assistant" and mensaje.get("content"):
            veredicto_final = mensaje["content"]
            break

    documento_completo = f"""# 📝 Transcripción Profesional (Diarización Acústica)
*Nota Arquitectónica: Para emular la precisión humana y evitar los errores lineales de Whisper, este sistema opera de forma Híbrida. La diarización acústica de oradores fue ejecutada por el nodo especializado de Langflow, y el análisis del debate fue delegado al Enjambre de Inteligencia Artificial (Swarm).*

> {texto_diarizado}

---

{veredicto_final}
"""
    return documento_completo
