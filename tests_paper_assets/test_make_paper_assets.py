"""Unit tests for scripts/make_paper_assets.py using tiny SYNTHETIC fixtures only (no real data, no network).

Run: sh tests_paper_assets/run_tests.sh <python with the pinned stack (matplotlib 3.9.2)>
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import unittest
from pathlib import Path

import _fixtures as F

MPA = F.MPA


def quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
        rc = fn(*a)
    return rc, err.getvalue()


def full_root(name, protein=True, comparison=True, optional=True, info_methods=True):
    root = F.new_root(name)
    F.make_score(root / "runs/S/score", optional=optional, info_methods=info_methods)
    args = ["--score", str(root / "runs/S/score")]
    if protein:
        F.make_protein(root / "runs/S/protein")
        args += ["--protein", str(root / "runs/S/protein")]
    else:
        args += ["--protein-not-run"]
    if comparison:
        F.make_report(root / "runs/S/compare/report.json")
        args += ["--comparison", str(root / "runs/S/compare/report.json")]
    else:
        args += ["--no-comparison"]
    return root, args


def read(root, rel):
    return (root / rel).read_text()


class TestFormatting(unittest.TestCase):
    def test_escape(self):
        self.assertEqual(MPA.tex("a_b&c%d$e#f{g}~^\\<>|"),
                         r"a\_b\&c\%d\$e\#f\{g\}\textasciitilde{}\textasciicircum{}\textbackslash{}"
                         r"\textless{}\textgreater{}\textbar{}")

    def test_numbers_and_flags(self):
        self.assertEqual(MPA.num(0.91234), "0.912")
        self.assertEqual(MPA.num(-0.0123), "$-$0.012")
        self.assertEqual(MPA.num(1234, count=True), "1{,}234")
        self.assertEqual(MPA.num(MPA.UNDEF), r"\textit{undef.}")
        self.assertEqual(MPA.num(MPA.NOTATT), r"\textit{not attainable}")
        with self.assertRaises(MPA.AssetError):
            MPA.num(2.5, count=True)

    def test_value_parsing(self):
        row = {"a": "nan", "b": "", "c": "-inf", "d": "0.5", "e": "inf", "x_ci95": "[0.1, nan]", "y_ci95": "nan"}
        self.assertIs(MPA.value(row, "a"), MPA.UNDEF)
        self.assertIs(MPA.value(row, "b"), MPA.UNDEF)
        self.assertIs(MPA.value(row, "c"), MPA.NEGINF)
        self.assertIs(MPA.value(row, "e"), MPA.UNDEF)
        self.assertEqual(MPA.value(row, "d"), 0.5)
        self.assertIs(MPA.value(row, "zz"), MPA.MISSING)
        self.assertIs(MPA.value(None, "a"), MPA.MISSING)
        self.assertEqual(MPA.ci(row, "x"), (0.1, MPA.UNDEF))
        self.assertIs(MPA.ci(row, "y"), MPA.UNDEF)
        self.assertIs(MPA.ci(row, "q"), MPA.MISSING)

    def test_contract_matches_artifacts_json(self):
        c = json.loads((F.REPO / "paper/artifacts.json").read_text())
        self.assertEqual(c["generated_inputs"], MPA.expected_inputs())
        self.assertTrue(all(n.startswith(("paper/generated/", "paper/figures/")) for n in c["generated_inputs"]))


class TestFullRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, args = full_root("full")
        rc, err = quiet(F.run, cls.root, *args)
        assert rc == 0, err

    def test_all_contract_files_exist(self):
        for rel in MPA.expected_inputs():
            self.assertTrue((self.root / rel).is_file(), rel)
        for rel in MPA.expected_inputs():
            if rel.endswith(".pdf"):
                self.assertTrue((self.root / rel).read_bytes().startswith(b"%PDF-"), rel)
        self.assertFalse((self.root / "paper/.paper-assets-staging").exists())

    def test_known_values(self):
        t = read(self.root, "paper/generated/table_operating_points.tex")
        self.assertIn("0.912", t)                       # A:M4 coverage@OPcov 0.91234
        self.assertIn("[0.851, 0.950]", t)              # recorded CI [0.8506, 0.95049]
        self.assertIn("0.042", t)                       # A:M4 accepted error 0.0423
        self.assertIn(r"\textit{not attainable}", t)   # B:M3 OP-err
        m = read(self.root, "paper/generated/results_macros.tex")
        self.assertIn(r"\csname ctv@A@M4@coverage-at-OPcov\endcsname{0.912}", m)
        self.assertIn(r"\csname ctci@A@M4@coverage-at-OPcov\endcsname{[0.851, 0.950]}", m)
        self.assertIn(r"\csname ctv@A@M4@unknown-cells\endcsname{1{,}234}", m)
        self.assertIn(r"\csname ctv@B@M3@coverage-at-OPerr\endcsname{\textit{not attainable}}", m)
        self.assertIn(r"\csname ctv@practical@P2@unknown-auroc\endcsname{\textit{undef.}}", m)
        self.assertIn(r"\csname ctv@B@M1@diff-vs-B-M4-coverage-at-OPcov\endcsname{$-$0.012}", m)
        self.assertIn(r"\csname ctv@protein@check@status\endcsname{run}", m)
        self.assertIn(r"\csname ctv@protein-totalvi-pbmc5k-protein-v3@A-M4@agreement-accepted\endcsname{0.876}", m)

    def test_thresholds_flags(self):
        t = read(self.root, "paper/generated/table_thresholds.tex")
        self.assertIn(r"$-\infty$ (all eligible accepted)", t)  # P1 tau_cov -inf
        self.assertIn("0.830", t)                                # recorded cap shown
        self.assertIn(r"\textit{not attainable}", t)

    def test_tracks_and_identities_preserved(self):
        t = read(self.root, "paper/generated/table_operating_points.tex")
        for lab in MPA.ARM_LABEL.values():
            self.assertIn(MPA.tex(lab), t)
        self.assertLess(t.index("Arm A"), t.index("Arm B"))
        self.assertLess(t.index("Arm B"), t.index("Practical track"))
        ps = read(self.root, "paper/generated/table_per_study.tex")
        self.assertIn(r"RA\_study\&1\%", ps)
        pd_ = read(self.root, "paper/generated/table_paired_differences.tex")
        self.assertIn("A:M4", pd_)  # practical comparator identity
        cal = read(self.root, "paper/generated/table_calibration.tex")
        self.assertEqual(cal.count("uncalibrated score"), 6)  # M1-M3 in arms A and B

    def test_undefined_values(self):
        t = read(self.root, "paper/generated/table_unknowns.tex")
        self.assertIn(r"\textit{undef.}", t)   # P2 AUROC nan
        self.assertIn("simulated", t)
        n = read(self.root, "paper/generated/table_bootstrap_nan.tex")
        self.assertIn(r"coverage@OPerr & 7", n.replace(r"\_", "_"))
        self.assertNotIn("M1 & macro", n)

    def test_protein_table(self):
        t = read(self.root, "paper/generated/table_protein.tex")
        self.assertIn("descriptive; replacement inputs", t)
        self.assertIn(r"File totalvi\_pbmc5k\_protein\_v3", t)
        self.assertIn("0.876", t)

    def test_reproduction_table(self):
        t = read(self.root, "paper/generated/table_reproduction.tex")
        self.assertIn("reproduced within tolerance (synthetic)", t)

    def test_provenance_hashes(self):
        prov = json.loads(read(self.root, "paper/generated/asset_provenance.json"))
        self.assertTrue(prov["contract"]["checked"])
        read_inputs = [r for r in prov["inputs"] if r["status"] == "read"]
        self.assertGreaterEqual(len(read_inputs), 15)
        for r in read_inputs:
            b = (self.root / r["path"]).read_bytes()
            self.assertEqual(r["sha256"], hashlib.sha256(b).hexdigest())
            self.assertEqual(r["bytes"], len(b))
            self.assertFalse(Path(r["path"]).is_absolute())
        for o in prov["outputs"]:
            self.assertEqual(o["sha256"], hashlib.sha256((self.root / o["path"]).read_bytes()).hexdigest())
        self.assertNotIn(str(self.root), json.dumps(prov))  # no absolute paths


class TestDeterminism(unittest.TestCase):
    def test_byte_identical(self):
        outs = []
        for name in ("det1", "det2"):
            root, args = full_root(name)
            rc, err = quiet(F.run, root, *args)
            self.assertEqual(rc, 0, err)
            outs.append({rel: (root / rel).read_bytes() for rel in MPA.expected_inputs()})
        for rel in MPA.expected_inputs():
            self.assertEqual(outs[0][rel], outs[1][rel], rel)

    def test_rerun_same_root_identical(self):
        root, args = full_root("rerun")
        quiet(F.run, root, *args)
        first = {rel: (root / rel).read_bytes() for rel in MPA.expected_inputs()}
        rc, _ = quiet(F.run, root, *args)
        self.assertEqual(rc, 0)
        for rel in MPA.expected_inputs():
            self.assertEqual(first[rel], (root / rel).read_bytes(), rel)


class TestNotRunAndOptional(unittest.TestCase):
    def test_protein_not_run_no_comparison(self):
        root, args = full_root("notrun", protein=False, comparison=False, optional=False)
        rc, err = quiet(F.run, root, *args)
        self.assertEqual(rc, 0, err)
        for rel in MPA.expected_inputs():
            self.assertTrue((root / rel).is_file(), rel)
        t = read(root, "paper/generated/table_protein.tex")
        self.assertIn(r"\textit{Protein check not run}", t)
        self.assertIn(r"\csname ctv@protein@check@status\endcsname{not run}", read(root, "paper/generated/results_macros.tex"))
        self.assertIn("no comparison report supplied", read(root, "paper/generated/table_reproduction.tex"))
        self.assertIn("not available", read(root, "paper/generated/table_bootstrap_nan.tex"))
        self.assertIn("not available", read(root, "paper/generated/table_unknowns_allstrata.tex"))
        prov = json.loads(read(root, "paper/generated/asset_provenance.json"))
        self.assertIn("not_run", prov["options"]["protein"])
        self.assertTrue(any(r["status"] == "absent (optional)" for r in prov["inputs"]))

    def test_eligibility_not_run_consistent(self):
        root, args = full_root("elig0", protein=False)
        e = F.make_eligibility(root / "runs/S/cite", eligible=())
        rc, err = quiet(F.run, root, *args, "--eligibility", str(e))
        self.assertEqual(rc, 0, err)
        t = read(root, "paper/generated/table_protein.tex")
        self.assertIn("first failing criterion 4 (coverage)", t)

    def test_eligibility_contradicts_protein(self):
        root, args = full_root("elig_bad", protein=True)
        e = F.make_eligibility(root / "runs/S/cite", eligible=())
        rc, err = quiet(F.run, root, *args, "--eligibility", str(e))
        self.assertEqual(rc, 2)
        self.assertIn("no replacement file is eligible", err)
        self.assertFalse((root / "paper/generated").exists())

    def test_eligibility_run_consistent(self):
        root, args = full_root("elig1", protein=True)
        e = F.make_eligibility(root / "runs/S/cite", eligible=("totalvi_pbmc5k_protein_v3",))
        rc, err = quiet(F.run, root, *args, "--eligibility", str(e))
        self.assertEqual(rc, 0, err)
        t = read(root, "paper/generated/table_protein.tex")
        self.assertIn(r"totalvi\_pbmc10k\_protein\_v3: ineligible, first failing criterion 4 (coverage)", t)

    def test_not_run_but_eligible(self):
        root, args = full_root("elig_bad2", protein=False)
        e = F.make_eligibility(root / "runs/S/cite", eligible=("totalvi_pbmc5k_protein_v3",))
        rc, err = quiet(F.run, root, *args, "--eligibility", str(e))
        self.assertEqual(rc, 2)
        self.assertIn("no protein_check output", err)

    def test_not_run_reason_without_record(self):
        root, args = full_root("notrun_reason", protein=False)
        rc, err = quiet(F.run, root, *args)
        self.assertEqual(rc, 0, err)
        self.assertIn("declared not run by the caller", read(root, "paper/generated/table_protein.tex"))

    def test_tampered_eligibility(self):
        root, args = full_root("elig_tamper", protein=False)
        e = F.make_eligibility(root / "runs/S/cite", eligible=())
        e.write_text(e.read_text() + " ")
        rc, err = quiet(F.run, root, *args, "--eligibility", str(e))
        self.assertEqual(rc, 2)

    def test_missing_expected_method_row_is_explicit(self):
        root, args = full_root("missing_row", info_methods=False)
        for p in sorted((root / "runs/S/score").glob("*.csv")):
            with open(p, newline="") as fh:
                rows = list(csv.DictReader(fh))
            F.write_csv(p, [r for r in rows if not (r.get("arm") == "B" and r.get("method") == "M6")])
        rc, err = quiet(F.run, root, *args)
        self.assertEqual(rc, 0, err)
        t = read(root, "paper/generated/table_operating_points.tex")
        self.assertIn(r"M6 & \textit{missing}", t)


class TestFailClosed(unittest.TestCase):
    def assertFails(self, root, args, fragment):
        rc, err = quiet(F.run, root, *args)
        self.assertEqual(rc, 2, err)
        self.assertIn(fragment, err)
        self.assertFalse((root / "paper/generated").exists())
        self.assertFalse((root / "paper/figures").exists())

    def test_input_outside_root(self):
        root, args = full_root("outside")
        other, _ = full_root("outside_other")
        args[1] = str(other / "runs/S/score")
        self.assertFails(root, args, "outside --root")

    def test_symlink_escape(self):
        root, args = full_root("symlink")
        other, _ = full_root("symlink_other")
        p = root / "runs/S/score/summary_test.csv"
        p.unlink()
        p.symlink_to(other / "runs/S/score/summary_test.csv")
        self.assertFails(root, args, "outside --root")

    def test_output_outside_root(self):
        root, args = full_root("outroot")
        rc, err = quiet(MPA.main, ["--root", str(root / "runs"), "--output", str(root / "paper")] + args)
        self.assertEqual(rc, 2)
        self.assertIn("outside --root", err)

    def test_missing_required(self):
        root, args = full_root("missing_req")
        (root / "runs/S/score/platform.csv").unlink()
        self.assertFails(root, args, "required input missing")

    def test_duplicate_row(self):
        root, args = full_root("dup")
        p = root / "runs/S/score/calibration_test.csv"
        lines = p.read_text().splitlines(keepends=True)
        p.write_text("".join(lines + [lines[1]]))
        self.assertFails(root, args, "duplicate row")

    def test_unknown_arm(self):
        root, args = full_root("arm", info_methods=False)
        for fn in ("summary_test.csv", "thresholds_validation.csv"):
            p = root / "runs/S/score" / fn
            p.write_text(p.read_text().replace("\nB,", "\nC,"))
        self.assertFails(root, args, "unrecognised arm")

    def test_score_info_mismatch(self):
        root, args = full_root("info")
        p = root / "runs/S/score/score_info.json"
        i = json.loads(p.read_text())
        i["methods"] = i["methods"][:-1]
        p.write_text(json.dumps(i))
        self.assertFails(root, args, "score_info.json methods")

    def test_bad_report_schema(self):
        root, args = full_root("schema")
        F.make_report(root / "runs/S/compare/report.json", schema="other/1")
        self.assertFails(root, args, "schema")

    def test_contract_mismatch(self):
        root, args = full_root("contract")
        c = json.loads((root / "paper/artifacts.json").read_text())
        c["generated_inputs"] = c["generated_inputs"][:-1]
        (root / "paper/artifacts.json").write_text(json.dumps(c))
        self.assertFails(root, args, "artifacts.json")

    def test_protein_and_not_run_exclusive(self):
        root, args = full_root("excl")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            MPA.main(["--root", str(root), "--output", str(root / "paper")] + args + ["--protein-not-run"])

    def test_empty_protein_when_run(self):
        root, args = full_root("emptyprot")
        (root / "runs/S/protein/protein_agreement.csv").write_text("file,arm,method,agreement_accepted\n")
        self.assertFails(root, args, "no rows")



class TestLatexCompiles(unittest.TestCase):
    """Offline smoke compile with a local engine (not the pinned Tectonic build; skipped if absent)."""

    def test_compile(self):
        import os
        import shutil
        import subprocess
        engine = shutil.which("xelatex") or shutil.which("pdflatex")
        if engine is None:
            self.skipTest("no local LaTeX engine")
        root, args = full_root("latex")
        rc, err = quiet(F.run, root, *args)
        self.assertEqual(rc, 0, err)
        body = ["\\documentclass{article}", "\\usepackage[margin=1cm,landscape]{geometry}",
                "\\input{generated/asset_preamble.tex}", "\\begin{document}", "\\input{generated/results_macros.tex}",
                "\\ctres{A}{M4}{coverage-at-OPcov} \\ctci{A}{M4}{coverage-at-OPcov} "
                "\\ctres{protein}{check}{status} \\ctres{comparison}{report}{overall}"]
        for n in MPA.TABLES:
            body.append(f"\\begin{{table}}\\scriptsize\\centering\\resizebox{{\\linewidth}}{{!}}{{\\input{{generated/{n}}}}}\\end{{table}}\\clearpage")
        for n in MPA.FIGURES:
            body.append(f"\\includegraphics[width=0.9\\linewidth]{{figures/{n}}}\\clearpage")
        body.append("\\end{document}")
        (root / "paper/smoke.tex").write_text("\n".join(body))
        env = dict(os.environ, TEXMFVAR=str(F.TMP / "texmf-var"), TEXMFCACHE=str(F.TMP / "texmf-cache"))
        r = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "smoke.tex"],
                           cwd=root / "paper", capture_output=True, text=True, env=env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:])
        self.assertTrue((root / "paper/smoke.pdf").read_bytes().startswith(b"%PDF-"))

    def test_undefined_macro_errors(self):
        import os
        import shutil
        import subprocess
        engine = shutil.which("xelatex") or shutil.which("pdflatex")
        if engine is None:
            self.skipTest("no local LaTeX engine")
        root, args = full_root("latex_undef")
        quiet(F.run, root, *args)
        (root / "paper/u.tex").write_text("\\documentclass{article}\\input{generated/asset_preamble.tex}"
                                          "\\begin{document}\\input{generated/results_macros.tex}"
                                          "\\ctres{A}{M9}{coverage-at-OPcov}\\end{document}")
        env = dict(os.environ, TEXMFVAR=str(F.TMP / "texmf-var"), TEXMFCACHE=str(F.TMP / "texmf-cache"))
        r = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "u.tex"],
                           cwd=root / "paper", capture_output=True, text=True, env=env, timeout=300)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("undefined result A/M9", r.stdout)


if __name__ == "__main__":
    unittest.main()
