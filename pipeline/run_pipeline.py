import argparse
import json
import os
from typing import Any, List, Dict


def load_raw_insights(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected input JSON to be a list of insight objects")
    return data


def save_processed_insights(insights: List[Dict[str, Any]], output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "insights.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="SignalSynth pipeline: raw -> processed insights.json")
    parser.add_argument("--input", required=True, help="Path to raw scraped JSON from the scraper")
    parser.add_argument("--output-dir", default="data/processed", help="Directory to write processed outputs")
    args = parser.parse_args()

    raw_insights = load_raw_insights(args.input)

    # For now, we simply pass through the enriched insights from the scraper.
    # Later we can add deduping, collapsing, and clustering here.
    out_path = save_processed_insights(raw_insights, args.output_dir)
    print(f"[PIPELINE] Wrote {len(raw_insights)} insights to {out_path}")


if __name__ == "__main__":
    main()
