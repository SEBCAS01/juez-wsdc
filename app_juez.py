import streamlit as st
import requests
import os
import uuid
from fpdf import FPDF
# IMPORTANTE: Volvemos a importar la función original, no la "con_texto"
from juez_swarm import ejecutar_evaluacion_swarm

# ==========================================
# 1. CONFIGURACIÓN VISUAL Y BARRA LATERAL
# ==========================================
st.set_page_config(page_title="Juez Automático WSDC", page_icon="⚖️", layout="centered")

st.sidebar.subheader("🔌 Conexión al Cerebro (IA)")
url_langflow = st.sidebar.text_input(
    "Pega aquí tu URL de Ngrok (Solo para arquitecturas locales):", 
    value="https://auction-hurried-passover.ngrok-free.dev" 
)

# ==========================================
# GESTIÓN DE SECRETOS (API KEYS INVISIBLES)
# ==========================================
try:
    api_key_openai = st.secrets.get("OPENAI_API_KEY", None)
    if not api_key_openai:
        raise ValueError("Llave vacía")
except Exception:
    api_key_openai = None
    st.sidebar.warning("⚠️ Modo Local sin API Key configurada. Swarm no funcionará.")

# ==========================================
# 2. CONFIGURACIÓN DE LLAVES Y RUTAS
# ==========================================
LANGFLOW_API_KEY = "sk-MKqzedV2Z3UnKzV4yOnFLaXiynsczt-_WuDZQKRkjCs" 
ARCHIVO_RUBRICA_EQUIPOS = "RUBRICA_EQUIPOS.txt"
ARCHIVO_RUBRICA_1VS1 = "RUBRICA_1V1.txt"

ARQUITECTURAS = {
    "Arquitectura Lineal (Chain)": {
        "flow_id": "9dd70430-ef75-4174-a93e-1976c7b6b692",
        "diarizador_id": "CustomComponent-5mTe3",
        "readfile_rubrica_id": "Read File-File-xUxcw"
    },
    "Arquitectura de Árbol (Tree)": {
        "flow_id": "0ca5391e-827a-49a5-aca1-e65768f7829f",
        "diarizador_id": "DiarizadorWSDC-pLb4O",
        "readfile_rubrica_id": "Read File-File-PdtnV"
    },
    "Arquitectura de Grafos (Graph)": {
        "flow_id": "2dd01fd2-65bd-4039-8007-7ae77d6c1f8c",
        "diarizador_id": "DiarizadorWSDC-pLb4O",
        "readfile_rubrica_id": "Read File-File-PdtnV"
    }
}

# ==========================================
# 3. INICIALIZACIÓN DE LA MEMORIA DE SESIÓN
# ==========================================
if "resultado_texto" not in st.session_state:
    st.session_state.resultado_texto = None
if "evaluado" not in st.session_state:
    st.session_state.evaluado = False
if "arquitectura_usada" not in st.session_state:
    st.session_state.arquitectura_usada = ""
if "rubrica_usada" not in st.session_state:
    st.session_state.rubrica_usada = ""

# ==========================================
# 4. FUNCIÓN MAESTRA PARA GENERAR PDF
# ==========================================
def generar_pdf_veredictos(texto, arquitectura, rubrica):
    texto_limpio = texto.replace("**", "").replace("###", "")
    texto_safe = texto_limpio.encode('latin-1', 'replace').decode('latin-1')
    arq_safe = arquitectura.encode('latin-1', 'replace').decode('latin-1')
    rub_safe = rubrica.encode('latin-1', 'replace').decode('latin-1')
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_fill_color(31, 41, 55) 
    pdf.rect(0, 0, 210, 38, 'F')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_y(12)
    pdf.cell(0, 8, "VEREDICTO OFICIAL DE EVALUACION", ln=True, align="C")
    
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(209, 213, 219)
    pdf.cell(0, 6, "Plataforma de IA para Debates WSDC", ln=True, align="C")
    
    pdf.set_y(45)
    pdf.set_fill_color(243, 244, 246)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(75, 85, 99)
    pdf.cell(0, 10, f"  Cerebro: {arq_safe}   |   Formato: {rub_safe}", ln=True, fill=True)
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(17, 24, 39)
    pdf.multi_cell(0, 6, texto_safe)
    
    return pdf.output()

# ==========================================
# 5. INTERFAZ PRINCIPAL
# ==========================================
st.title("⚖️ Juez Automático de Debates WSDC")
st.markdown("Plataforma de evaluación automática. Selecciona la arquitectura de IA, el formato del debate y sube la grabación para obtener el veredicto.")

st.subheader("⚙️ Parámetros de Evaluación")
col1, col2 = st.columns(2)

with col1:
    opciones_menu = list(ARQUITECTURAS.keys()) + ["Sistema Multi-Agente (Swarm)"]
    arquitectura_elegida = st.selectbox(
        "🧠 Cerebro (Arquitectura):",
        options=opciones_menu
    )

with col2:
    tipo_rubrica = st.selectbox(
        "📋 Formato de Rúbrica:",
        options=["Equipos WSDC", "Individual (1vs1)"]
    )

if tipo_rubrica == "Equipos WSDC":
    rubrica_seleccionada = os.path.join(os.getcwd(), ARCHIVO_RUBRICA_EQUIPOS)
else:
    rubrica_seleccionada = os.path.join(os.getcwd(), ARCHIVO_RUBRICA_1VS1)

with st.expander("👀 Ver reglas de evaluación que usará la IA (Rúbrica)"):
    try:
        with open(rubrica_seleccionada, "r", encoding="utf-8") as file:
            st.text(file.read())
    except FileNotFoundError:
        st.error(f"Archivo de rúbrica no encontrado.")

st.divider() 
archivo_subido = st.file_uploader("Sube el audio/video del debate aquí", type=["mp3", "mp4", "wav"])

if archivo_subido is not None:
    st.success(f"🎵 Archivo '{archivo_subido.name}' cargado temporalmente. Configura tus opciones arriba y presiona el botón para iniciar.")
    st.audio(archivo_subido)
    
    if not st.session_state.evaluado:
        if st.button("🚀 Iniciar Evaluación", type="primary"):
            nombre_unico = f"{uuid.uuid4()}_{archivo_subido.name}"
            ruta_audio_temporal = os.path.join(os.getcwd(), nombre_unico)
            with open(ruta_audio_temporal, "wb") as f:
                f.write(archivo_subido.getbuffer())
                
            try:
                # -----------------------------------------------------
                # RUTA A: PROCESAMIENTO EN LA NUBE (SWARM PURE + WHISPER)
                # -----------------------------------------------------
                if arquitectura_elegida == "Sistema Multi-Agente (Swarm)":
                    if not api_key_openai:
                        st.error("⚠️ El administrador del sistema no ha configurado la clave de OpenAI en el servidor.")
                        st.stop()
                        
                    with st.status("Ejecutando Enjambre de IA (Transcribiendo y Evaluando)...", expanded=True) as status:
                        st.write("🎙️ Envi
