# ⚖️ Juez WSDC — Sistema de Evaluación Automática de Debates

Plataforma de evaluación automática para debates en formato **WSDC (World Schools Debating Championship)**. El sistema procesa grabaciones de audio, transcribe y diariza el debate por hablante, evalúa la calidad argumentativa con un modelo especializado (**TRACE**), y genera un veredicto oficial usando IA generativa aplicando la rúbrica WSDC.

> 🇬🇧 Read this in English: [README.en.md](README.en.md)

---

## 📋 Tabla de contenidos

- [Arquitectura general](#-arquitectura-general)
- [Arquitecturas de evaluación disponibles](#-arquitecturas-de-evaluación-disponibles)
- [¿Qué es TRACE?](#-qué-es-trace)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Configuración de API Keys](#-configuración-de-api-keys)
- [Cómo correr la aplicación](#-cómo-correr-la-aplicación)
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

---

## 🧠 Arquitecturas de evaluación disponibles

La interfaz permite elegir entre 4 "cerebros" de evaluación:

| Arquitectura | Motor | Descripción |
|---|---|---|
| **Cadena (Chain)** | Langflow | Pipeline lineal simple de evaluación |
| **Árbol (Tree)** | Langflow | Evaluación jerárquica por ramas de criterio |
| **Grafo (Graph)** | Langflow | Evaluación con dependencias cruzadas entre criterios |
| **Multi-Agente (Swarm)** | OpenAI Swarm | 3 agentes GPT-4o especializados (Argumentación, Estilo, Juez Principal) que colaboran y se transfieren el control entre sí |

Las 3 primeras corren sobre **Langflow** (requiere tenerlo desplegado y accesible vía su API, ver `url_langflow` en el sidebar de la app). La cuarta (**Swarm**) corre completamente dentro de esta aplicación Streamlit, sin dependencias externas de Langflow.

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

- Python 3.11+
- Cuenta y API Key de [OpenAI](https://platform.openai.com/) (para el modo Swarm)
- Cuenta y API Key de [Deepgram](https://deepgram.com/) (para transcripción + diarización, todas las arquitecturas)
- (Opcional) Instancia de [Langflow](https://www.langflow.org/) desplegada y accesible, si se usarán las arquitecturas Chain/Tree/Graph
- ~1GB de espacio en disco libre para los pesos del modelo TRACE

---

## 🚀 Instalación

```bash
# 1. Clona el repositorio (incluye los pesos de TRACE vía Git LFS)
git lfs install
git clone https://github.com/SEBCAS01/juez-wsdc.git
cd juez-wsdc

# 2. Crea y activa un entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instala las dependencias
pip install -r requirements.txt
```

> El `requirements.txt` incluye `--extra-index-url` para instalar automáticamente los wheels CPU de PyTorch — no se requieren pasos manuales adicionales.

---

## 🔑 Configuración de API Keys

Copia la plantilla de configuración y complétala con tus propias keys:

```bash
mkdir -p ~/.streamlit
cp secrets.toml.example ~/.streamlit/secrets.toml
nano ~/.streamlit/secrets.toml
```

Debe quedar así:
```toml
OPENAI_API_KEY = "sk-tu-clave-de-openai"
DEEPGRAM_API_KEY = "tu-clave-de-deepgram"
```

> ⚠️ **Nunca subas `secrets.toml` con tus keys reales al repositorio.** El `.gitignore` ya lo excluye por defecto.

---

## ▶️ Cómo correr la aplicación

```bash
source venv/bin/activate
python -m streamlit run app_juez.py --server.port 8501 --server.address 0.0.0.0
```

Abre tu navegador en `http://localhost:8501` (o `http://<ip-de-tu-servidor>:8501` si corres en una VPS).

### Para dejarlo corriendo en segundo plano (VPS)

```bash
nohup python -m streamlit run app_juez.py --server.port 8501 --server.address 0.0.0.0 > streamlit.log 2>&1 &
```

---

## 📁 Estructura del proyecto

```
juez-wsdc/
├── app_juez.py               # Interfaz Streamlit principal
├── juez_swarm.py              # Lógica del modo Multi-Agente (Swarm) + Deepgram + TRACE
├── trace_scorer.py             # Wrapper de TRACE para el modo Swarm (por hablante)
├── trace_runner.py             # Script standalone para correr TRACE desde stdin
├── requirements.txt             # Dependencias del proyecto
├── secrets.toml.example         # Plantilla de configuración de API keys
├── RUBRICA_1V1.txt              # Rúbrica para debates individuales
├── RUBRICA_EQUIPOS.txt          # Rúbrica para debates por equipos
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
Si el archivo pesa solo unos cientos de bytes, es un puntero LFS sin resolver — corre `git lfs pull` de nuevo.

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
Asegúrate de que `requirements.txt` incluya la línea `--extra-index-url https://download.pytorch.org/whl/cpu` al inicio del archivo. Sin esto, pip no encuentra los wheels CPU-only de PyTorch.

### Streamlit se detiene al cerrar la sesión SSH
Corre el proceso con `nohup` (ver sección "Cómo correr la aplicación") para que sobreviva al cierre de la terminal.

---

## 📚 Referencias

- Kim, Y. & Yang, H. (2026). *TRACE: Toulmin-based Reasoning Assessment through Constructive Elements for LLM CoT Evaluation*. PMLR 306.
- Toulmin, S. E. (2003). *The Uses of Argument*. Cambridge University Press.
- Flavell, J. H. (1979). *Metacognition and cognitive monitoring: A new area of cognitive-developmental inquiry*. American Psychologist, 34(10), 906.
- He, P., Gao, J., & Chen, W. (2023). *DeBERTaV3: Improving DeBERTa using ELECTRA-Style Pre-Training with Gradient-Disentangled Embedding Sharing*. ICLR.

---

## 📄 Licencia

Este proyecto es de uso académico/investigación.
