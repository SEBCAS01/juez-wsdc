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
    instructions="Eres el Presidente del Jurado. Recibirás los análisis de los expertos en Argumentación y Estilo. Tu trabajo es unirlos, aplicar la rúbrica oficial y redactar el Veredicto Final en un texto estructurado y profesional, sin mencionar que consultaste a otros agentes.",
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