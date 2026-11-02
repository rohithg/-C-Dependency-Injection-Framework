from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LineageGraph:
    """Lightweight table/column lineage for run reports."""

    edges: list[dict] = field(default_factory=list)

    def add(
        self,
        source: str,
        target: str,
        columns: list[str] | None = None,
        transform: str = "",
    ) -> None:
        self.edges.append(
            {
                "source": source,
                "target": target,
                "columns": columns or [],
                "transform": transform,
            }
        )

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"edges": self.edges}, indent=2) + "\n", encoding="utf-8")
        return path
