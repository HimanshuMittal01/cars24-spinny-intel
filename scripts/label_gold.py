"""Interactive helper for labeling gold listings.

Per-platform template selection:
- platform=cars24 -> gold_template_cars24.json
- platform=spinny -> gold_template_spinny.json

Workflow:
    uv run python scripts/label_gold.py list                 # show fixtures without labels
    uv run python scripts/label_gold.py <platform> <listing> # init a label file
    # operator edits eval/labels/<platform>/<listing_id>.json
    uv run python scripts/label_gold.py compile              # build eval/gold.jsonl
"""
import json
import sys
from pathlib import Path

from ci.config import EVAL_DIR, FIXTURES_DIR


def list_unlabeled() -> list[tuple[str, str]]:
    labels = EVAL_DIR / "labels"
    out = []
    for plat_dir in FIXTURES_DIR.iterdir():
        if not plat_dir.is_dir():
            continue
        for lid_dir in plat_dir.iterdir():
            if not lid_dir.is_dir():
                continue
            lab = labels / plat_dir.name / f"{lid_dir.name}.json"
            if not lab.exists():
                out.append((plat_dir.name, lid_dir.name))
    return out


def init_label(platform: str, listing_id: str) -> Path:
    if platform not in ("cars24", "spinny"):
        raise SystemExit(f"unsupported platform: {platform}")
    labels = EVAL_DIR / "labels" / platform
    labels.mkdir(parents=True, exist_ok=True)
    target = labels / f"{listing_id}.json"
    if not target.exists():
        tmpl_path = EVAL_DIR / f"gold_template_{platform}.json"
        tmpl = json.loads(tmpl_path.read_text())
        tmpl["listing_id"] = listing_id
        tmpl["platform"] = platform
        target.write_text(json.dumps(tmpl, indent=2))
    return target


def compile_jsonl() -> Path:
    labels = EVAL_DIR / "labels"
    out_path = EVAL_DIR / "gold.jsonl"
    rows = []
    if labels.exists():
        for plat_dir in labels.iterdir():
            if plat_dir.is_dir():
                for f in plat_dir.glob("*.json"):
                    rows.append(json.loads(f.read_text()))
    out_path.write_text("\n".join(json.dumps(r) for r in rows))
    print(f"wrote {len(rows)} records to {out_path}")
    return out_path


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "compile":
        compile_jsonl()
        return
    if len(sys.argv) == 2 and sys.argv[1] == "list":
        for plat, lid in list_unlabeled():
            print(f"{plat}/{lid}")
        return
    if len(sys.argv) == 3:
        plat, lid = sys.argv[1], sys.argv[2]
        path = init_label(plat, lid)
        print(f"label file: {path}")
        return
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    main()
