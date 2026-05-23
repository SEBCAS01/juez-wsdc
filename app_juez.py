import streamlit as st
import requests
import os
import uuid
from fpdf import FPDF
from juez_swarm import ejecutar_evaluacion_swarm

# Esto crea una cajita en un menú lateral para pegar el link de Ngrok
st.sidebar.subheader("🔌 Conexión al Cerebro (IA)")
url_langflow = st.sidebar.text_input(
    "Pega aquí tu URL de Ngrok:", 
    value="https://auction-hurried-passover.ngrok-free.dev" 
)

# Agrega esto en el Sidebar debajo del input de Ngrok:
st.sidebar.subheader("🔑 Clave OpenAI (Para Swarm)")
api_key_openai = st.sidebar.text_input("Pega tu API Key de OpenAI aquí:", type="password")

# ==========================================
# 1. CONFIGURACIÓN DE LLAVES Y RUTAS
# ==========================================
# Pega aquí la clave secreta que generaste en los Settings de Langflow
LANGFLOW_API_KEY = "sk-MKqzedV2Z3UnKzV4yOnFLaXiynsczt-_WuDZQKRkjCs" 

# Nombres exactos de tus archivos de texto (deben estar en la misma carpeta que este script de Python)
ARCHIVO_RUBRICA_EQUIPOS = "RUBRICA_EQUIPOS.txt"
ARCHIVO_RUBRICA_1VS1 = "RUBRICA_1V1.txt"

# Diccionario maestro: Llena los espacios con los IDs exactos de Langflow
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
# 1.5 INICIALIZACIÓN DE LA MEMORIA DE SESIÓN (STATE)
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
# 1.8 FUNCIÓN MAESTRA PARA GENERAR PDF FORMATEADO
# ==========================================
def generar_pdf_veredictos(texto, arquitectura, rubrica):
    # Limpiamos el texto de asteriscos de Markdown para que el PDF se vea limpio
    texto_limpio = texto.replace("**", "").replace("###", "")
    
    # Configuramos el formato adaptando caracteres en español (Latin-1)
    texto_safe = texto_limpio.encode('latin-1', 'replace').decode('latin-1')
    arq_safe = arquitectura.encode('latin-1', 'replace').decode('latin-1')
    rub_safe = rubrica.encode('latin-1', 'replace').decode('latin-1')
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Banner de Encabezado Estilizado
    pdf.set_fill_color(31, 41, 55) # Gris oscuro/azul profesional
    pdf.rect(0, 0, 210, 38, 'F')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_y(12)
    pdf.cell(0, 8, "VEREDICTO OFICIAL DE EVALUACION", ln=True, align="C")
    
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(209, 213, 219)
    pdf.cell(0, 6, "Plataforma de IA para Debates WSDC", ln=True, align="C")
    
    # Bloque de Metadatos
    pdf.set_y(45)
    pdf.set_fill_color(243, 244, 246) # Gris claro
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(75, 85, 99)
    pdf.cell(0, 10, f"  Cerebro: {arq_safe}   |   Formato: {rub_safe}", ln=True, fill=True)
    pdf.ln(5)
    
    # Cuerpo del Texto
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(17, 24, 39) # Negro tipográfico
    pdf.multi_cell(0, 6, texto_safe)
    
    # Retorna los bytes del PDF directamente a memoria
    return pdf.output()

# ==========================================
# 2. CONFIGURACIÓN VISUAL DE LA PÁGINA
# ==========================================
st.set_page_config(page_title="Juez Automático WSDC", page_icon="⚖️", layout="centered")
st.title("⚖️ Juez Automático de Debates WSDC")
st.markdown("Plataforma de evaluación automática. Selecciona la arquitectura de IA, el formato del debate y sube la grabación para obtener el veredicto.")

# ==========================================
# 3. PANELES DE CONFIGURACIÓN (MENÚS)
# ==========================================
st.subheader("⚙️ Parámetros de Evaluación")

col1, col2 = st.columns(2)

with col1:
    # AÑADIMOS SWARM A LA LISTA DE OPCIONES
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

# ==========================================
# 4. ZONA DE SUBIDA Y PROCESAMIENTO
# ==========================================
st.divider() 
archivo_subido = st.file_uploader("Sube el audio/video del debate aquí", type=["mp3", "mp4", "wav"])

