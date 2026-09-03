import argparse
from pathlib import Path
import json
import shutil
import tempfile

from loguru import logger

from src.core import SingleStageCore, FiveStageCore
from src.generate_metrics import generate_metrics
from src.memory import InstructionMemory, DataMemory
from src.assembler import assemble, words_to_imem
from src.cache import SetAssociativeCache
from src.predictor import BranchPredictor
from src.report import write_report

if __name__ == "__main__":
    # logger.remove()
    # logger.add(sys.stderr, level="DEBUG")
    # logger.add(sys.stderr, level="DEBUG", backtrace=True, diagnose=True)

    # parse arguments for input file location
    parser = argparse.ArgumentParser(description='RV32I processor')
    parser.add_argument('--iodir', default="iodir", type=str, help='Directory containing the input files.')
    parser.add_argument('--mode', choices=['ss', 'fs', 'both'], default='both', help='Core(s) to execute.')
    parser.add_argument('--asm-file', type=str, help='Assemble this RV32I source file before running.')
    parser.add_argument('--predictor', choices=['always-not-taken', 'always-taken', 'one-bit', 'two-bit'], default='always-not-taken')
    parser.add_argument('--cache', action='store_true', help='Enable the default 256-byte direct-mapped data cache.')
    parser.add_argument('--report', type=str, help='Write a structured JSON observatory report.')
    args = parser.parse_args()

    ioDir = Path(args.iodir)

    if args.asm_file:
        program = assemble(Path(args.asm_file).read_text())
        (ioDir / "imem.txt").write_text(words_to_imem(program.words))

    logger.info(f"List IO Directory: {list(ioDir.iterdir())}")

    imem = InstructionMemory("Imem", ioDir)

    ss_cache = SetAssociativeCache() if args.cache else None
    fs_cache = SetAssociativeCache() if args.cache else None
    dmem_ss = DataMemory("SS", ioDir, ss_cache)
    dmem_fs = DataMemory("FS", ioDir, fs_cache)

    ssCore = SingleStageCore(ioDir, imem, dmem_ss)
    fsCore = FiveStageCore(ioDir, imem, dmem_fs)
    predictor = BranchPredictor(args.predictor)
    ssCore.predictor = predictor
    fsCore.predictor = predictor

    while (True):
        if args.mode in ('ss', 'both') and not ssCore.halted:
            ssCore.step()

        if args.mode in ('fs', 'both') and not fsCore.halted:
            fsCore.step()

        ss_done = args.mode not in ('ss', 'both') or ssCore.halted
        fs_done = args.mode not in ('fs', 'both') or fsCore.halted
        if ss_done and fs_done:
            break

        # if ssCore.halted or fsCore.halted:
        #     break

        # test only
        # if fsCore.cycle > 100:
        #     logger.error("Five Stage Core is taking too long to execute. Exiting...")
        #     break

    # dump SS and FS data mem.
    if args.mode in ('ss', 'both'): dmem_ss.output_data_memory()
    if args.mode in ('fs', 'both'): dmem_fs.output_data_memory()

    if args.mode in ('ss', 'both'):
        generate_metrics("w", "Single Stage Core Performance Metrics", ssCore.cycle, ssCore.cycle - 1, ioDir)
    if args.mode in ('fs', 'both'):
        generate_metrics("a" if args.mode == 'both' else "w", "Five Stage Core Performance Metrics", fsCore.cycle, fsCore.cycle - 1, ioDir)

    if args.report:
        cores = {}
        for name, core in (("single_stage", ssCore), ("five_stage", fsCore)):
            if (name == "single_stage" and args.mode not in ('ss', 'both')) or (name == "five_stage" and args.mode not in ('fs', 'both')): continue
            cores[name] = {"cycles": core.cycle, "instructions": max(0, core.cycle - 1), "cpi": round(core.cycle / max(1, core.cycle - 1), 6),
                           "ipc": round(max(0, core.cycle - 1) / max(1, core.cycle), 6), "stalls": core.stall_count,
                           "forwarding_events": core.forwarding_events, "branch_flushes": core.branch_flushes}
        write_report(Path(args.report), cores, {"branch": predictor.report()},
                     {"single_stage": ss_cache.stats.report(), "five_stage": fs_cache.stats.report()} if args.cache else {},
                     traces={"single_stage": ssCore.trace, "five_stage": fsCore.trace})
