# ⚖️ Juez WSDC — Sistema de Evaluación Automática de Debates

Plataforma de evaluación automática para debates en formato **WSDC (World Schools Debating Championship)**. El sistema procesa grabaciones de audio, transcribe y diariza el debate por hablante, evalúa la calidad argumentativa con un modelo especializado (**TRACE**), y genera un veredicto oficial usando IA generativa aplicando la rúbrica WSDC.

> 🇬🇧 Read this in English: [README.en.md](README.en.md)

> 📌 **Estas instrucciones están escritas para un despliegue en una VPS con Ubuntu.** Si instalas en otro sistema operativo, los comandos de paquetes del sistema (`apt-get`) y las rutas absolutas (`/root/...`) van a variar.

---

## 📋 Tabla de contenidos

- [Arquitectura general](#-arquitectura-general)
- [Arquitecturas de evaluación disponibles](#-arquitecturas-de-evaluación-disponibles)
- [¿Qué es TRACE?](#-qué-es-trace)
- [Requisitos](#-requisitos)
- [Instalación completa (VPS Ubuntu)](#-instalación-completa-vps-ubuntu)
- [Configuración de API Keys](#-configuración-de-api-keys)
- [Configuración de los flujos de Langflow](#-configuración-de-los-flujos-de-langflow)
- [Cómo correr la aplicación](#-cómo-correr-la-aplicación)
- [Audios de prueba](#-audios-de-prueba)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Rúbricas de evaluación](#-rúbricas-de-evaluación)
- [Troubleshooting](#-troubleshooting)
- [Referencias](#-referencias)

---

## 🏗️ Arquitectura general

El pipeline completo sigue estos pasos, sin importar qué arquitectura de IA se elija:

```
Audio del debate (.mp3/.mp4/.wav)
        │
        ▼
Transcripción + Diarización (Deepgram, modelo nova-2)
        │
        ▼
Análisis TRACE por hablante (DeBERTa-v3, clasificación Toulmin)
        │
        ▼
Evaluación argumentativa (LLM aplicando rúbrica WSDC + evidencia TRACE)
        │
        ▼
Veredicto oficial (Streamlit UI + descarga en PDF)
```

Todas las arquitecturas comparten la misma fuente de transcripción/diarización (Deepgram) y el mismo módulo de scoring TRACE (`trace-module/`), garantizando resultados comparables entre sí.

Este proyecto tiene **dos componentes que corren de forma independiente en la misma VPS**:
1. **Langflow** — motor de flujos visuales, necesario para 3 de las 4 arquitecturas de evaluación
2. **La app de Streamlit** (`app_juez.py`) — la interfaz principal que el usuario final utiliza, y que se conecta a Langflow vía su API

---

## 🧠 Arquitecturas de evaluación disponibles

La interfaz permite elegir entre 4 "cerebros" de evaluación:

| Arquitectura | Motor | Descripción |
|---|---|---|
| **Cadena (Chain)** | Langflow | Pipeline lineal simple de evaluación |
| **Árbol (Tree)** | Langflow | Evaluación jerárquica por ramas de criterio |
| **Grafo (Graph)** | Langflow | Evaluación con dependencias cruzadas entre criterios |
| **Multi-Agente (Swarm)** | OpenAI Swarm | 3 agentes GPT-4o especializados (Argumentación, Estilo, Juez Principal) que colaboran y se transfieren el control entre sí |

**Langflow es un requisito del proyecto, no opcional** — 3 de las 4 arquitecturas dependen de él. Solo si tu intención es usar exclusivamente el modo Swarm podrías omitir la instalación de Langflow, pero la instalación completa documentada aquí asume que quieres las 4 arquitecturas funcionando.

---

## 🔬 ¿Qué es TRACE?

**TRACE (Toulmin-based Reasoning Assessment through Constructive Elements)** es una métrica desarrollada por Kim & Yang (ICML 2026) para evaluar la calidad estructural de un argumento, basada en el **modelo de Toulmin** y la **teoría metacognitiva de Flavell**.

### Cómo funciona

1. **Segmentación**: el texto de cada hablante se divide en oraciones (spaCy, modelo en español `es_core_news_sm`).
2. **Clasificación multi-label**: cada oración se pasa por un modelo `DeBERTa-v3-base` fine-tuneado (`TraceDeBERTa`) que detecta la presencia de 8 elementos constructivos:
   - `Claim` (afirmación/conclusión)
   - `Data/Evidence` (evidencia/datos)
   - `Warrant` (razonamiento que conecta evidencia con conclusión)
   - `Backing` (respaldo del razonamiento)
   - `Qualifier` (expresión de certeza/incertidumbre)
   - `Rebuttal` (contraargumento)
   - `Monitoring` (auto-chequeo, metacognición)
   - `Evaluation` (juicio sobre la calidad del propio razonamiento)
3. **Cálculo del score**: combina dos componentes ponderados (α = 0.7):

   ```
   TRACE = α · State Validity + (1 − α) · Transition Coherence
   ```

   - **State Validity**: ¿tiene cada oración una combinación de labels argumentativamente válida? (ej. `Claim+Evaluation` es válido; `Qualifier` aislado es débil)
   - **Transition Coherence**: ¿fluyen bien las oraciones consecutivas? (ej. `Data/Evidence → Claim` es una transición "buena"; `Monitoring → Qualifier` repetido indica divagación/duda)

El resultado es un número entre 0 y 1 — mientras más alto, más sólida es la estructura argumentativa de ese orador.

> ⚠️ **Importante**: TRACE evalúa **estructura argumentativa**, no corrección factual. Un orador puede tener TRACE alto con datos incorrectos (argumenta bien pero se equivoca), o TRACE bajo con una conclusión correcta (dubitativo pero acertó). Por eso se usa como **complemento** a la evaluación del LLM juez, no como reemplazo.

**Paper original:** Kim, Y. & Yang, H. (2026). *TRACE: Toulmin-based Reasoning Assessment through Constructive Elements for LLM CoT Evaluation*. PMLR 306. [Código fuente del modelo](https://github.com/hyyangkisti/trace)

---

## ✅ Requisitos

- VPS con **Ubuntu 22.04+** (probado en Ubuntu, CPU-only, sin GPU)
- Python 3.11+
- Cuenta y API Key de [OpenAI](https://platform.openai.com/) (para el modo Swarm)
- Cuenta y API Key de [Deepgram](https://deepgram.com/) (para transcripción + diarización, todas las arquitecturas)
- Cuenta y API Key de [Google AI Studio](https://aistudio.google.com/) (Gemini, usado dentro de los flujos de Langflow para Chain/Tree/Graph)
- ~1GB de espacio en disco libre para los pesos del modelo TRACE
- Acceso `root` o `sudo` en la VPS

---

## 🚀 Instalación completa (VPS Ubuntu)

### Paso 1: Actualiza el sistema e instala dependencias base

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip git git-lfs
git lfs install
```

### Paso 2: Crea la carpeta del proyecto y clona el repositorio

```bash
mkdir -p /root/juez-wsdc
cd /root
git clone https://github.com/SEBCAS01/juez-wsdc.git
cd juez-wsdc
```

### Paso 3: Crea y activa el entorno virtual de la aplicación

```bash
python3 -m venv venv
source venv/bin/activate
```

> A partir de aquí, cada vez que abras una nueva sesión SSH para trabajar en el proyecto, debes reactivar el entorno con `source venv/bin/activate` (estando dentro de `/root/juez-wsdc`).

### Paso 4: Instala las dependencias de la aplicación

```bash
pip install -r requirements.txt
```

> El `requirements.txt` incluye una línea `--extra-index-url` que instala automáticamente los wheels CPU de PyTorch — no se requieren pasos manuales adicionales.

### Paso 5: Verifica que los pesos del modelo TRACE se descargaron vía Git LFS

```bash
git lfs pull
ls -la models/trace/model.safetensors
```
Debe pesar aproximadamente 700MB. Si pesa solo unos bytes, es un puntero LFS sin resolver — corre `git lfs pull` de nuevo.

### Paso 6: Instala Langflow (en un entorno virtual **separado**)

Langflow tiene un árbol de dependencias enorme (LangChain y decenas de integraciones) que puede generar conflictos si se mezcla con el entorno de la app. Por eso se instala en su **propio venv**, independiente del de Streamlit:

```bash
cd /root/juez-wsdc
python3 -m venv venv-langflow
source venv-langflow/bin/activate
pip install langflow
deactivate
```

Continúa con la sección [Configuración de los flujos de Langflow](#-configuración-de-los-flujos-de-langflow) antes de correr la aplicación por primera vez.

---

## 🔑 Configuración de API Keys

Hay **dos sistemas de configuración de keys completamente separados** en este proyecto — no se mezclan ni comparten archivo:

### 1. Keys de la app de Streamlit (OpenAI + Deepgram)

```bash
mkdir -p ~/.streamlit
cp /root/juez-wsdc/secrets.toml.example ~/.streamlit/secrets.toml
nano ~/.streamlit/secrets.toml
```

Debe quedar así:
```toml
OPENAI_API_KEY = "sk-tu-clave-de-openai"
DEEPGRAM_API_KEY = "tu-clave-de-deepgram"
```

Estas dos keys se leen automáticamente por `app_juez.py` al iniciar Streamlit. Son necesarias para **todas** las arquitecturas (Deepgram) y específicamente para el modo Swarm (OpenAI).

### 2. Key de Gemini (usada dentro de Langflow, para Chain/Tree/Graph)

Esta key **no va en `secrets.toml`** — se configura directamente dentro de la interfaz de Langflow, como se detalla en la siguiente sección.

> ⚠️ **Nunca subas `secrets.toml` con tus keys reales al repositorio.** El `.gitignore` ya lo excluye por defecto.

---

## 🔧 Configuración de los flujos de Langflow

Los flujos exportados están en `langflow-flows/`:
```
langflow-flows/
├── chain_arquitectura_lineal.json
├── tree_arquitectura_arbol.json
└── graph_arquitectura_grafos.json
```

### Por qué esto requiere un paso manual

Langflow **regenera los IDs de flow y de componente cada vez que un flujo se importa** — no existe forma de fijarlos o preservarlos entre exportación e importación ([limitación documentada oficialmente](https://github.com/langflow-ai/langflow/issues/5375)). Esto significa que los IDs hardcodeados en `app_juez.py` (dentro del diccionario `ARQUITECTURAS`) van a quedar desactualizados apenas importes los flujos en tu propia instancia, y **debes actualizarlos manualmente**.

### Pasos

1. **Levanta Langflow** (ver comando en la siguiente sección) y abre `http://<ip-de-tu-vps>:7860` en el navegador
2. Importa cada uno de los 3 archivos `.json` de `langflow-flows/` (botón **"Import"** en la página de Proyectos)
3. Configura tu key de Gemini como **Global Variable**: perfil → **Settings** → **Global Variables** → crea una variable, por ejemplo `GEMINI_API_KEY`, con tu clave de Google AI Studio
4. Abre cada uno de los 3 flujos importados, localiza el/los componente(s) de modelo Gemini, y en el campo de API key selecciona esa Global Variable en vez de pegar la clave literal (así solo la configuras una vez para los 3 flujos)
5. Dentro de cada flujo, copia:
   - El **Flow ID** (visible en la URL al editar el flujo, ej. `.../flow/<este-es-el-flow-id>`)
   - El **ID del componente Diarizador** (click en el componente → aparece en su configuración, formato `NombreComponente-XXXXX`)
   - El **ID del componente de lectura de rúbrica** (`ReadFile`, mismo formato)
6. Abre `app_juez.py` y reemplaza los valores correspondientes en `ARQUITECTURAS`:

```python
ARQUITECTURAS = {
    "Arquitectura Lineal (Chain)": {
        "flow_id": "TU-NUEVO-FLOW-ID-AQUI",
        "diarizador_id": "TU-NUEVO-DIARIZADOR-ID-AQUI",
        "readfile_rubrica_id": "TU-NUEVO-READFILE-ID-AQUI"
    },
    # ... repetir para Tree y Graph
}
```

7. Guarda el archivo y reinicia Streamlit (ver siguiente sección)

---

## ▶️ Cómo correr la aplicación

Necesitas **dos procesos corriendo en paralelo**: Langflow y Streamlit. Cada uno usa su propio entorno virtual.

### Levantar Langflow

```bash
cd /root/juez-wsdc
source venv-langflow/bin/activate
python -m langflow run --host 0.0.0.0 --port 7860
```
Langflow queda disponible en `http://<ip-de-tu-vps>:7860`.

### Levantar la app de Streamlit (en otra sesión/terminal)

```bash
cd /root/juez-wsdc
source venv/bin/activate
python -m streamlit run app_juez.py --server.port 8501 --server.address 0.0.0.0
```
La app queda disponible en `http://<ip-de-tu-vps>:8501`.

### Dejar ambos corriendo en segundo plano (recomendado para VPS)

Si cierras la sesión SSH con los comandos anteriores corriendo directamente, **el proceso se detiene**. Usa `nohup` para que sobrevivan al cierre de la terminal:

```bash
# Langflow
cd /root/juez-wsdc
source venv-langflow/bin/activate
nohup python -m langflow run --host 0.0.0.0 --port 7860 > langflow.log 2>&1 &
deactivate

# Streamlit
cd /root/juez-wsdc
source venv/bin/activate
nohup python -m streamlit run app_juez.py --server.port 8501 --server.address 0.0.0.0 > streamlit.log 2>&1 &
deactivate
```

Verifica que ambos quedaron corriendo:
```bash
ps aux | grep -E "langflow|streamlit"
```

Para detenerlos:
```bash
pkill -f "langflow run"
pkill -f "streamlit run app_juez.py"
```

---

## 🎧 Audios de prueba

En la carpeta [`sample-audios/`](sample-audios/) hay grabaciones de debates de ejemplo para probar la plataforma sin necesidad de tener tus propias grabaciones a mano. Súbelas directamente desde la interfaz de Streamlit para verificar que la instalación funciona correctamente de punta a punta (transcripción, diarización, TRACE, y veredicto final).

---

## 📁 Estructura del proyecto

```
juez-wsdc/
├── app_juez.py               # Interfaz Streamlit principal
├── juez_swarm.py              # Lógica del modo Multi-Agente (Swarm) + Deepgram + TRACE
├── trace_scorer.py             # Wrapper de TRACE para el modo Swarm (por hablante)
├── trace_runner.py             # Script standalone para correr TRACE desde stdin
├── requirements.txt             # Dependencias de la app de Streamlit
├── secrets.toml.example         # Plantilla de configuración de API keys (Streamlit)
├── RUBRICA_1V1.txt              # Rúbrica para debates individuales
├── RUBRICA_EQUIPOS.txt          # Rúbrica para debates por equipos
├── sample-audios/               # Audios de ejemplo para probar la plataforma
├── langflow-flows/              # Flujos exportados de Langflow (requieren re-configurar IDs, ver arriba)
│   ├── chain_arquitectura_lineal.json
│   ├── tree_arquitectura_arbol.json
│   └── graph_arquitectura_grafos.json
├── models/
│   └── trace/                  # Pesos del modelo TRACE-DeBERTa (Git LFS)
└── trace-module/
    ├── eval/
    │   ├── calculate.py         # Cálculo de State Validity / Transition Coherence
    │   ├── parser.py            # Segmentación de oraciones (spaCy, español)
    │   └── inference.py         # Inferencia del modelo TraceDeBERTa
    └── main.py                  # CLI standalone del framework TRACE original
```

---

## 📊 Rúbricas de evaluación

El sistema soporta dos formatos de rúbrica WSDC:

- **`RUBRICA_1V1.txt`** — para debates individuales (1 vs 1)
- **`RUBRICA_EQUIPOS.txt`** — para debates por equipos

Ambas rúbricas evalúan sobre 100 puntos totales:
- **Contenido**: 40 puntos
- **Estilo**: 40 puntos
- **Estrategia**: 20 puntos

Puedes editar estos archivos directamente para ajustar los criterios sin tocar el código.

---

## 🛠️ Troubleshooting

### El modelo TRACE no carga / error de `local_files_only`
Verifica que los pesos se descargaron correctamente vía Git LFS:
```bash
git lfs pull
ls -la models/trace/model.safetensors  # debe pesar ~700MB, no unos pocos bytes
```

### `ModuleNotFoundError` para `calculate` o `parser`
Estos módulos se importan dinámicamente agregando su ruta a `sys.path`. Confirma que la ruta exista:
```bash
ls /root/juez-wsdc/trace-module/eval/
```
Si tu proyecto no está en `/root/juez-wsdc/`, ajusta la constante `TRACE_PATH` en `trace_scorer.py`.

### Falla la segmentación de oraciones en español
Instala el modelo de spaCy en español si no viene incluido:
```bash
python -m spacy download es_core_news_sm
```

### Error de autenticación con Deepgram/OpenAI
Confirma que `~/.streamlit/secrets.toml` existe y tiene el formato correcto (ver sección de configuración arriba). Verifica también que el proceso de Streamlit fue reiniciado después de crear/editar el archivo.

### `torch==2.4.0+cpu` no se instala
Asegúrate de que `requirements.txt` incluya la línea `--extra-index-url https://download.pytorch.org/whl/cpu` al inicio del archivo.

### Langflow y Streamlit se detienen al cerrar la sesión SSH
Usa `nohup` para ambos procesos (ver sección "Dejar ambos corriendo en segundo plano").

### Error "flow not found" o "component not found" en Chain/Tree/Graph
Los IDs hardcodeados en `ARQUITECTURAS` (`app_juez.py`) corresponden a la instancia original de Langflow donde se crearon los flujos. Si importaste los flujos en una instancia distinta, **debes actualizar esos IDs manualmente** — ver [Configuración de los flujos de Langflow](#-configuración-de-los-flujos-de-langflow).

### Conflictos de dependencias entre Langflow y la app de Streamlit
Si instalaste ambos en el mismo entorno virtual, es muy probable que tengas conflictos de versiones (Langflow trae su propia versión de `torch`, `transformers`, etc.). Usa **dos venvs separados** como se indica en la sección de instalación (`venv/` para la app, `venv-langflow/` para Langflow).

---

## 📚 Referencias

- Kim, Y. & Yang, H. (2026). *TRACE: Toulmin-based Reasoning Assessment through Constructive Elements for LLM CoT Evaluation*. PMLR 306.
- Toulmin, S. E. (2003). *The Uses of Argument*. Cambridge University Press.
- Flavell, J. H. (1979). *Metacognition and cognitive monitoring: A new area of cognitive-developmental inquiry*. American Psychologist, 34(10), 906.
- He, P., Gao, J., & Chen, W. (2023). *DeBERTaV3: Improving DeBERTa using ELECTRA-Style Pre-Training with Gradient-Disentangled Embedding Sharing*. ICLR.

---

## 📄 Licencia

Este proyecto es de uso académico/investigación. Ajusta esta sección según corresponda a tu contexto institucional.
