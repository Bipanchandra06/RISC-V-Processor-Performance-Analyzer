import json
from pathlib import Path

def write_report(path: Path, cores: dict, predictors=None, caches=None, trace=None, traces=None):
    payload = {"project": "RISC-V Pipeline Observatory", "cores": cores,
               "predictors": predictors or {}, "caches": caches or {},
               "trace_cycles": len(trace.cycles) if trace else 0,
               "traces": {name: [x.__dict__ for x in recorder.cycles] for name, recorder in (traces or {}).items()}}
    path.write_text(json.dumps(payload, indent=2))
    return payload
