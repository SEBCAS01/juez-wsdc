"""
trace_scorer.py

Wrapper de TRACE para juez_swarm.py, reutilizando EXACTAMENTE los mismos
módulos y pesos que ya usa el custom component de Langflow
(TRACEDebateComponent):

  - /root/juez-wsdc/trace-module/eval/calculate.py  -> binarize_predictions, calculate_trace_from_labels
  - /root/juez-wsdc/trace-module/eval/parser.py     -> SentenceParser
  - /root/juez-wsdc/models/trace/                  -> tokenizer, config, model.safetensors

No descarga nada de HuggingFace Hub ni reimplementa las fórmulas: llama a
tu propio código ya validado en producción.
"""

import sys
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoConfig, AutoModel
from safetensors.torch import load_file

# ==========================================
# 1. RUTAS (idénticas a las del custom component de Langflow)
# ==========================================
TRACE_PATH = "/root/juez-wsdc/trace-module/eval"
MODEL_DIR = "/root/juez-wsdc/models/trace"

if TRACE_PATH not in sys.path:
    sys.path.insert(0, TRACE_PATH)

from calculate import binarize_predictions, calculate_trace_from_labels  # noqa: E402
from parser import SentenceParser  # noqa: E402

LABELS = ["Claim", "Data/Evidence", "Warrant", "Backing",
          "Qualifier", "Rebuttal", "Monitoring", "Evaluation"]


# ==========================================
# 2. DEFINICIÓN DEL MODELO (idéntica a la del custom component)
# ==========================================
class TraceDeBERTa(nn.Module):
    def __init__(self, config, num_labels=8):
        super().__init__()
        self.deberta = AutoModel.from_config(config)
        self.classifier = nn.Linear(config.hidden_size, num_labels)

    def forward(self, input_ids, attention_mask=None):
        outputs = self.deberta(input_ids=input_ids, attention_mask=attention_mask)
        return torch.sigmoid(self.classifier(outputs.last_hidden_state[:, 0, :]))


# ==========================================
# 3. CARGA PEREZOSA (una sola vez por proceso, no por request)
# ==========================================
_tokenizer = None
_model = None
_parser = None


def _cargar_recursos():
    global _tokenizer, _model, _parser

    if _parser is None:
        _parser = SentenceParser()

    if _tokenizer is None or _model is None:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
        config = AutoConfig.from_pretrained(MODEL_DIR, local_files_only=True)

        modelo = TraceDeBERTa(config)
        weights_path = f"{MODEL_DIR}/model.safetensors"
        state_dict = {k: v for k, v in load_file(weights_path).items() if not k.startswith("pooler.")}
        modelo.load_state_dict(state_dict, strict=False)
        modelo.eval()

        _model = modelo


# ==========================================
# 4. FUNCIÓN PÚBLICA (misma interfaz que espera juez_swarm.py)
# ==========================================
def analizar_toulmin(texto_razonamiento):
    """
    Ejecuta el mismo pipeline TRACE que el custom component de Langflow,
    pero sobre un bloque de texto único (transcripción completa del swarm,
    sin separación por hablante).
    """
    try:
        _cargar_recursos()

        if not texto_razonamiento or texto_razonamiento.strip() == "":
            return {"trace_score": 0.0, "num_sentences": 0, "label_train": []}

        oraciones = _parser.parse(texto_razonamiento)
        if not oraciones:
            return {"trace_score": 0.0, "num_sentences": 0, "label_train": []}

        all_preds = []
        for oracion in oraciones:
            enc = _tokenizer(oracion, return_tensors="pt", truncation=True, max_length=512)
            enc = {k: v for k, v in enc.items() if k in ["input_ids", "attention_mask"]}
            with torch.no_grad():
                preds = _model(**enc)
            all_preds.append({label: float(score) for label, score in zip(LABELS, preds[0])})

        binarios = [binarize_predictions(p) for p in all_preds]
        score = calculate_trace_from_labels(binarios)

        conteo = {}
        for b in binarios:
            for label, val in b.items():
                if val == 1:
                    conteo[label] = conteo.get(label, 0) + 1

        label_train = []
        for oracion, b in zip(oraciones, binarios):
            etiquetas_activas = [label for label, val in b.items() if val == 1]
            label_train.append({"sentence": oracion, "labels": etiquetas_activas})

        return {
            "trace_score": round(float(score), 4),
            "num_sentences": len(oraciones),
            "label_counts": dict(sorted(conteo.items(), key=lambda x: x[1], reverse=True)),
            "label_train": label_train,
        }

    except Exception as e:
        import traceback
        return {
            "trace_score": None,
            "error": f"{str(e)}\n{traceback.format_exc()}",
            "label_train": [],
            "num_sentences": 0,
        }


def analizar_toulmin_por_hablante(texto_por_hablante):
    """
    Ejecuta analizar_toulmin() para cada hablante por separado.
    texto_por_hablante: dict {"SPEAKER_0": "texto...", "SPEAKER_1": "texto...", ...}
    Devuelve: dict {"SPEAKER_0": resultado_trace, ...}
    """
    resultado = {}
    for speaker, texto in texto_por_hablante.items():
        resultado[speaker] = analizar_toulmin(texto)
    return resultado


def formatear_reporte_trace_por_hablante(resultado_por_hablante):
    """Convierte el dict de analizar_toulmin_por_hablante() en un reporte Markdown."""
    if not resultado_por_hablante:
        return "⚠️ No se detectaron hablantes distintos en la transcripción."

    secciones = []
    for speaker, resultado in resultado_por_hablante.items():
        secciones.append(f"### 🎤 {speaker}\n{formatear_reporte_trace(resultado)}")
    return "\n\n".join(secciones)


def formatear_reporte_trace(resultado_trace):
    """Convierte el resultado de analizar_toulmin() en un reporte Markdown legible."""
    if resultado_trace.get("trace_score") is None:
        return f"⚠️ No se pudo calcular TRACE: {resultado_trace.get('error', 'error desconocido')}"

    lineas = [
        f"**TRACE Score:** {resultado_trace['trace_score']:.4f}",
        f"- Oraciones analizadas: {resultado_trace['num_sentences']}",
    ]

    if resultado_trace.get("label_counts"):
        lineas.append("- Distribución de elementos constructivos:")
        for label, count in resultado_trace["label_counts"].items():
            lineas.append(f"  - {label}: {count}")

    lineas.append("")
    lineas.append("**Detalle por oración:**")
    for item in resultado_trace.get("label_train", []):
        etiquetas = ", ".join(item["labels"]) if item["labels"] else "(sin etiqueta)"
        texto_corto = item["sentence"][:80] + "..." if len(item["sentence"]) > 80 else item["sentence"]
        lineas.append(f'  - "{texto_corto}" → [{etiquetas}]')

    return "\n".join(lineas)
