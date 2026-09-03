"""Configurable instruction/data cache models for the RISC-V Observatory."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Literal

CacheType = Literal["direct", "set-associative", "fully-associative"]
ReplacementPolicy = Literal["lru", "fifo"]

@dataclass
class CacheConfig:
    cache_type: CacheType = "direct"
    capacity_bytes: int = 256
    block_size_bytes: int = 16
    associativity: int = 1
    replacement_policy: ReplacementPolicy = "lru"
    hit_latency: int = 1
    miss_penalty: int = 20
    memory_latency: int = 100

    def __post_init__(self):
        if self.cache_type not in {"direct", "set-associative", "fully-associative"}:
            raise ValueError("cache_type must be direct, set-associative, or fully-associative")
        if self.replacement_policy not in {"lru", "fifo"}:
            raise ValueError("replacement_policy must be lru or fifo")
        if self.capacity_bytes <= 0 or self.block_size_bytes <= 0:
            raise ValueError("Cache capacity and block size must be positive")
        if self.capacity_bytes % self.block_size_bytes:
            raise ValueError("Cache capacity must be divisible by block size")
        if self.hit_latency <= 0 or self.miss_penalty < 0 or self.memory_latency < 0:
            raise ValueError("Hit latency must be positive; penalties cannot be negative")
        lines = self.capacity_bytes // self.block_size_bytes
        if self.cache_type == "direct" and self.associativity != 1:
            raise ValueError("Direct-mapped caches must have associativity 1")
        if self.cache_type == "fully-associative" and self.associativity != 1:
            raise ValueError("Fully-associative caches use associativity 1")
        if self.cache_type == "set-associative" and (self.associativity <= 1 or lines % self.associativity):
            raise ValueError("Set-associative cache requires a valid associativity that divides its line count")

    @property
    def line_count(self): return self.capacity_bytes // self.block_size_bytes
    @property
    def set_count(self): return 1 if self.cache_type == "fully-associative" else (self.line_count if self.cache_type == "direct" else self.line_count // self.associativity)
    @property
    def ways(self): return 1 if self.cache_type == "direct" else (self.line_count if self.cache_type == "fully-associative" else self.associativity)
    def report(self):
        result = asdict(self)
        result.update({"line_count": self.line_count, "set_count": self.set_count, "ways": self.ways})
        return result

@dataclass
class CacheAccessResult:
    hit: bool
    penalty_cycles: int
    set_index: int
    tag: int
    block_number: int
    evicted_block: int | None
    access_type: str

@dataclass
class CacheStats:
    accesses: int = 0; hits: int = 0; misses: int = 0; evictions: int = 0; penalty_cycles: int = 0
    events: list[dict] = field(default_factory=list)
    def report(self):
        return {"accesses": self.accesses, "hits": self.hits, "misses": self.misses, "evictions": self.evictions,
                "penalty_cycles": self.penalty_cycles, "hit_rate": round(self.hits / self.accesses, 4) if self.accesses else 1.0,
                "events": self.events}

class Cache:
    """Tag-only cache; functional bytes remain in InstructionMemory/DataMemory."""
    def __init__(self, config: CacheConfig):
        self.config = config; self.stats = CacheStats(); self.lines = [[] for _ in range(config.set_count)]; self.current_cycle = None
    def reset(self): self.lines = [[] for _ in range(self.config.set_count)]; self.stats = CacheStats()
    def report(self):
        result = self.stats.report()
        result["configuration"] = self.config.report()
        return result
    def access(self, address: int, access_type: str = "data", write: bool = False) -> CacheAccessResult:
        if address < 0: raise ValueError(f"Invalid cache address: {address}")
        self.stats.accesses += 1
        block = address // self.config.block_size_bytes
        set_index = 0 if self.config.cache_type == "fully-associative" else block % self.config.set_count
        tag = block // self.config.set_count; bucket = self.lines[set_index]; hit = block in bucket; evicted = None
        if hit:
            self.stats.hits += 1
            if self.config.replacement_policy == "lru": bucket.remove(block); bucket.append(block)
        else:
            self.stats.misses += 1
            if len(bucket) >= self.config.ways: evicted = bucket.pop(0); self.stats.evictions += 1
            bucket.append(block)
        penalty = max(0, self.config.hit_latency - 1)
        if not hit: penalty += self.config.miss_penalty + self.config.memory_latency
        self.stats.penalty_cycles += penalty
        result = CacheAccessResult(hit, penalty, set_index, tag, block, evicted, access_type)
        event = asdict(result); event["cycle"] = self.current_cycle; event["write"] = write; self.stats.events.append(event)
        return result

class SetAssociativeCache(Cache):
    """Backward-compatible wrapper for the previous cache class."""
    def __init__(self, size=256, block_size=16, associativity=1):
        super().__init__(CacheConfig("direct" if associativity == 1 else "set-associative", size, block_size, associativity))
