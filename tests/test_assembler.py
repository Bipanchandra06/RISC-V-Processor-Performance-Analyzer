import unittest

from src.assembler import assemble


class AssemblerTests(unittest.TestCase):
    def test_canonical_and_legacy_memory_syntax(self):
        program = assemble("""
            /* legacy sample comment containing machine words */
            lw x1, 0(x0)
            LW R2, R0, #4
            sw x1, 8(x0)
            SW R2, R0, #12
            halt
        """)
        self.assertEqual(len(program.words), 5)
        self.assertEqual(program.words[1], assemble("lw x2, 4(x0)\n").words[0])
        self.assertEqual(program.words[2] & 0x7f, 0x23)
        self.assertEqual(program.words[3] & 0x7f, 0x23)

    def test_labels_and_branch(self):
        program = assemble("""
            loop: addi x1, x1, -1
            bne x1, x0, loop
            jal x0, loop
            halt
        """)
        self.assertEqual(program.labels["loop"], 0)
        self.assertEqual(len(program.words), 4)


if __name__ == "__main__":
    unittest.main()
