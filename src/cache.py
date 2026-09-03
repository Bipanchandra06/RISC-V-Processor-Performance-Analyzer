from dataclasses import dataclass

@dataclass
class CacheStats:
    accesses: int = 0; hits: int = 0; misses: int = 0
    def report(self): return {"accesses": self.accesses, "hits": self.hits, "misses": self.misses, "hit_rate": round(self.hits / self.accesses, 4) if self.accesses else 1.0}

class SetAssociativeCache:
    def __init__(self, size=256, block_size=16, associativity=1):
        if size <= 0 or block_size <= 0 or associativity <= 0: raise ValueError("Cache parameters must be positive")
        self.block_size, self.ways = block_size, associativity
        self.sets = max(1, size // block_size // associativity); self.lines = [[] for _ in range(self.sets)]; self.stats = CacheStats()
    def access(self, address: int, write=False) -> bool:
        if address < 0: raise ValueError(f"Invalid cache address: {address}")
        self.stats.accesses += 1; block = address // self.block_size; bucket = self.lines[block % self.sets]
        hit = block in bucket
        if hit: self.stats.hits += 1; bucket.remove(block)
        else:
            self.stats.misses += 1
            if len(bucket) >= self.ways: bucket.pop(0)
        bucket.append(block); return hit
