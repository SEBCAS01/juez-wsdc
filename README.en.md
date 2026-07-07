# ⚖️ Juez WSDC — Automated WSDC Debate Evaluation System

Automated evaluation platform for debates in the **WSDC (World Schools Debating Championship)** format. The system processes audio recordings, transcribes and diarizes the debate by speaker, evaluates argumentative quality using a specialized model (**TRACE**), and generates an official verdict using generative AI applying the WSDC rubric.

> 🇪🇸 Léelo en español: [README.md](README.md)

---

## 📋 Table of contents

- [General architecture](#-general-architecture)
- [Available evaluation architectures](#-available-evaluation-architectures)
- [What is TRACE?](#-what-is-trace)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [API Keys configuration](#-api-keys-configuration)
- [Running the application](#-running-the-application)
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

---

## 🧠 Available evaluation architectures

The interface lets you choose between 4 evaluation "brains":

| Architecture | Engine | Description |
|---|---|---|
| **Chain** | Langflow | Simple linear evaluation pipeline |
| **Tree** | Langflow | Hierarchical evaluation across criterion branches |
| **Graph** | Langflow | Evaluation with cross-dependencies between criteria |
| **Multi-Agent (Swarm)** | OpenAI Swarm | 3 specialized GPT-4o agents (Argumentation, Style, Head Judge) that collaborate and hand off control to each other |

The first three run on top of **Langflow** (requires it to be deployed and reachable via its API — see `url_langflow` in the app sidebar). The fourth (**Swarm**) runs entirely within this Streamlit application, with no external Langflow dependency.

### ⚠️ Required setup for Chain/Tree/Graph (Langflow)

Unlike Swarm mode, the 3 Langflow architectures **do not work immediately after cloning the repo** — they require an extra manual step due to a known Langflow limitation.

Exported flows live in `langflow-flows/`:
```
langflow-flows/
├── chain_arquitectura_lineal.json
├── tree_arquitectura_arbol.json
└── graph_arquitectura_grafos.json
```

**Why importing alone isn't enough:** Langflow **regenerates flow and component IDs every time a flow is imported** — there is no way to fix or preserve them across export/import ([officially documented limitation](https://github.com/langflow-ai/langflow/issues/5375)). This means the IDs hardcoded in `app_juez.py` (inside the `ARQUITECTURAS` dictionary) will become outdated as soon as you import the flows into your own instance.

**Steps to get it working:**

1. Open your Langflow instance
2. Import each of the 3 `.json` files from `langflow-flows/` (**"Import"** button on the Projects page)
3. Open each imported flow and copy:
   - The **Flow ID** (visible in the URL while editing the flow, e.g. `.../flow/<this-is-the-flow-id>`)
   - The **Diarizer component ID** (click the component → shown in its settings, format `ComponentName-XXXXX`)
   - The **Rubric reader component ID** (`ReadFile`, same format)
4. Open `app_juez.py` and replace the corresponding values in `ARQUITECTURAS`:

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

5. Restart Streamlit for the changes to take effect

**Additionally**, these 3 flows use **Google Gemini** for the final evaluation, configured *inside* Langflow (not in Streamlit's `secrets.toml`, which is a separate configuration system). After importing the flows:

6. In Langflow, go to your profile → **Settings** → **Global Variables** → create a variable, e.g. `GEMINI_API_KEY`, with your Google AI Studio key
7. Open each of the 3 imported flows, locate the Gemini model component(s), and in the API key field select that Global Variable instead of pasting the literal key (this way you only configure it once for all 3 flows)

> 💡 If you're only interested in **Swarm** mode, you can skip this section entirely — it works without any Langflow or Gemini configuration.

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

- Python 3.11+
- [OpenAI](https://platform.openai.com/) account and API Key (for Swarm mode)
- [Deepgram](https://deepgram.com/) account and API Key (for transcription + diarization, all architectures)
- A deployed and reachable [Langflow](https://www.langflow.org/) instance, if using the Chain/Tree/Graph architectures — these also require a [Google AI Studio](https://aistudio.google.com/) (Gemini) API Key, configured inside Langflow
- ~1GB of free disk space for the TRACE model weights

---

## 🚀 Installation

```bash
# 1. Clone the repository (includes TRACE weights via Git LFS)
git lfs install
git clone https://github.com/SEBCAS01/juez-wsdc.git
cd juez-wsdc

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

> `requirements.txt` includes an `--extra-index-url` entry to automatically install PyTorch's CPU wheels — no extra manual steps required.

---

## 🔑 API Keys configuration

Copy the configuration template and fill it in with your own keys:

```bash
mkdir -p ~/.streamlit
cp secrets.toml.example ~/.streamlit/secrets.toml
nano ~/.streamlit/secrets.toml
```

It should look like this:
```toml
OPENAI_API_KEY = "sk-your-openai-key"
DEEPGRAM_API_KEY = "your-deepgram-key"
```

> ⚠️ **Never commit `secrets.toml` with your real keys to the repository.** `.gitignore` already excludes it by default.

---

## ▶️ Running the application

```bash
source venv/bin/activate
python -m streamlit run app_juez.py --server.port 8501 --server.address 0.0.0.0
```

Open your browser at `http://localhost:8501` (or `http://<your-server-ip>:8501` if running on a VPS).

### Keeping it running in the background (VPS)

```bash
nohup python -m streamlit run app_juez.py --server.port 8501 --server.address 0.0.0.0 > streamlit.log 2>&1 &
```

---

## 📁 Project structure

```
juez-wsdc/
├── app_juez.py               # Main Streamlit interface
├── juez_swarm.py              # Multi-Agent (Swarm) mode logic + Deepgram + TRACE
├── trace_scorer.py             # TRACE wrapper for Swarm mode (per speaker)
├── trace_runner.py             # Standalone script to run TRACE from stdin
├── requirements.txt             # Project dependencies
├── secrets.toml.example         # API keys configuration template
├── RUBRICA_1V1.txt              # Rubric for individual (1v1) debates
├── RUBRICA_EQUIPOS.txt          # Rubric for team debates
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
If the file is only a few hundred bytes, it's an unresolved LFS pointer — run `git lfs pull` again.

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
Make sure `requirements.txt` includes the line `--extra-index-url https://download.pytorch.org/whl/cpu` at the top of the file. Without this, pip can't find PyTorch's CPU-only wheels.

### Streamlit stops when closing the SSH session
Run the process with `nohup` (see "Running the application" section) so it survives the terminal closing.

### "Flow not found" or "component not found" error in Chain/Tree/Graph
The IDs hardcoded in `ARQUITECTURAS` (`app_juez.py`) correspond to the original Langflow instance where the flows were created. If you imported the flows into a different instance, **you must update those IDs manually** — see the [Required setup for Chain/Tree/Graph](#-available-evaluation-architectures) section above.

---

## 📚 References

- Kim, Y. & Yang, H. (2026). *TRACE: Toulmin-based Reasoning Assessment through Constructive Elements for LLM CoT Evaluation*. PMLR 306.
- Toulmin, S. E. (2003). *The Uses of Argument*. Cambridge University Press.
- Flavell, J. H. (1979). *Metacognition and cognitive monitoring: A new area of cognitive-developmental inquiry*. American Psychologist, 34(10), 906.
- He, P., Gao, J., & Chen, W. (2023). *DeBERTaV3: Improving DeBERTa using ELECTRA-Style Pre-Training with Gradient-Disentangled Embedding Sharing*. ICLR.

---

## 📄 License

This project is for academic/research use. Adjust this section as appropriate for your institutional context.
