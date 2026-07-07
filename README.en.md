# ⚖️ Juez WSDC — Automated WSDC Debate Evaluation System

Automated evaluation platform for debates in the **WSDC (World Schools Debating Championship)** format. The system processes audio recordings, transcribes and diarizes the debate by speaker, evaluates argumentative quality using a specialized model (**TRACE**), and generates an official verdict using generative AI applying the WSDC rubric.

> 🇪🇸 Léelo en español: [README.md](README.md)

> 📌 **These instructions are written for deployment on an Ubuntu VPS.** If installing on a different operating system, the system package commands (`apt-get`) and absolute paths (`/root/...`) will vary.

---

## 📋 Table of contents

- [General architecture](#-general-architecture)
- [Available evaluation architectures](#-available-evaluation-architectures)
- [What is TRACE?](#-what-is-trace)
- [Requirements](#-requirements)
- [Full installation (Ubuntu VPS)](#-full-installation-ubuntu-vps)
- [API Keys configuration](#-api-keys-configuration)
- [Langflow flows configuration](#-langflow-flows-configuration)
- [Running the application](#-running-the-application)
- [Sample audios](#-sample-audios)
- [Project structure](#-project-structure)
- [Evaluation rubrics](#-evaluation-rubrics)
- [Troubleshooting](#-troubleshooting)
- [References](#-references)

---

## 🏗️ General architecture

The full pipeline follows these steps regardless of which AI architecture is selected:

```
Debate audio (.mp3/.mp4/.wav)
        │
        ▼
Transcription + Diarization (Deepgram, nova-2 model)
        │
        ▼
Per-speaker TRACE analysis (DeBERTa-v3, Toulmin classification)
        │
        ▼
Argumentative evaluation (LLM applying WSDC rubric + TRACE evidence)
        │
        ▼
Official verdict (Streamlit UI + downloadable PDF)
```

All four architectures share the same transcription/diarization source (Deepgram) and the same TRACE scoring module (`trace-module/`), ensuring comparable results across all of them.

This project has **two independently running components on the same VPS**:
1. **Langflow** — visual flow engine, required for 3 of the 4 evaluation architectures
2. **The Streamlit app** (`app_juez.py`) — the main interface the end user interacts with, which connects to Langflow via its API

---

## 🧠 Available evaluation architectures

The interface lets you choose between 4 evaluation "brains":

| Architecture | Engine | Description |
|---|---|---|
| **Chain** | Langflow | Simple linear evaluation pipeline |
| **Tree** | Langflow | Hierarchical evaluation across criterion branches |
| **Graph** | Langflow | Evaluation with cross-dependencies between criteria |
| **Multi-Agent (Swarm)** | OpenAI Swarm | 3 specialized GPT-4o agents (Argumentation, Style, Head Judge) that collaborate and hand off control to each other |

**Langflow is a project requirement, not optional** — 3 of the 4 architectures depend on it. Only if your intent is to exclusively use Swarm mode could you skip installing Langflow, but the full installation documented here assumes you want all 4 architectures working.

---

## 🔬 What is TRACE?

**TRACE (Toulmin-based Reasoning Assessment through Constructive Elements)** is a metric developed by Kim & Yang (ICML 2026) to evaluate the structural quality of an argument, based on **Toulmin's argumentation model** and **Flavell's metacognitive theory**.

### How it works

1. **Segmentation**: each speaker's text is split into sentences (spaCy, Spanish model `es_core_news_sm`).
2. **Multi-label classification**: each sentence is passed through a fine-tuned `DeBERTa-v3-base` model (`TraceDeBERTa`) that detects the presence of 8 constructive elements:
   - `Claim`
   - `Data/Evidence`
   - `Warrant` (reasoning connecting evidence to claim)
   - `Backing` (support for the warrant)
   - `Qualifier` (expression of certainty/uncertainty)
   - `Rebuttal` (counterargument)
   - `Monitoring` (self-checking, metacognition)
   - `Evaluation` (judgment on the quality of one's own reasoning)
3. **Score computation**: combines two weighted components (α = 0.7):

   ```
   TRACE = α · State Validity + (1 − α) · Transition Coherence
   ```

   - **State Validity**: does each sentence have an argumentatively valid combination of labels? (e.g. `Claim+Evaluation` is valid; an isolated `Qualifier` is weak)
   - **Transition Coherence**: do consecutive sentences flow well? (e.g. `Data/Evidence → Claim` is a "good" transition; repeated `Monitoring → Qualifier` indicates hesitation/rambling)

The result is a number between 0 and 1 — the higher it is, the sounder that speaker's argumentative structure.

> ⚠️ **Important**: TRACE evaluates **argumentative structure**, not factual correctness. A speaker may have a high TRACE score with incorrect data (reasons well but is wrong), or a low TRACE score with a correct conclusion (hesitant but right). That's why it's used as a **complement** to the judge LLM's evaluation, not a replacement.

**Original paper:** Kim, Y. & Yang, H. (2026). *TRACE: Toulmin-based Reasoning Assessment through Constructive Elements for LLM CoT Evaluation*. PMLR 306. [Model source code](https://github.com/hyyangkisti/trace)

---

## ✅ Requirements

- VPS with **Ubuntu 22.04+** (tested on Ubuntu, CPU-only, no GPU)
- Python 3.11+
- [OpenAI](https://platform.openai.com/) account and API Key (for Swarm mode)
- [Deepgram](https://deepgram.com/) account and API Key (for transcription + diarization, all architectures)
- [Google AI Studio](https://aistudio.google.com/) account and API Key (Gemini, used inside the Langflow flows for Chain/Tree/Graph)
- ~1GB of free disk space for the TRACE model weights
- `root` or `sudo` access on the VPS

---

## 🚀 Full installation (Ubuntu VPS)

### Step 1: Update the system and install base dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip git git-lfs
git lfs install
```

### Step 2: Create the project folder and clone the repository

```bash
mkdir -p /root/juez-wsdc
cd /root
git clone https://github.com/SEBCAS01/juez-wsdc.git
cd juez-wsdc
```

### Step 3: Create and activate the application's virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

> From this point on, every time you open a new SSH session to work on the project, you need to reactivate the environment with `source venv/bin/activate` (from within `/root/juez-wsdc`).

### Step 4: Install the application's dependencies

```bash
pip install -r requirements.txt
```

> `requirements.txt` includes an `--extra-index-url` line that automatically installs PyTorch's CPU wheels — no extra manual steps required.

### Step 5: Verify the TRACE model weights were downloaded via Git LFS

```bash
git lfs pull
ls -la models/trace/model.safetensors
```
It should be roughly 700MB. If it's only a few bytes, it's an unresolved LFS pointer — run `git lfs pull` again.

### Step 6: Install Langflow (in a **separate** virtual environment)

Langflow has a huge dependency tree (LangChain and dozens of integrations) that can cause conflicts if mixed with the app's environment. That's why it's installed in its **own venv**, independent from Streamlit's:

```bash
cd /root/juez-wsdc
python3 -m venv venv-langflow
source venv-langflow/bin/activate
pip install langflow
deactivate
```

Continue with the [Langflow flows configuration](#-langflow-flows-configuration) section before running the application for the first time.

---

## 🔑 API Keys configuration

There are **two completely separate key configuration systems** in this project — they don't mix or share a file:

### 1. Streamlit app keys (OpenAI + Deepgram)

```bash
mkdir -p ~/.streamlit
cp /root/juez-wsdc/secrets.toml.example ~/.streamlit/secrets.toml
nano ~/.streamlit/secrets.toml
```

It should look like this:
```toml
OPENAI_API_KEY = "sk-your-openai-key"
DEEPGRAM_API_KEY = "your-deepgram-key"
```

These two keys are automatically read by `app_juez.py` when Streamlit starts. They're required for **all** architectures (Deepgram) and specifically for Swarm mode (OpenAI).

### 2. Gemini key (used inside Langflow, for Chain/Tree/Graph)

This key **does not go in `secrets.toml`** — it's configured directly inside the Langflow interface, as detailed in the next section.

> ⚠️ **Never commit `secrets.toml` with your real keys to the repository.** `.gitignore` already excludes it by default.

---

## 🔧 Langflow flows configuration

Exported flows live in `langflow-flows/`:
```
langflow-flows/
├── chain_arquitectura_lineal.json
├── tree_arquitectura_arbol.json
└── graph_arquitectura_grafos.json
```

### Why this requires a manual step

Langflow **regenerates flow and component IDs every time a flow is imported** — there is no way to fix or preserve them across export/import ([officially documented limitation](https://github.com/langflow-ai/langflow/issues/5375)). This means the IDs hardcoded in `app_juez.py` (inside the `ARQUITECTURAS` dictionary) will become outdated as soon as you import the flows into your own instance, and **you must update them manually**.

### Steps

1. **Start Langflow** (see command in the next section) and open `http://<your-vps-ip>:7860` in your browser
2. Import each of the 3 `.json` files from `langflow-flows/` (**"Import"** button on the Projects page)
3. Configure your Gemini key as a **Global Variable**: profile → **Settings** → **Global Variables** → create a variable, e.g. `GEMINI_API_KEY`, with your Google AI Studio key
4. Open each of the 3 imported flows, locate the Gemini model component(s), and in the API key field select that Global Variable instead of pasting the literal key (this way you only configure it once for all 3 flows)
5. Inside each flow, copy:
   - The **Flow ID** (visible in the URL while editing the flow, e.g. `.../flow/<this-is-the-flow-id>`)
   - The **Diarizer component ID** (click the component → shown in its settings, format `ComponentName-XXXXX`)
   - The **Rubric reader component ID** (`ReadFile`, same format)
6. Open `app_juez.py` and replace the corresponding values in `ARQUITECTURAS`:

```python
ARQUITECTURAS = {
    "Arquitectura Lineal (Chain)": {
        "flow_id": "YOUR-NEW-FLOW-ID-HERE",
        "diarizador_id": "YOUR-NEW-DIARIZER-ID-HERE",
        "readfile_rubrica_id": "YOUR-NEW-READFILE-ID-HERE"
    },
    # ... repeat for Tree and Graph
}
```

7. Save the file and restart Streamlit (see next section)

---

## ▶️ Running the application

You need **two processes running in parallel**: Langflow and Streamlit. Each uses its own virtual environment.

### Start Langflow

```bash
cd /root/juez-wsdc
source venv-langflow/bin/activate
python -m langflow run --host 0.0.0.0 --port 7860
```
Langflow becomes available at `http://<your-vps-ip>:7860`.

### Start the Streamlit app (in another session/terminal)

```bash
cd /root/juez-wsdc
source venv/bin/activate
python -m streamlit run app_juez.py --server.port 8501 --server.address 0.0.0.0
```
The app becomes available at `http://<your-vps-ip>:8501`.

### Keep both running in the background (recommended for a VPS)

If you close the SSH session while the commands above are running directly, **the process stops**. Use `nohup` so they survive the terminal closing:

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

Verify both are running:
```bash
ps aux | grep -E "langflow|streamlit"
```

To stop them:
```bash
pkill -f "langflow run"
pkill -f "streamlit run app_juez.py"
```

---

## 🎧 Sample audios

The [`sample-audios/`](sample-audios/) folder contains example debate recordings to test the platform without needing your own recordings on hand. Upload them directly from the Streamlit interface to verify the installation works correctly end to end (transcription, diarization, TRACE, and final verdict).

---

## 📁 Project structure

```
juez-wsdc/
├── app_juez.py               # Main Streamlit interface
├── juez_swarm.py              # Multi-Agent (Swarm) mode logic + Deepgram + TRACE
├── trace_scorer.py             # TRACE wrapper for Swarm mode (per speaker)
├── trace_runner.py             # Standalone script to run TRACE from stdin
├── requirements.txt             # Streamlit app dependencies
├── secrets.toml.example         # API keys configuration template (Streamlit)
├── RUBRICA_1V1.txt              # Rubric for individual (1v1) debates
├── RUBRICA_EQUIPOS.txt          # Rubric for team debates
├── sample-audios/               # Sample audios to test the platform
├── langflow-flows/              # Exported Langflow flows (require re-configuring IDs, see above)
│   ├── chain_arquitectura_lineal.json
│   ├── tree_arquitectura_arbol.json
│   └── graph_arquitectura_grafos.json
├── models/
│   └── trace/                  # TRACE-DeBERTa model weights (Git LFS)
└── trace-module/
    ├── eval/
    │   ├── calculate.py         # State Validity / Transition Coherence computation
    │   ├── parser.py            # Sentence segmentation (spaCy, Spanish)
    │   └── inference.py         # TraceDeBERTa model inference
    └── main.py                  # Standalone CLI for the original TRACE framework
```

---

## 📊 Evaluation rubrics

The system supports two WSDC rubric formats:

- **`RUBRICA_1V1.txt`** — for individual (1v1) debates
- **`RUBRICA_EQUIPOS.txt`** — for team debates

Both rubrics score out of 100 total points:
- **Content**: 40 points
- **Style**: 40 points
- **Strategy**: 20 points

You can edit these files directly to adjust criteria without touching the code.

---

## 🛠️ Troubleshooting

### TRACE model fails to load / `local_files_only` error
Verify the weights were downloaded correctly via Git LFS:
```bash
git lfs pull
ls -la models/trace/model.safetensors  # should be ~700MB, not a few bytes
```

### `ModuleNotFoundError` for `calculate` or `parser`
These modules are imported dynamically by adding their path to `sys.path`. Confirm the path exists:
```bash
ls /root/juez-wsdc/trace-module/eval/
```
If your project isn't located at `/root/juez-wsdc/`, adjust the `TRACE_PATH` constant in `trace_scorer.py`.

### Spanish sentence segmentation fails
Install the Spanish spaCy model if it's not included:
```bash
python -m spacy download es_core_news_sm
```

### Deepgram/OpenAI authentication error
Confirm `~/.streamlit/secrets.toml` exists and has the correct format (see configuration section above). Also verify the Streamlit process was restarted after creating/editing the file.

### `torch==2.4.0+cpu` won't install
Make sure `requirements.txt` includes the line `--extra-index-url https://download.pytorch.org/whl/cpu` at the top of the file.

### Langflow and Streamlit stop when closing the SSH session
Use `nohup` for both processes (see "Keep both running in the background" section).

### "Flow not found" or "component not found" error in Chain/Tree/Graph
The IDs hardcoded in `ARQUITECTURAS` (`app_juez.py`) correspond to the original Langflow instance where the flows were created. If you imported the flows into a different instance, **you must update those IDs manually** — see [Langflow flows configuration](#-langflow-flows-configuration).

### Dependency conflicts between Langflow and the Streamlit app
If you installed both in the same virtual environment, you're very likely to run into version conflicts (Langflow brings its own version of `torch`, `transformers`, etc.). Use **two separate venvs** as described in the installation section (`venv/` for the app, `venv-langflow/` for Langflow).

---

## 📚 References

- Kim, Y. & Yang, H. (2026). *TRACE: Toulmin-based Reasoning Assessment through Constructive Elements for LLM CoT Evaluation*. PMLR 306.
- Toulmin, S. E. (2003). *The Uses of Argument*. Cambridge University Press.
- Flavell, J. H. (1979). *Metacognition and cognitive monitoring: A new area of cognitive-developmental inquiry*. American Psychologist, 34(10), 906.
- He, P., Gao, J., & Chen, W. (2023). *DeBERTaV3: Improving DeBERTa using ELECTRA-Style Pre-Training with Gradient-Disentangled Embedding Sharing*. ICLR.

---

## 📄 License

This project is for academic/research use. Adjust this section as appropriate for your institutional context.
