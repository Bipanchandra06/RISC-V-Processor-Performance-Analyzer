# RISC-V Pipeline Observatory

An end-to-end RV32I processor simulation and performance-analysis platform. The project combines a modular CPU execution model, an assembly-to-machine-code toolchain, configurable cache and branch-prediction experiments, structured observability, and a Streamlit interface for analyzing execution at instruction and cycle granularity.

## Project overview

The simulator accepts either the existing byte-oriented `imem.txt` format or assembly source. Assembly is translated into 32-bit RISC-V words and then into the four-byte-per-instruction format expected by instruction memory. The selected processor executes the same program and produces the traditional register and data-memory result files.

The five-stage core models the following stages:

| Stage | Work performed                                                          |
| ----- | ----------------------------------------------------------------------- |
| IF    | Fetch an instruction and advance the PC                                 |
| ID    | Decode it, read registers, generate control signals, and detect hazards |
| EX    | Perform the ALU operation and calculate branch or memory addresses      |
| MEM   | Read or write data memory and resolve branches                          |
| WB    | Write an ALU or load result back to the register file                   |

The stages overlap, allowing multiple instructions to be active in different stages during one cycle. The single-stage core completes one instruction through its datapath before starting the next one and provides a controlled baseline for throughput and latency comparisons.

This is a classic in-order pipeline simulator, not a dynamically scheduled or out-of-order processor. It handles dependencies with forwarding and stalls, and handles incorrect branch predictions by flushing wrong-path instructions and redirecting the PC to the resolved target.

## Technical capabilities

- RV32I instruction subset: `add`, `sub`, `and`, `or`, `xor`, `addi`, `lw`, `sw`, `beq`, `bne`, `jal`, `nop`, and `halt`.
- Register aliases such as `zero`, `ra`, `sp`, `t0`, `s0`, and `a0`.
- Labels for branches and jumps.
- Canonical memory syntax (`lw x1, 0(x0)`) plus backward-compatible `R` register and immediate syntax.
- Hazard detection, ALU forwarding, load-use stalls, branch handling, and pipeline flush tracking.
- Always-taken, always-not-taken, one-bit, and two-bit branch predictors.
- Independent instruction and data caches for each core.
- Direct-mapped, set-associative, and fully associative cache organizations.
- LRU and FIFO replacement policies.
- Cache access records with cycle, address/block, type, hit/miss, set, tag, penalty, and eviction.
- JSON reports containing metrics, predictor statistics, cache statistics, and five-stage cycle traces.
- Streamlit observability dashboard for assembly editing, execution results, translated instructions, and pipeline inspection.

## Engineering highlights

- Separated core, memory, assembler, cache, predictor, tracing, reporting, and UI modules so each concern can be tested and evolved independently.
- Preserved the existing register-file, data-memory, and text-metrics interfaces while adding richer JSON output for new analysis features.
- Kept cache timing analytically separate from architectural execution cycles, preventing performance experiments from changing functional results.
- Created independent instruction/data cache state for each processor so single-stage and five-stage comparisons are reproducible and isolated.
- Added readable validation errors for malformed assembly, unsupported instructions, invalid addresses, and invalid cache geometries.
- Added deterministic regression tests for instruction encoding, cache placement, LRU/FIFO behavior, and cache timing.

## Quick start

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the web dashboard:

```bash
streamlit run app.py
```

Enter assembly, resolve any validation message, choose the processor and optional cache settings, and select **Run program**. The five-stage tab lets you select a cycle and inspect the source instruction in IF, ID, EX, MEM, and WB. The translation tab shows the generated PC, assembly, hexadecimal word, and binary word.

Run the existing file-based workflow:

```bash
python main.py --iodir iodir --mode both
```

Assemble a source file directly:

```bash
python main.py --iodir iodir --asm-file input/Code.asm --mode both --report observatory.json
```

`--mode` accepts `ss`, `fs`, or `both`. The original RF, DMEM, and performance text files remain in the selected I/O directory for compatibility.

## Cache experiments

Enable both caches with the default configuration:

```bash
python main.py --iodir iodir --mode both --cache --report observatory.json
```

Useful options are:

```text
--cache-type direct|set-associative|fully-associative
--associativity N
--replacement lru|fifo
--cache-size BYTES
--block-size BYTES
--hit-latency CYCLES
--miss-penalty CYCLES
--memory-latency CYCLES
--instruction-cache
--data-cache
```

The cache is tag-only: the functional memory remains the source of truth, so enabling a cache cannot change registers or memory results. A hit adds `hit_latency - 1` analytical penalty cycles; a miss adds that hit cost, miss penalty, and memory refill latency. The normal processor cycle is reported separately as **base cycles**.

The report distinguishes:

```text
base cycles       = processor model cycles
cache penalty     = analytical cache delay
effective cycles  = base cycles + cache penalty
effective CPI     = effective cycles / retired instructions
effective IPC     = retired instructions / effective cycles
```

## Assembly example

```asm
start:
    addi x1, x0, 3
    addi x2, x0, 7
    add  x3, x1, x2
    sw   x3, 8(x0)
    lw   x4, 8(x0)
    beq  x4, x3, done
    addi x5, x0, 99
done:
    halt
```

Comments may use `//` or `# comment`. A `#` immediately before a number is accepted as the legacy immediate marker.

## Project layout

```text
app.py                 Streamlit interface
main.py                Command-line runner
src/assembler.py       Assembly parser and encoder
src/core.py            Single-stage and five-stage cores
src/memory.py          Instruction and data memory
src/cache.py           Cache organizations and replacement policies
src/predictor.py       Branch predictors
src/trace.py           Structured cycle trace support
src/report.py          Deterministic JSON report writer
tests/                 Regression tests
input/                 Default assembly and memory inputs
iodir/                 Compatibility output directory
```

## Testing

Run the regression suite with:

```bash
python -m unittest discover -s tests -p "test*.py" -v
```

Run a syntax check with:

```bash
python -m compileall -q .
```

If the CLI reports that `imem.txt` or `dmem.txt` is missing, pass an `--iodir` containing both files. When using `--asm-file`, only `dmem.txt` is required initially because the assembler generates `imem.txt` there.
