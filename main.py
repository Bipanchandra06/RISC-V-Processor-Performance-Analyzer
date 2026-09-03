import argparse
from pathlib import Path

from loguru import logger

from src.assembler import assemble, words_to_imem
from src.cache import Cache, CacheConfig
from src.core import SingleStageCore, FiveStageCore
from src.generate_metrics import generate_metrics
from src.memory import InstructionMemory, DataMemory
from src.predictor import BranchPredictor
from src.report import write_report


def build_parser():
    parser = argparse.ArgumentParser(description="MicroTrace: RV32I pipeline and cache simulator")
    parser.add_argument("--iodir", default="iodir", help="Directory containing input files")
    parser.add_argument("--mode", choices=["ss", "fs", "both"], default="both")
    parser.add_argument("--asm-file")
    parser.add_argument("--predictor", choices=["always-not-taken", "always-taken", "one-bit", "two-bit"], default="always-not-taken")
    parser.add_argument("--cache", action="store_true", help="Enable both instruction and data caches")
    parser.add_argument("--instruction-cache", action="store_true")
    parser.add_argument("--data-cache", action="store_true")
    parser.add_argument("--cache-type", choices=["direct", "set-associative", "fully-associative"], default="direct")
    parser.add_argument("--associativity", type=int, default=2)
    parser.add_argument("--replacement", choices=["lru", "fifo"], default="lru")
    parser.add_argument("--cache-size", type=int, default=256)
    parser.add_argument("--block-size", type=int, default=16)
    parser.add_argument("--hit-latency", type=int, default=1)
    parser.add_argument("--miss-penalty", type=int, default=20)
    parser.add_argument("--memory-latency", type=int, default=100)
    parser.add_argument("--report")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    io_dir = Path(args.iodir)
    if args.asm_file:
        if not (io_dir / "dmem.txt").exists():
            raise FileNotFoundError(f"{io_dir} must contain dmem.txt when using --asm-file")
        program = assemble(Path(args.asm_file).read_text())
        (io_dir / "imem.txt").write_text(words_to_imem(program.words))
    elif not (io_dir / "imem.txt").exists() or not (io_dir / "dmem.txt").exists():
        raise FileNotFoundError(f"{io_dir} must contain imem.txt and dmem.txt")

    cache_enabled = args.cache or args.instruction_cache or args.data_cache
    use_i_cache = args.cache or args.instruction_cache
    use_d_cache = args.cache or args.data_cache
    cache_config = None
    if cache_enabled:
        associativity = 1 if args.cache_type in {"direct", "fully-associative"} else args.associativity
        cache_config = CacheConfig(args.cache_type, args.cache_size, args.block_size, associativity,
                                   args.replacement, args.hit_latency, args.miss_penalty, args.memory_latency)

    def new_cache(enabled):
        return Cache(CacheConfig(**cache_config.__dict__)) if enabled else None

    ss_imem = InstructionMemory("ImemSS", io_dir, new_cache(use_i_cache))
    fs_imem = InstructionMemory("ImemFS", io_dir, new_cache(use_i_cache))
    ss_dmem = DataMemory("SS", io_dir, new_cache(use_d_cache))
    fs_dmem = DataMemory("FS", io_dir, new_cache(use_d_cache))
    ss_core = SingleStageCore(io_dir, ss_imem, ss_dmem)
    fs_core = FiveStageCore(io_dir, fs_imem, fs_dmem)
    ss_core.predictor = BranchPredictor(args.predictor)
    fs_core.predictor = BranchPredictor(args.predictor)

    while True:
        if args.mode in ("ss", "both") and not ss_core.halted: ss_core.step()
        if args.mode in ("fs", "both") and not fs_core.halted: fs_core.step()
        if (args.mode not in ("ss", "both") or ss_core.halted) and (args.mode not in ("fs", "both") or fs_core.halted): break

    if args.mode in ("ss", "both"): ss_dmem.output_data_memory()
    if args.mode in ("fs", "both"): fs_dmem.output_data_memory()
    if args.mode in ("ss", "both"): generate_metrics("w", "Single Stage Core Performance Metrics", ss_core.cycle, ss_core.cycle - 1, io_dir)
    if args.mode in ("fs", "both"): generate_metrics("a" if args.mode == "both" else "w", "Five Stage Core Performance Metrics", fs_core.cycle, fs_core.cycle - 1, io_dir)

    if args.report:
        cores = {}
        for name, core in (("single_stage", ss_core), ("five_stage", fs_core)):
            if name == "single_stage" and args.mode not in ("ss", "both"): continue
            if name == "five_stage" and args.mode not in ("fs", "both"): continue
            retired = core.retired_instructions
            penalty = core.cache_penalty_cycles()
            base_cycles = core.cycle
            effective_cycles = base_cycles + penalty
            cores[name] = {
                "cycles": base_cycles, "instructions": max(0, base_cycles - 1), "cpi": round(base_cycles / max(1, base_cycles - 1), 6),
                "ipc": round(max(0, base_cycles - 1) / max(1, base_cycles), 6), "stalls": core.stall_count,
                "forwarding_events": core.forwarding_events, "branch_flushes": core.branch_flushes,
                "base_cycles": base_cycles, "retired_instructions": retired,
                "cache_penalty_cycles": penalty, "effective_cycles": effective_cycles,
                "base_cpi": round(base_cycles / max(1, retired), 6), "effective_cpi": round(effective_cycles / max(1, retired), 6),
                "base_ipc": round(retired / max(1, base_cycles), 6), "effective_ipc": round(retired / max(1, effective_cycles), 6),
                **core.cache_report(),
            }
        write_report(Path(args.report), cores, {"branch": {"single_stage": ss_core.predictor.report(), "five_stage": fs_core.predictor.report()}},
                     {"configuration": cache_config.report() if cache_config else None},
                     traces={"single_stage": ss_core.trace, "five_stage": fs_core.trace},
                     cache_config=cache_config.report() if cache_config else None)
    return 0


if __name__ == "__main__":
    main()
