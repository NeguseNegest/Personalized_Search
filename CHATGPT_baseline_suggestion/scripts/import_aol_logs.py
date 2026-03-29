from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.config import BASE_DIR


def normalize_domain(click_url: str | None) -> str | None:
    if not click_url:
        return None
    value = click_url.strip().lower()
    value = value.replace("http://", "").replace("https://", "")
    return value.split("/")[0] if value else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to AOL CSV file")
    parser.add_argument("--output", default=str(BASE_DIR / "data" / "interactions_from_aol.jsonl"))
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with input_path.open("r", encoding="utf-8", newline="") as fin, output_path.open("w", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        for row in reader:
            if count >= args.limit:
                break

            query = (row.get("Query") or "").strip()
            if not query:
                continue

            item_rank = (row.get("ItemRank") or "").strip()
            clicked = bool(item_rank)
            clicked_domain = normalize_domain(row.get("ClickURL"))

            normalized = {
                "user_id": str((row.get("AnonID") or "").strip()),
                "query": query,
                "timestamp": (row.get("QueryTime") or "").strip(),
                "clicked": clicked,
                "clicked_rank": int(item_rank) if item_rank.isdigit() else None,
                "clicked_domain": clicked_domain,
                "source": "aol",
            }

            fout.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            count += 1

    print(f"Wrote {count} normalized interactions to {output_path}")


if __name__ == "__main__":
    main()
