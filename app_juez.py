import streamlit as st
import requests
import os
import uuid
import shutil
from fpdf import FPDF
from juez_swarm import ejecutar_evaluacion_swarm
import time

# ==========================================
# 1. CONFIGURACIÓN VISUAL Y BARRA LATERAL
# ==========================================
st.set_page_config(page_title="Juez Automático WSDC", page_icon="⚖️", layout="centered")

st.sidebar.subheader("🔌 Conexión al Cerebro (IA)")
url_langflow = st.sidebar.text_input(
    "Pega aquí tu URL de Ngrok (o localhost para VPS):",
    value="http://178.105.248.246:7860"
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
    st.sidebar.warning("⚠️ Modo sin API Key de OpenAI. Swarm no funcionará.")

try:
    api_key_deepgram = st.secrets.get("DEEPGRAM_API_KEY", None)
    if not api_key_deepgram:
        raise ValueError("Llave vacía")
except Exception:
    api_key_deepgram = None
    st.sidebar.warning("⚠️ Modo sin API Key de Deepgram. Swarm no funcionará.")

# ==========================================
# 2. CONFIGURACIÓN DE LLAVES Y RUTAS
# ==========================================
LANGFLOW_API_KEY = "sk-5QBKBErZvnFrswaSnmu7eOa_Mf9xZwmbM9kNzyhAnEs"
ARCHIVO_RUBRICA_EQUIPOS = "RUBRICA_EQUIPOS.txt"
ARCHIVO_RUBRICA_1VS1 = "RUBRICA_1V1.txt"
LANGFLOW_CACHE = "/root/.cache/langflow/root/juez-wsdc"

ARQUITECTURAS = {
    "Arquitectura Lineal (Chain)": {
        "flow_id": "aa9b2ebe-b00e-487f-ac25-05c01f943248",
        "diarizador_id": "DiarizadorWSDC-5fYq9",
        "readfile_rubrica_id": "File-Temvp"
    },
    "Arquitectura de Árbol (Tree)": {
        "flow_id": "157b5a89-6e55-4671-a4e0-a3ee14c3d57c",
        "diarizador_id": "DiarizadorWSDC-3QpYw",
        "readfile_rubrica_id": "File-k3TmF"
    },
    "Arquitectura de Grafos (Graph)": {
        "flow_id": "9afb1f1d-8709-4552-8c2b-13121b9bf77e",
        "diarizador_id": "DiarizadorWSDC-MUGRA",
        "readfile_rubrica_id": "File-BnTw7"
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
if "tiempo_total" not in st.session_state:
    st.session_state.tiempo_total = 0.0

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

if arquitectura_elegida != "Sistema Multi-Agente (Swarm)":
    st.info("ℹ️ **Aviso de Arquitectura:** Las opciones de Langflow asumen que el motor está corriendo en el mismo entorno o VPS que esta web para compartir rutas de disco.")

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
            tiempo_inicio = time.time()
            nombre_unico = f"{uuid.uuid4()}_{archivo_subido.name}"
            ruta_audio_temporal = os.path.join("/root/juez-wsdc", nombre_unico)
            ruta_audio_cache = os.path.join(LANGFLOW_CACHE, nombre_unico)

            with open(ruta_audio_temporal, "wb") as f:
                f.write(archivo_subido.getbuffer())

            shutil.copy(ruta_audio_temporal, ruta_audio_cache)

            try:
                # -----------------------------------------------------
                # RUTA A: PROCESAMIENTO EN LA NUBE (SWARM PURE + WHISPER)
                # -----------------------------------------------------
                if arquitectura_elegida == "Sistema Multi-Agente (Swarm)":
                    if not api_key_openai:
                        st.error("⚠️ El administrador del sistema no ha configurado la clave de OpenAI en el servidor.")
                        st.stop()

                    if not api_key_deepgram:
                        st.error("⚠️ El administrador del sistema no ha configurado la clave de Deepgram en el servidor.")
                        st.stop()

                    with st.status("Ejecutando Enjambre de IA (Transcribiendo y Evaluando)...", expanded=True) as status:
                        st.write("🎙️ Enviando audio a Deepgram para transcripción y diarización...")
                        resultado_texto = ejecutar_evaluacion_swarm(
                            ruta_audio_temporal,
                            rubrica_seleccionada,
                            api_key_openai,
                            api_key_deepgram
                        )
                        status.update(label="✅ Análisis Completado", state="complete")

                    st.session_state.resultado_texto = resultado_texto
                    st.session_state.arquitectura_usada = arquitectura_elegida
                    st.session_state.rubrica_usada = tipo_rubrica
                    tiempo_fin = time.time()
                    st.session_state.tiempo_total = tiempo_fin - tiempo_inicio
                    st.session_state.evaluado = True
                    st.rerun()

                # -----------------------------------------------------
                # RUTA B: PROCESAMIENTO CON LANGFLOW (LAS 3 ARQUITECTURAS RESTANTES)
                # -----------------------------------------------------
                else:
                    with st.spinner(f"Evaluando debate con {arquitectura_elegida}... Esto puede tardar unos minutos."):
                        config_actual = ARQUITECTURAS[arquitectura_elegida]
                        flow_url = f"{url_langflow.rstrip('/')}/api/v1/run/{config_actual['flow_id']}"

                        tweaks = {
                            config_actual["diarizador_id"]: {
                                "audio_file": os.path.join("/root/juez-wsdc", nombre_unico)
                            },
                            config_actual["readfile_rubrica_id"]: {
                                "path": rubrica_seleccionada
                            }
                        }

                        payload = {
                            "output_type": "chat",
                            "input_type": "chat",
                            "input_value": "Inicia la evaluación",
                            "session_id": str(uuid.uuid4()),
                            "tweaks": tweaks
                        }

                        headers = {"x-api-key": LANGFLOW_API_KEY}

                        response = requests.post(flow_url, json=payload, headers=headers, timeout=3600)
                        response.raise_for_status()
                        datos = response.json()

                        tiempo_fin = time.time()
                        st.session_state.tiempo_total = tiempo_fin - tiempo_inicio

                        try:
                            outputs = datos["outputs"][0]["outputs"]
                            bloques = []
                            for output in outputs:
                                try:
                                    texto = output["results"]["message"]["text"]
                                    if texto:
                                        bloques.append(texto)
                                except KeyError:
                                    continue

                            if bloques:
                                resultado_texto = "\n\n---\n\n".join(bloques)
                                st.session_state.resultado_texto = resultado_texto
                                st.session_state.arquitectura_usada = arquitectura_elegida
                                st.session_state.rubrica_usada = tipo_rubrica
                                st.session_state.evaluado = True
                                st.rerun()
                            else:
                                st.warning("No se encontró texto en la respuesta.")
                                st.json(datos)

                        except KeyError:
                            st.warning("El formato de respuesta cambió. Mostrando datos crudos:")
                            st.json(datos)

            except requests.exceptions.Timeout:
                st.error("⏰ El proceso tardó demasiado tiempo en responder.")
            except Exception as e:
                st.error(f"❌ Error durante el procesamiento: {e}\n\nSi estás usando Streamlit Cloud con Langflow local, asegúrate de que comparten rutas o usa la opción Swarm.")

            finally:
                if os.path.exists(ruta_audio_temporal):
                    os.remove(ruta_audio_temporal)
                if os.path.exists(ruta_audio_cache):
                    os.remove(ruta_audio_cache)

# ==========================================
# 6. RENDERIZADO DEL RESULTADO PERMANENTE
# ==========================================
if st.session_state.evaluado and st.session_state.resultado_texto:
    st.divider()
    st.success("✨ ¡Análisis completado exitosamente!")
    st.subheader(f"🏆 Veredicto Final")
    st.caption(f"Evaluado usando {st.session_state.arquitectura_usada} con rúbrica de {st.session_state.rubrica_usada}")
    st.info(f"⏱️ Tiempo total: {st.session_state.tiempo_total:.2f} segundos")

    st.write(st.session_state.resultado_texto)

    pdf_data = generar_pdf_veredictos(
        st.session_state.resultado_texto,
        st.session_state.arquitectura_usada,
        st.session_state.rubrica_usada
    )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        st.download_button(
            label="📥 Descargar Veredicto en PDF",
            data=bytes(pdf_data),
            file_name=f"Veredicto_{st.session_state.rubrica_usada.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    with col_btn2:
        if st.button("🔄 Nueva Evaluación / Limpiar", type="secondary", use_container_width=True):
            st.session_state.resultado_texto = None
            st.session_state.evaluado = False
            st.session_state.arquitectura_usada = ""
            st.session_state.rubrica_usada = ""
            st.session_state.tiempo_total = 0.0
            st.rerun()
