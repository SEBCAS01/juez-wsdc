import sys
import json

sys.path.insert(0, '/root/juez-wsdc/trace-module/eval')

from inference import TRACEInference
from calculate import binarize_predictions, calculate_trace_from_labels
from parser import SentenceParser
import re

MODEL_DIR = '/root/juez-wsdc/models/trace'

texto = sys.stdin.read()

turns = re.findall(r'Turno\s+\d+\s+-\s+SPEAKER_(\w+)\*\*:\s*"(.*?)"', texto, re.DOTALL)

por_hablante = {}
for speaker, texto_turno in turns:
    key = f"SPEAKER_{speaker}"
    if key not in por_hablante:
        por_hablante[key] = []
    por_hablante[key].append(texto_turno.strip())

parser = SentenceParser()
model = TRACEInference(local_dir=MODEL_DIR, local_files_only=True)

resultado = {}
for speaker, turnos in por_hablante.items():
    texto_completo = " ".join(turnos)
    oraciones = parser.parse(texto_completo)
    if not oraciones:
        resultado[speaker] = {"trace_score": 0.0, "num_sentences": 0}
        continue

    preds = model.predict_batch(oraciones)
    binarios = [binarize_predictions(p) for p in preds]
    score = calculate_trace_from_labels(binarios)

    conteo = {}
    for b in binarios:
        for label, val in b.items():
            if val == 1:
                conteo[label] = conteo.get(label, 0) + 1

    resultado[speaker] = {
        "trace_score": round(score, 4),
        "num_sentences": len(oraciones),
        "label_counts": conteo
    }

print(json.dumps(resultado, indent=2, ensure_ascii=False))
