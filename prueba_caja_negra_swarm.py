import time
import os
import toml
from juez_swarm import ejecutar_evaluacion_swarm

secrets = toml.load(os.path.expanduser("~/.streamlit/secrets.toml"))
api_key_openai = secrets["OPENAI_API_KEY"]
api_key_deepgram = secrets["DEEPGRAM_API_KEY"]

inicio = time.time()
resultado = ejecutar_evaluacion_swarm(
    "/root/juez-wsdc/sample-audios/debate_final.mp3",
    "/root/juez-wsdc/RUBRICA_EQUIPOS.txt",
    api_key_openai,
    api_key_deepgram,
)
tiempo_total = time.time() - inicio

with open("/root/juez-wsdc/resultado_caja_negra_swarm.txt", "w", encoding="utf-8") as f:
    f.write(f"TIEMPO TOTAL: {tiempo_total:.2f} segundos\n\n")
    f.write(resultado)

print(f"Listo. Tiempo: {tiempo_total:.2f}s")
