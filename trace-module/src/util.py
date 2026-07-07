import json
from pathlib import Path
from typing import Any, Dict, List

from tqdm import tqdm

from eval.calculate import binarize_predictions, calculate_trace_from_labels
from eval.inference import TRACEInference
from eval.parser import SentenceParser


def _active_labels(binary: Dict[str, int]) -> List[str]:
    """Return the sorted list of labels with value 1; empty list if none."""
    return sorted(label for label, value in binary.items() if value == 1)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read a JSONL file. Each non-empty line must be a JSON object."""
    samples: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_no} of {path}: {e}") from e
    return samples


def label_reasoning(
    sample: Dict[str, Any],
    inference_model: TRACEInference,
    sentence_parser: SentenceParser,
    threshold: float = 0.5,
    batch_size: int = 32,
) -> Dict[str, Any]:
    """Label one reasoning sample and compute its TRACE score."""
    sample_id = sample.get("id")
    text = sample.get("think", "") or ""

    sentences = sentence_parser.parse(text)
    if not sentences:
        return {
            "id": sample_id,
            "label": [],
            "num_sentences": 0,
            "score": 0.0,
        }

    raw_predictions = inference_model.predict_batch(sentences, batch_size=batch_size)
    binary_predictions = [
        binarize_predictions(p, threshold=threshold) for p in raw_predictions
    ]
    trace_score = calculate_trace_from_labels(binary_predictions)

    return {
        "id": sample_id,
        "label": [
            {sent: _active_labels(binary)}
            for sent, binary in zip(sentences, binary_predictions)
        ],
        "num_sentences": len(sentences),
        "score": round(trace_score, 6),
    }


def run_pipeline(
    input_path: Path,
    output_dir: Path = Path("output"),
    model_name: str = "hyyangkisti/TRACE-DeBERTa-v3-base",
    device: str = None,
    threshold: float = 0.5,
    batch_size: int = 32,
) -> Dict[str, Any]:
    """
    Run the TRACE labeling + scoring pipeline.

    Reads `input_path` (a JSONL file with 'id' and 'think' fields per line)
    and writes `{output_dir}/{input_stem}.json` with structure:

        {
          "results": [ {id, label, num_sentences, score}, ... ],
          "total_samples": int,
          "mean_score": float
        }
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}.json"

    samples = load_jsonl(input_path)
    if not samples:
        raise ValueError(f"No samples found in {input_path}")

    sentence_parser = SentenceParser()
    inference_model = TRACEInference(model_name=model_name, device=device)

    results: List[Dict[str, Any]] = []
    for sample in tqdm(samples, desc="Scoring", unit="sample"):
        result = label_reasoning(
            sample,
            inference_model=inference_model,
            sentence_parser=sentence_parser,
            threshold=threshold,
            batch_size=batch_size,
        )
        results.append(result)

    scored = [r for r in results if r["num_sentences"] > 0]
    mean_score = (
        sum(r["score"] for r in scored) / len(scored)
        if scored
        else 0.0
    )

    payload = {
        "results": results,
        "total_samples": len(results),
        "mean_score": round(mean_score, 6),
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return payload
