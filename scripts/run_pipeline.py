"""Run the end-to-end pipeline on the 6 ranking listings.

Reads ranking listing IDs from eval/ranking_listings.json (operator-provided).
Writes trace + ranking output under runs/<timestamp>/.
"""
import json
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

from ci.config import EVAL_DIR, RUNS_DIR
from ci.llm import AnthropicLLMClient
from ci.pipeline import run_pipeline


def main() -> None:
    load_dotenv()
    listings_file = EVAL_DIR / "ranking_listings.json"
    listings = [
        (d["platform"], d["listing_id"])
        for d in json.loads(listings_file.read_text())
    ]

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "-"
        + uuid.uuid4().hex[:6]
    )
    run_dir = RUNS_DIR / run_id

    client = AnthropicLLMClient()
    rows = run_pipeline(
        ranking_listings=listings,
        client=client,
        run_dir=run_dir,
    )
    out_path = run_dir / "ranking.json"
    out_path.write_text(json.dumps([r.model_dump() for r in rows], indent=2))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
