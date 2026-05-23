import os
from openai import OpenAI
from swarm import Swarm, Agent

# ==========================================
# 1. DEFINICIÓN DE LOS EXPERTOS (AGENTES)
# ==========================================

agente_argumentacion = Agent(
    name="Experto en Argumentación",
    instructions="Eres un juez WSDC estricto. Evalúa únicamente la lógica, solidez y refutación de los argumentos del debate. Haz un resumen de tus hallazgos y pásale la batuta al Juez Principal.",
    model="gpt-4o-mini"
)

agente_estilo = Agent(
    name="Experto en Estilo",
    instructions="Eres un juez WSDC. Evalúa únicamente el lenguaje corporal (si aplica), tono de voz, claridad y persuasión. Haz un resumen de tus hallazgos y pásale la batuta al Juez Principal.",
    model="gpt-4o-mini"
)

juez_principal = Agent(
    name="Juez Principal WSDC",
    instructions="""Eres el Presidente del Jurado WSDC. Recibirás los análisis de los expertos en Argumentación y Estilo. Tu trabajo es unirlos, aplicar la rúbrica oficial y redactar el Veredicto Final estructurado de forma idéntica al formato solicitado.

    REGLA DE ORO DE FORMATO: Tu respuesta debe ser un texto en Markdown siguiendo EXACTAMENTE esta estructura y títulos. NO cambies el orden ni agregues saludos.

    # 🏆 Veredicto Oficial del Debate
    * **Tema del debate:** [Identifica el tema]
    * **Equipo Ganador:** [Nombre del equipo]
    * **Justificación:** [Resumen de por qué ganó en 3-4 líneas]

    ## 📊 Desempeño por Equipos

    ### Equipo A: [Postura]
    #### Orador: [Nombre o ID]
    * **Cita textual:** "[Extrae una cita representativa]"
    * **Argumento y Refutación:** [Análisis detallado de su participación]
    * **Contenido:** [Nota]/40
    * **Estilo:** [Nota]/40
    * **Estrategia:** [Nota]/20
    * **Justificación:** [Explicación de las notas]

    *(Repite este bloque para cada orador del Equipo A y luego para los del Equipo B)*

    ---

    --- ANÁLISIS DE POSTURAS ---
    * Equipo A [Postura]: [Resumen de 2 líneas]
    * Equipo B [Postura]: [Resumen de 2 líneas]

    --- TABLA DE PUNTAJES ---
    Equipo A: Contenido (X/40) | Estilo (X/40) | Estrategia (X/20) = TOTAL: X/100
    Equipo B: Contenido (X/40) | Estilo (X/40) | Estrategia (X/20) = TOTAL: X/100

    --- VEREDICTO ---
    GANADOR: [Equipo]
    MARGEN: [X] pts ([Cerrado/Claro/Dominante])
    RAZÓN PRINCIPAL: [1 o 2 líneas directas sobre la victoria]
    """,
    model="gpt-4o-mini"
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

# Les damos las instrucciones de a quién pueden "pasarle el micrófono"
agente_argumentacion.functions = [transferir_a_juez_principal]
agente_estilo.functions = [transferir_a_juez_principal]
juez_principal.functions = [transferir_a_argumentacion, transferir_a_estilo]

# ==========================================
# 3. FUNCIÓN MAESTRA: TRANSCRIBIR Y EVALUAR
# ==========================================
def ejecutar_evaluacion_swarm(ruta_audio, ruta_rubrica, api_key):
    # 3.1 Configurar clientes
    os.environ["OPENAI_API_KEY"] = api_key
    openai_client = OpenAI(api_key=api_key)
    swarm_client = Swarm(client=openai_client)
    
    # 3.2 Leer el texto de la rúbrica seleccionada
    with open(ruta_rubrica, "r", encoding="utf-8") as f:
        texto_rubrica = f.read()

    # 3.3 Transcribir el audio súper rápido con Whisper API
    with open(ruta_audio, "rb") as audio_file:
        transcripcion = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    texto_debate = transcripcion.text

    # 3.4 Iniciar el debate de los agentes
    prompt_inicial = f"Aplica esta rúbrica:\n{texto_rubrica}\n\nAl siguiente debate:\n{texto_debate}\n\nPor favor, coordina con tu equipo de expertos y genera el veredicto final."
    
    respuesta = swarm_client.run(
        agent=juez_principal,
        messages=[{"role": "user", "content": prompt_inicial}],
        debug=False # Ponlo en True si quieres ver en la terminal cómo hablan entre ellos
    )
    
    # Devolvemos el último mensaje (El veredicto del juez principal)
    return respuesta.messages[-1]["content"]