from dataclasses import dataclass, field

@dataclass
class BranchPredictor:
    mode: str = "always-not-taken"
    table: dict[int, int] = field(default_factory=dict)
    predictions: int = 0
    mispredictions: int = 0
    branches: int = 0

    def predict(self, pc: int) -> bool:
        self.predictions += 1
        if self.mode == "always-taken": return True
        if self.mode == "always-not-taken": return False
        return (self.table.get(pc, 1) >= 2) if self.mode == "two-bit" else bool(self.table.get(pc, 0))

    def update(self, pc: int, taken: bool, predicted: bool | None = None) -> None:
        self.branches += 1
        if (self.predict(pc) if predicted is None else predicted) != taken: self.mispredictions += 1
        if self.mode == "one-bit": self.table[pc] = int(taken)
        elif self.mode == "two-bit": self.table[pc] = max(0, min(3, self.table.get(pc, 1) + (1 if taken else -1)))

    def report(self) -> dict:
        return {"mode": self.mode, "branches": self.branches, "predictions": self.predictions,
                "mispredictions": self.mispredictions,
                "accuracy": round((self.branches - self.mispredictions) / self.branches, 4) if self.branches else 1.0}
