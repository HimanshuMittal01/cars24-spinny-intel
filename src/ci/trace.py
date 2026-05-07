import json
from pathlib import Path
from typing import Iterator

from ci.schemas import TraceEvent


class TraceStore:
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.run_dir / "trace.jsonl"

    def write(self, event: TraceEvent) -> None:
        with self.path.open("a") as f:
            f.write(event.model_dump_json())
            f.write("\n")

    def read(self) -> Iterator[TraceEvent]:
        if not self.path.exists():
            return
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    yield TraceEvent.model_validate_json(line)
