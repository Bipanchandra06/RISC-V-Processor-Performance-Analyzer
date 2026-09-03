import json
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class CycleTrace:
    cycle: int; pc: int; stages: dict; instruction: int = 0; events: list[str] | None = None

class TraceRecorder:
    def __init__(self): self.cycles = []
    def record(self, cycle, pc, stages, instruction=0, events=None): self.cycles.append(CycleTrace(cycle, pc, stages, instruction, events or []))
    def write(self, path: Path): path.write_text(json.dumps([asdict(x) for x in self.cycles], indent=2))