if archivo_subido is not None:
    st.success(f"🎵 Archivo '{archivo_subido.name}' cargado temporalmente. Configura tus opciones arriba y presiona el botón para iniciar.")
    st.audio(archivo_subido)
    
    # Solo mostramos el botón de iniciar si NO se ha evaluado el archivo actual
    if not st.session_state.evaluado:
        if st.button("🚀 Iniciar Evaluación", type="primary"):
            with st.spinner(f"Evaluando debate con {arquitectura_elegida}... Esto puede tardar unos minutos."):
                
                nombre_unico = f"{uuid.uuid4()}_{archivo_subido.name}"
                ruta_audio_temporal = os.path.join(os.getcwd(), nombre_unico)
                with open(ruta_audio_temporal, "wb") as f:
                    f.write(archivo_subido.getbuffer())
                
                try:
                    # -----------------------------------------------------
                    # RUTA A: PROCESAMIENTO CON SWARM (API DE OPENAI)
                    # -----------------------------------------------------
                    if arquitectura_elegida == "Sistema Multi-Agente (Swarm)":
                        if not api_key_openai or api_key_openai.strip() == "":
                            st.error("⚠️ Para usar Swarm, debes pegar tu clave de OpenAI en la barra lateral.")
                            st.stop()
                            
                        st.toast("Transcribiendo y debatiendo con Agentes Swarm...")
                        resultado_texto = ejecutar_evaluacion_swarm(
                            ruta_audio_temporal, 
                            rubrica_seleccionada, 
                            api_key_openai
                        )
                        
                        # GUARDAMOS TODO EN LA MEMORIA DE SESIÓN
                        st.session_state.resultado_texto = resultado_texto
                        st.session_state.arquitectura_usada = arquitectura_elegida
                        st.session_state.rubrica_usada = tipo_rubrica
                        st.session_state.evaluado = True
                        st.rerun()

                    # -----------------------------------------------------
                    # RUTA B: PROCESAMIENTO CON LANGFLOW LOCAL
                    # -----------------------------------------------------
                    else:
                        config_actual = ARQUITECTURAS[arquitectura_elegida]
                        flow_url = f"{url_langflow.rstrip('/')}/api/v1/run/{config_actual['flow_id']}"
                        
                        tweaks = {
                            config_actual["diarizador_id"]: {
                                "audio_file": ruta_audio_temporal
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
                        
                        response = requests.post(flow_url, json=payload, headers=headers, timeout=1200)
                        response.raise_for_status() 
                        datos = response.json()
                        
                        try:
                            resultado_texto = datos["outputs"][0]["outputs"][0]["results"]["message"]["text"]
                            
                            # GUARDAMOS TODO EN LA MEMORIA DE SESIÓN
                            st.session_state.resultado_texto = resultado_texto
                            st.session_state.arquitectura_usada = arquitectura_elegida
                            st.session_state.rubrica_usada = tipo_rubrica
                            st.session_state.evaluado = True
                            st.rerun()
                            
                        except KeyError:
                            st.warning("El formato de respuesta cambió. Mostrando datos crudos:")
                            st.json(datos)
                            
                except requests.exceptions.Timeout:
                    st.error("⏰ El proceso tardó demasiado tiempo en responder.")
                except Exception as e:
                    st.error(f"❌ Error durante el procesamiento: {e}")
                    
                finally:
                    if os.path.exists(ruta_audio_temporal):
                        os.remove(ruta_audio_temporal)

# ==========================================
# 5. RENDERIZADO DEL RESULTADO PERMANENTE
# ==========================================
if st.session_state.evaluado and st.session_state.resultado_texto:
    st.divider()
    st.success("✨ ¡Análisis completado exitosamente!")
    st.subheader(f"🏆 Veredicto Final")
    st.caption(f"Evaluado usando {st.session_state.arquitectura_usada} con rúbrica de {st.session_state.rubrica_usada}")
    
    # El texto permanece pase lo que pase
    st.write(st.session_state.resultado_texto)
    
    # Compilamos el PDF en memoria listo para la descarga
    pdf_data = generar_pdf_veredictos(
        st.session_state.resultado_texto, 
        st.session_state.arquitectura_usada, 
        st.session_state.rubrica_usada
    )
    
    # Bloque de Botones de Control de la Sesión
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
        # BOTÓN NUEVO: El usuario decide de forma manual cuándo resetear la pantalla
        if st.button("🔄 Nueva Evaluación / Limpiar", type="secondary", use_container_width=True):
            st.session_state.resultado_texto = None
            st.session_state.evaluado = False
            st.session_state.arquitectura_usada = ""
            st.session_state.rubrica_usada = ""
            st.rerun()