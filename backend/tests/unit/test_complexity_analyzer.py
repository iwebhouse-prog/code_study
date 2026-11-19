"""Verifies code complexity assessment for uploaded code (T066, FR-021)."""

import unittest

from src.models import UploadedCode
from src.services.code_analysis.complexity_analyzer import (
    ADVANCED,
    INTERMEDIATE,
    ComplexityReport,
    FileMetrics,
    analyze_file,
    assess_complexity,
    complexity_level,
)

PYTHON = '''"""Docstring."""
import math

# comment
def area(r):
    if r > 0:
        return math.pi * r * r
    return 0
'''

JAVASCRIPT = """// add numbers
function add(a, b) {
  if (a) {
    return a + b;
  }
}
const double = (x) => x * 2;
/* block
   comment */
"""


class TestFileMetrics(unittest.TestCase):
    def test_python(self) -> None:
        # Docstring, comment and blank lines are not code; def -> 1 function;
        # "return math.pi" sits two levels below "def".
        self.assertEqual(analyze_file("geo.py", PYTHON), FileMetrics(8, 5, 1, 2))

    def test_javascript_counts_function_keyword_and_arrows(self) -> None:
        self.assertEqual(analyze_file("add.js", JAVASCRIPT), FileMetrics(9, 6, 2, 2))

    def test_c_preprocessor_lines_are_code(self) -> None:
        source = "#include <stdio.h>\nint main(void) {\n  return 0;\n}\n"
        self.assertEqual(analyze_file("main.c", source), FileMetrics(4, 4, 1, 1))

    def test_java_class_and_method_nest(self) -> None:
        source = "public class Main {\n  void run() {\n    for (;;) {\n    }\n  }\n}\n"
        self.assertEqual(analyze_file("Main.java", source), FileMetrics(6, 6, 1, 3))

    def test_css_rules_nest_by_braces(self) -> None:
        source = "a { color: red; }\n@media print {\n  b { c: d; }\n}\n"
        self.assertEqual(analyze_file("site.css", source), FileMetrics(4, 4, 0, 2))

    def test_tsx_and_jsx_use_their_own_lexers(self) -> None:
        tsx = "const B = ({ t }: P) => <b>{t}</b>;\n"
        jsx = "function App() {\n  return <div onClick={() => go()}>{n}</div>;\n}\n"
        self.assertEqual(analyze_file("B.tsx", tsx).function_count, 1)
        self.assertEqual(analyze_file("App.jsx", jsx).function_count, 2)

    def test_html_has_no_functions_or_nesting(self) -> None:
        source = "<html>\n  <body>\n    <p>hi</p>\n  </body>\n</html>\n"
        self.assertEqual(analyze_file("index.html", source), FileMetrics(5, 5, 0, 0))

    def test_txt_with_a_python_shebang_is_analysed_as_python(self) -> None:
        source = "#!/usr/bin/env python3\ndef f():\n    pass\n"
        self.assertEqual(analyze_file("run.txt", source), FileMetrics(3, 2, 1, 1))

    def test_tabs_and_crlf(self) -> None:
        self.assertEqual(
            analyze_file("t.py", "def f():\n\tif x:\n\t\treturn 1\n").max_nesting_depth,
            2,
        )
        self.assertEqual(
            analyze_file("w.py", "def f():\r\n    return 1\r\n"),
            FileMetrics(2, 2, 1, 1),
        )

    def test_unbalanced_closing_braces_do_not_go_negative(self) -> None:
        self.assertEqual(analyze_file("x.js", "}\n}\n{\n").max_nesting_depth, 1)

    def test_empty_file(self) -> None:
        self.assertEqual(analyze_file("empty.py", ""), FileMetrics(0, 0, 0, 0))


class TestLevelThresholds(unittest.TestCase):
    def test_thresholds(self) -> None:
        self.assertEqual(
            (INTERMEDIATE.code_lines, INTERMEDIATE.functions, INTERMEDIATE.depth),
            (100, 5, 3),
        )
        self.assertEqual(
            (ADVANCED.code_lines, ADVANCED.functions, ADVANCED.depth), (500, 20, 5)
        )

    def test_levels_are_the_stored_values(self) -> None:
        self.assertIn(complexity_level(0, 0, 0), UploadedCode.COMPLEXITY_LEVELS)

    def test_below_every_threshold_is_beginner(self) -> None:
        self.assertEqual(complexity_level(99, 4, 2), "beginner")

    def test_any_one_metric_reaching_intermediate_is_enough(self) -> None:
        for metrics in ((100, 0, 0), (0, 5, 0), (0, 0, 3)):
            with self.subTest(metrics=metrics):
                self.assertEqual(complexity_level(*metrics), "intermediate")

    def test_any_one_metric_reaching_advanced_is_enough(self) -> None:
        self.assertEqual(complexity_level(499, 19, 4), "intermediate")
        for metrics in ((500, 0, 0), (0, 20, 0), (0, 0, 5)):
            with self.subTest(metrics=metrics):
                self.assertEqual(complexity_level(*metrics), "advanced")


class TestUploadComplexity(unittest.TestCase):
    def test_small_upload_is_beginner(self) -> None:
        self.assertEqual(
            assess_complexity([("geo.py", PYTHON)]),
            ComplexityReport("beginner", 8, 5, 1, 2),
        )

    def test_sums_lines_and_functions_and_keeps_the_deepest_file(self) -> None:
        report = assess_complexity([("geo.py", PYTHON), ("add.js", JAVASCRIPT)])
        self.assertEqual(report, ComplexityReport("beginner", 17, 11, 3, 2))

    def test_documents_count_in_total_lines_only(self) -> None:
        readme = "# 제목\n" + "설명 줄\n" * 200
        report = assess_complexity([("README.md", readme), ("geo.py", PYTHON)])
        self.assertEqual(report, ComplexityReport("beginner", 209, 5, 1, 2))

    def test_many_small_functions_make_it_intermediate(self) -> None:
        source = "".join(f"def f{i}():\n    return {i}\n" for i in range(6))
        self.assertEqual(assess_complexity([("many.py", source)]).level, "intermediate")

    def test_long_file_makes_it_advanced(self) -> None:
        source = "x = 1\n" * 500
        report = assess_complexity([("long.py", source)])
        self.assertEqual((report.level, report.code_lines), ("advanced", 500))

    def test_deep_nesting_makes_it_advanced(self) -> None:
        source = "function f() {" + " if (a) {" * 4 + "}" * 5 + "\n"
        report = assess_complexity([("deep.js", source)])
        self.assertEqual((report.level, report.max_nesting_depth), ("advanced", 5))

    def test_empty_upload_is_beginner(self) -> None:
        self.assertEqual(
            assess_complexity([]), ComplexityReport("beginner", 0, 0, 0, 0)
        )
