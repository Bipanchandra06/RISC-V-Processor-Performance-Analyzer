"""Clean, beginner-friendly Streamlit interface for the RISC-V simulator."""
from pathlib import Path
import json, shutil, subprocess, sys, tempfile
import pandas as pd
import streamlit as st
from src.assembler import assemble

ROOT = Path(__file__).parent
DEFAULT = "addi x1, x0, 5\naddi x2, x0, 10\nadd x3, x1, x2\nhalt\n"

st.set_page_config(page_title="RISC-V Simulator", page_icon="⚙️", layout="wide")
st.markdown("""
<style>
.stApp { background:#f7f9fb; }
[data-testid="stSidebar"] { background:#edf3f7; border-right:1px solid #d6e0e7; }
[data-testid="stMetric"] { background:white; border:1px solid #d6e0e7; border-radius:6px; padding:10px 14px; }
h1,h2,h3 { color:#17324d; }
.title-note { color:#607585; font-size:1.02rem; margin-top:-10px; }
.stage { background:#eaf2f7; border:1px solid #c9dbe7; border-radius:5px; padding:9px 5px; text-align:center; color:#17324d; }
</style>
""", unsafe_allow_html=True)

st.title("RISC-V Simulator")
st.markdown('<p class="title-note">Write assembly, run it, and inspect the five pipeline stages one cycle at a time.</p>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Run settings")
    mode = st.radio("Processor", ["fs", "ss", "both"], format_func=lambda x: {"fs":"5-stage pipeline", "ss":"Single-stage", "both":"Compare both"}[x])
    predictor = st.selectbox("Branch predictor", ["always-not-taken", "always-taken", "one-bit", "two-bit"])
    cache = st.checkbox("Enable cache statistics")
    run = st.button("Run program", type="primary", use_container_width=True)

source = st.text_area("Assembly code", DEFAULT, height=230, help="Use one supported instruction per line. Comments start with #.")

try:
    program = assemble(source)
    st.caption(f"{len(program.words)} instruction(s) ready")
except ValueError as exc:
    program = None
    st.error(str(exc))

if run:
    if program is None:
        st.warning("Fix the assembly error before running.")
    else:
        with tempfile.TemporaryDirectory(prefix="riscv_ui_") as temp:
            work = Path(temp)
            shutil.copy(ROOT / "input" / "dmem.txt", work / "dmem.txt")
            asm = work / "program.asm"; asm.write_text(source)
            report = work / "report.json"
            command = [sys.executable, str(ROOT / "main.py"), "--iodir", str(work), "--mode", mode, "--asm-file", str(asm), "--predictor", predictor, "--report", str(report)]
            if cache: command.append("--cache")
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            if result.returncode:
                st.error("The program could not be completed.")
                with st.expander("Details"): st.code(result.stderr or result.stdout)
            else:
                st.session_state.result = json.loads(report.read_text())
                st.session_state.program = program

if "result" in st.session_state:
    data = st.session_state.result
    st.divider()
    st.header("Results")
    core_rows = []
    for name, values in data.get("cores", {}).items():
        core_rows.append({"Processor": name.replace("_", " ").title(), "Cycles": values["cycles"], "Instructions": values["instructions"], "CPI": values["cpi"], "IPC": values["ipc"], "Stalls": values["stalls"], "Forwarding": values["forwarding_events"], "Flushes": values["branch_flushes"]})
    st.dataframe(pd.DataFrame(core_rows), use_container_width=True, hide_index=True)
    cols = st.columns(len(core_rows) or 1)
    for col, row in zip(cols, core_rows):
        with col:
            st.metric(f'{row["Processor"]} cycles', row["Cycles"])
            st.metric(f'{row["Processor"]} CPI', row["CPI"])

    if mode in ("fs", "both"):
        tab_trace, tab_translation = st.tabs(["5-stage execution", "Translated instructions"])
        with tab_trace:
            traces = data.get("traces", {}).get("five_stage", [])
            if not traces:
                st.info("No pipeline trace was returned.")
            else:
                cycle = st.number_input("Cycle", min_value=0, max_value=len(traces)-1, value=0, step=1)
                selected = traces[int(cycle)]
                st.write(f'Cycle {selected["cycle"]}  |  PC {selected["pc"]}  |  Machine word `0x{selected["instruction"]:08x}`')
                stage_cols = st.columns(5)
                for col, stage in zip(stage_cols, ["IF", "ID", "EX", "MEM", "WB"]):
                    info = selected["stages"].get(stage, {})
                    instr = (info.get("Instr", 0) if stage == "ID" else info.get("instr", 0)) if isinstance(info, dict) else 0
                    pc = info.get("PC", info.get("pc", "-")) if isinstance(info, dict) else "-"
                    if stage == "IF" and not instr:
                        text = st.session_state.program.source_by_pc.get(pc, "NOP / empty")
                    else:
                        text = st.session_state.program.source_by_pc.get(pc, "NOP / empty") if instr else "NOP / empty"
                    col.markdown(f'<div class="stage"><b>{stage}</b><br><small>PC {pc}</small><br>{text}</div>', unsafe_allow_html=True)
                if selected.get("events"): st.warning(" | ".join(selected["events"]))
                with st.expander("Show stage details for this cycle"):
                    detail_rows = []
                    for stage in ["IF", "ID", "EX", "MEM", "WB"]:
                        info = selected["stages"].get(stage, {})
                        if not isinstance(info, dict):
                            continue
                        instr = info.get("Instr", info.get("instr", 0))
                        pc_value = info.get("PC", "-")
                        source_line = st.session_state.program.source_by_pc.get(pc_value, "NOP / empty") if instr else "NOP / empty"
                        detail_rows.append({
                            "Stage": stage,
                            "PC": pc_value,
                            "Instruction": source_line,
                            "Status": "NOP / idle" if info.get("nop", False) else "Active",
                            "rs1": info.get("Rs", info.get("rs1", "-")),
                            "rs2": info.get("Rt", info.get("rs2", "-")),
                            "rd": info.get("Wrt_reg_addr", "-"),
                            "ALU result": info.get("ALUresult", info.get("Wrt_data", "-")),
                            "MemRead": info.get("rd_mem", "-"),
                            "MemWrite": info.get("wrt_mem", "-"),
                        })
                    st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)
        with tab_translation:
            rows = []
            for index, word in enumerate(st.session_state.program.words):
                pc = index * 4
                rows.append({"PC": pc, "Assembly": st.session_state.program.source_by_pc.get(pc, ""), "Hex": f"0x{word:08x}", "Binary": f"{word:032b}"})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption("This is the assembly-to-machine-code translation loaded into instruction memory for the five-stage run.")
