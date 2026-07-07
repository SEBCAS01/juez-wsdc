import argparse
from pathlib import Path

from src.util import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="TRACE: score reasoning samples from a JSONL file"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to JSONL input (e.g. dataset/sample.jsonl). "
             "Each line must be a JSON object with 'id' and 'think' fields.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to write {input_stem}.json (default: output)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="hyyangkisti/TRACE-DeBERTa-v3-base",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="cuda | cpu (default: auto)",
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    payload = run_pipeline(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        model_name=args.model,
        device=args.device,
        threshold=args.threshold,
        batch_size=args.batch_size,
    )

    out_path = Path(args.output_dir) / f"{Path(args.input).stem}.json"
    print(f"\nSaved {payload['total_samples']} sample(s) to {out_path}")
    print(f"Mean TRACE score: {payload['mean_score']:.4f}")


if __name__ == "__main__":
    main()
