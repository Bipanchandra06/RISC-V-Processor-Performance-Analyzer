"""Small, dependency-free RV32I assembler used by the MicroTrace UI/CLI."""
from __future__ import annotations

import re
from dataclasses import dataclass

REGISTERS = {f"x{i}": i for i in range(32)}
REGISTERS.update({f"r{i}": i for i in range(32)})
REGISTERS.update({"zero": 0, "ra": 1, "sp": 2, "gp": 3, "tp": 4,
                  "t0": 5, "t1": 6, "t2": 7, "s0": 8, "fp": 8,
                  "s1": 9, "a0": 10, "a1": 11, "a2": 12, "a3": 13,
                  "a4": 14, "a5": 15, "a6": 16, "a7": 17,
                  "s2": 18, "s3": 19, "s4": 20, "s5": 21, "s6": 22,
                  "s7": 23, "s8": 24, "s9": 25, "s10": 26, "s11": 27,
                  "t3": 28, "t4": 29, "t5": 30, "t6": 31})

R_OPS = {"add": (0x00, 0x0), "sub": (0x20, 0x0), "and": (0x00, 0x7),
         "or": (0x00, 0x6), "xor": (0x00, 0x4)}
I_OPS = {"addi": 0x0}
B_OPS = {"beq": 0x0, "bne": 0x1}

@dataclass
class AssembledProgram:
    words: list[int]
    source_by_pc: dict[int, str]
    labels: dict[str, int]

def _reg(token: str, line: str) -> int:
    try: return REGISTERS[token.lower()]
    except KeyError as exc: raise ValueError(f"Unknown register '{token}' in: {line}") from exc

def _imm(token: str, line: str) -> int:
    try: return int(token.lstrip("#"), 0)
    except ValueError as exc: raise ValueError(f"Invalid immediate '{token}' in: {line}") from exc

def _is_register(token: str) -> bool:
    return token.lower() in REGISTERS

def _check_signed(value: int, bits: int, line: str) -> None:
    if not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
        raise ValueError(f"Immediate {value} does not fit in {bits} bits in: {line}")

def _target(token: str, labels: dict[str, int], line: str) -> int:
    if token in labels: return labels[token]
    try: return int(token, 0)
    except ValueError as exc: raise ValueError(f"Unknown label or address '{token}' in: {line}") from exc

def assemble(text: str) -> AssembledProgram:
    """Assemble the supported RV32I subset into byte-addressed words."""
    # Some of the original sample files wrap machine words in a C-style block
    # comment. Ignore those blocks so the same files can be assembled directly.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    lines = []
    labels = {}
    pc = 0
    for raw in text.splitlines():
        # A # immediately followed by a number is an accepted legacy immediate
        # marker (for example, LW R1, R0, #0); other # characters start a comment.
        line = re.sub(r"#(?=\s|$).*", "", raw).split("//", 1)[0].strip()
        if not line: continue
        while ":" in line:
            label, line = line.split(":", 1)
            label = label.strip()
            if not re.fullmatch(r"[A-Za-z_][\w.]*", label): raise ValueError(f"Invalid label '{label}'")
            if label in labels: raise ValueError(f"Duplicate label '{label}'")
            labels[label] = pc
            line = line.strip()
            if not line: break
        if line:
            lines.append((pc, line)); pc += 4

    words, source_by_pc = [], {}
    for pc, line in lines:
        source_by_pc[pc] = line
        parts = [p for p in re.split(r"[\s,()]+", line.strip()) if p]
        op = parts[0].lower(); args = parts[1:]
        try:
            if op in R_OPS and len(args) == 3:
                rd, rs1, rs2 = map(lambda x: _reg(x, line), args)
                funct7, funct3 = R_OPS[op]; word = (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0x33
            elif op in I_OPS and len(args) == 3:
                rd, rs1 = _reg(args[0], line), _reg(args[1], line); imm = _imm(args[2], line); _check_signed(imm, 12, line)
                word = ((imm & 0xfff) << 20) | (rs1 << 15) | (I_OPS[op] << 12) | (rd << 7) | 0x13
            elif op in {"lw", "sw"} and len(args) == 3:
                # Support both canonical RV32I syntax, lw rd, imm(rs1), and
                # the legacy project syntax, LW rd, rs1, #imm.
                if _is_register(args[1]) and not _is_register(args[2]):
                    r, base, imm = _reg(args[0], line), _reg(args[1], line), _imm(args[2], line)
                else:
                    r, imm, base = _reg(args[0], line), _imm(args[1], line), _reg(args[2], line)
                _check_signed(imm, 12, line)
                if op == "lw":
                    word = (r << 7) | (base << 15) | (0x2 << 12) | ((imm & 0xfff) << 20) | 0x03
                else:
                    word = ((imm & 0xfe0) << 20) | (base << 15) | (0x2 << 12) | (r << 20) | ((imm & 0x1f) << 7) | 0x23
            elif op in B_OPS and len(args) == 3:
                rs1, rs2 = _reg(args[0], line), _reg(args[1], line); target = _target(args[2], labels, line)
                offset = target - pc; _check_signed(offset, 13, line)
                if offset % 2: raise ValueError(f"Branch target must be 2-byte aligned in: {line}")
                word = (((offset >> 12) & 1) << 31) | (((offset >> 5) & 0x3f) << 25) | (rs2 << 20) | (rs1 << 15) | (B_OPS[op] << 12) | (((offset >> 1) & 0xf) << 8) | (((offset >> 11) & 1) << 7) | 0x63
            elif op == "jal" and len(args) == 2:
                rd, target = _reg(args[0], line), _target(args[1], labels, line)
                offset = target - pc; _check_signed(offset, 21, line)
                word = (((offset >> 20) & 1) << 31) | (((offset >> 1) & 0x3ff) << 21) | (((offset >> 11) & 1) << 20) | (((offset >> 12) & 0xff) << 12) | (rd << 7) | 0x6f
            elif op in {"halt", "stop"} and not args: word = 0xffffffff
            elif op == "nop" and not args: word = 0
            else: raise ValueError(f"Unsupported or malformed instruction: {line}")
        except IndexError as exc: raise ValueError(f"Malformed instruction: {line}") from exc
        words.append(word & 0xffffffff)
    return AssembledProgram(words, source_by_pc, labels)

def words_to_imem(words: list[int]) -> str:
    return "\n".join(f"{(word >> shift) & 0xff:08b}" for word in words for shift in (24, 16, 8, 0)) + "\n"
