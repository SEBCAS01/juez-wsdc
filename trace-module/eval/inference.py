import os
from pathlib import Path
from typing import Dict, List, Optional, Union

import torch
import torch.nn as nn
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file
from transformers import AutoConfig, AutoModel, AutoTokenizer
from tqdm import tqdm


def _resolve_hf_token(token: Optional[str] = None) -> Optional[str]:
    return token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")


def _load_pretrained_kwargs(
    model_name_or_path: Union[str, Path],
    token: Optional[str] = None,
    local_files_only: bool = False,
) -> dict:
    kwargs = {"local_files_only": local_files_only}
    resolved = _resolve_hf_token(token)
    if resolved:
        kwargs["token"] = resolved
    return kwargs


class TraceDeBERTa(nn.Module):
    def __init__(self, config, num_labels=8):
        super().__init__()
        self.deberta = AutoModel.from_config(config)
        self.classifier = nn.Linear(config.hidden_size, num_labels)
    
    def forward(self, input_ids, attention_mask=None):
        outputs = self.deberta(input_ids=input_ids, attention_mask=attention_mask)
        return torch.sigmoid(self.classifier(outputs.last_hidden_state[:, 0, :]))


class TRACEInference:
    def __init__(
        self,
        model_name: str = "hyyangkisti/TRACE-DeBERTa-v3-base",
        device: str = None,
        token: Optional[str] = None,
        local_dir: Optional[Union[str, Path]] = None,
        local_files_only: bool = False,
    ):
        self.device = torch.device(device if device else ("cuda" if torch.cuda.is_available() else "cpu"))
        load_path = Path(local_dir) if local_dir else model_name
        hf_kwargs = _load_pretrained_kwargs(load_path, token=token, local_files_only=local_files_only)

        print(f"Loading {load_path} on {self.device}")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(load_path, **hf_kwargs)
            config = AutoConfig.from_pretrained(load_path, **hf_kwargs)
        except Exception as e:
            hint = (
                "\n\n[Hugging Face load failed]\n"
                "  - Private/gated model: huggingface-cli login  OR  set HF_TOKEN env var\n"
                "  - Local weights: pass local_dir=... with config.json, tokenizer files, model.safetensors\n"
                "  - Wrong repo id: confirm the model name on huggingface.co\n"
            )
            raise RuntimeError(f"Could not load tokenizer/config from {load_path}.{hint}") from e

        self.model = TraceDeBERTa(config)

        if local_dir:
            weights_path = Path(local_dir) / "model.safetensors"
            if not weights_path.exists():
                raise FileNotFoundError(f"model.safetensors not found in {local_dir}")
        else:
            download_kwargs = {"repo_id": model_name, "filename": "model.safetensors"}
            resolved_token = _resolve_hf_token(token)
            if resolved_token:
                download_kwargs["token"] = resolved_token
            weights_path = hf_hub_download(**download_kwargs)

        state_dict = {k: v for k, v in load_file(weights_path).items() if not k.startswith("pooler.")}
        self.model.load_state_dict(state_dict, strict=False)
        self.model.to(self.device).eval()
        
        self.labels = ["Claim", "Data/Evidence", "Warrant", "Backing", "Qualifier", "Rebuttal", "Monitoring", "Evaluation"]
        
    def predict(self, text: str) -> Dict[str, float]:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(self.device) for k, v in inputs.items() if k in ['input_ids', 'attention_mask']}
        with torch.no_grad():
            predictions = self.model(**inputs)
        return {label: float(score) for label, score in zip(self.labels, predictions[0])}
    
    def predict_batch(self, texts: List[str], batch_size: int = 32) -> List[Dict[str, float]]:
        all_results = []
        for i in tqdm(range(0, len(texts), batch_size), desc="Predicting", leave=False):
            inputs = self.tokenizer(texts[i:i + batch_size], return_tensors="pt", truncation=True, max_length=512, padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items() if k in ['input_ids', 'attention_mask']}
            with torch.no_grad():
                predictions = self.model(**inputs)
            all_results.extend([{label: float(score) for label, score in zip(self.labels, pred)} for pred in predictions])
        return all_results
