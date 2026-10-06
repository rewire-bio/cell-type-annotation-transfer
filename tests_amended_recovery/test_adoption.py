"""Adoption of completed B M4-M6 from a SYNTHETIC prior run: success path, source mismatch, hash tampering.

Run: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests_amended_recovery -t .
"""
import json
import os
from pathlib import Path

from tests_amended_recovery._support import PriorRunFixture, R, RM, NAMES, sha, snapshot, w


class TestAdoptionSuccess(PriorRunFixture):
    def test_adopts_without_refit_and_preserves_original(self):
        before = snapshot(self.prior_run)
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake)), 0)
        calls = self.calls(st)
        scripts = [(Path(c[0]).name, c[c.index("--arm") + 1] + c[c.index("--method") + 1] + c[c.index("--stage") + 1]
                    if "--arm" in c else "") for c in calls]
        expect = [("build_cite_totalvi.py", "")] + [("run_matched.py", f"A{m}predict") for m in R.ALL_M]
        expect += [("score_all.py", ""), ("protein_check.py", "")]
        self.assertEqual(scripts, expect)  # no Arm B fit or predict was launched
        b = calls[0]
        self.assertEqual(b[1:], ["--workspace", str(self.ws), "--data", str(self.hist / self.lay["data"]),
                                 "--out", b[-1]])
        man = self.manifest()
        self.assertEqual(man["status"], "complete")
        adopted = [s for s in man["steps"] if s["status"] == "adopted"]
        self.assertEqual(sorted(s["name"] for s in adopted), sorted(R.ADOPTABLE))
        prior = json.loads(self.prior_manifest.read_text())
        for s in adopted:  # original provenance retained
            self.assertEqual(s["source"], prior["source"])
            self.assertTrue(s["receipt"].startswith(str(self.prior_run)))
            self.assertEqual(s["receipt_sha256"], sha(s["receipt"]))
        self.assertNotEqual(man["source"], prior["source"])  # new run records its own source separately
        asm = json.loads((self.d / "run" / "assembly.json").read_text())
        b4 = asm["armB"]["M4"]
        self.assertEqual(b4["provenance"], "adopted-recomputed")
        self.assertEqual(b4["source"], prior["source"])
        self.assertEqual(b4["adopted_from"]["prior_manifest_sha256"], sha(self.prior_manifest))
        link = self.d / "run" / "armB" / "M4"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), prior["assembly"]["armB"]["M4"]["predictions_dir"])
        self.assertEqual(man["eligibility"]["n_eligible"], 2)
        self.assertEqual(man["protein_check"]["status"], "run")
        self.assertEqual(man["protein_check"]["label"], RM.PROTEIN_LABEL)
        self.assertEqual(snapshot(self.prior_run), before)  # immutable original run (content, mode, mtime)

    def test_dry_run_verifies_and_launches_nothing(self):
        before = snapshot(self.prior_run)
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake, extra=["--dry-run"])), 0)
        self.assertEqual(self.calls(st), [])
        man = self.manifest()
        self.assertEqual(man["status"], "dry-run-verified")
        self.assertIn("verified_utc", man["adoption"])
        self.assertEqual(snapshot(self.prior_run), before)

    def test_only_driver_hash_may_differ(self):
        prior = json.loads(self.prior_manifest.read_text())
        self.assertEqual(prior["source"]["code_sha256"]["scripts/recover.py"], "0" * 64)  # != current driver
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake, extra=["--dry-run"])), 0)


class TestSourceMismatch(PriorRunFixture):
    def assertBlocked(self, needle, extra=()):
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake, extra=extra)), 3)
        self.assertIn(needle, self.manifest()["blocker"] if (self.d / "run/recovery_manifest.json").exists()
                      else needle)
        self.assertEqual(self.calls(st), [], "nothing may launch (and nothing is refit) after a failed adoption")

    def test_scientific_code_changed(self):
        w(self.ws / "companion/src/celltransfer/methods.py", "# changed\n")
        self.assertBlocked("scientific code differs")

    def test_training_script_changed(self):
        w(self.ws / "companion/scripts/run_matched.py", "# changed\n")
        self.assertBlocked("companion/scripts/run_matched.py")

    def test_resource_guard_change_is_not_tolerated(self):
        w(self.ws / "scripts/resource_guard.py", "# changed guard\n")
        self.assertBlocked("scripts/resource_guard.py")

    def test_dirty_prior_source(self):
        def mut(m):
            m["source"]["dirty"] = True
        self.rewrite_prior(mut)
        self.assertBlocked("not a clean recorded revision")

    def test_different_historical_manifest(self):
        self.rewrite_prior(lambda m: m.update(historical_manifest_sha256="f" * 64))
        self.assertBlocked("different historical manifest")

    def test_supplied_manifest_differs_from_original_run(self):
        man = json.loads(self.prior_manifest.read_text())
        man["stage_seconds_used"] = 1.0  # e.g. a hand-edited copy understating time already spent
        self.prior_manifest.write_text(json.dumps(man))
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake)), 3)
        self.assertEqual(self.calls(st), [])

    def test_adoption_requires_amendment_and_new_run_dir(self):
        fake, st = self.fake_python()
        a = [x for x in self.args(fake) if x not in ("--amendment", R.AMENDMENT_ID)]
        self.assertEqual(R.main(a), 3)  # --adopt-from without --amendment
        self.assertEqual(R.main(self.args(fake, run="run2", adopt=False)), 3)  # amendment without adoption
        self.assertEqual(self.calls(st), [])

    def test_reviewed_amendment_text_must_match_approval(self):
        w(self.ws / R.AMENDMENT_REVIEWED, "edited after approval\n")
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake)), 3)
        self.assertEqual(self.calls(st), [])


class TestHashTampering(PriorRunFixture):
    def run_blocked(self, needle):
        before = snapshot(self.prior_run)
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake)), 3)
        self.assertIn(needle, self.manifest()["blocker"])
        self.assertEqual(self.calls(st), [], "tampering must never trigger a refit or any launch")
        self.assertEqual(snapshot(self.prior_run), before)

    def prior_step(self, name):
        return next(s for s in json.loads(self.prior_manifest.read_text())["steps"] if s["name"] == name)

    def test_prediction_bytes_changed(self):
        Path(self.prior_step("B_M5_predict")["out_dir"], "predictions_s.parquet").write_text("tampered")
        self.run_blocked("does not hash-match its receipt")

    def test_model_bytes_changed(self):
        Path(self.prior_step("B_M6_fit")["out_dir"], "scanvi", "model.pt").write_bytes(b"tampered")
        self.run_blocked("B_M6_fit: adopted output does not hash-match")

    def test_extra_file_in_output(self):
        w(Path(self.prior_step("B_M4_fit")["out_dir"]) / "stray.txt", "x")
        self.run_blocked("does not hash-match its receipt")

    def test_missing_output_file(self):
        Path(self.prior_step("B_M4_predict")["out_dir"], "predict_info.json").unlink()
        self.run_blocked("does not hash-match its receipt")

    def test_receipt_differs_from_evidence_copy(self):
        rp = Path(self.prior_step("B_M5_fit")["receipt"])
        r = json.loads(rp.read_text())
        r["files_sha256"]["model.pkl"] = "0" * 64
        rp.write_text(json.dumps(r, indent=1, sort_keys=True))
        self.run_blocked("receipt differs from evidence copy")

    def test_receipt_and_evidence_tampered_together(self):
        name = "B_M5_fit"
        out = Path(self.prior_step(name)["out_dir"])
        (out / "model.pkl").write_text("tampered")
        for rp in (Path(self.prior_step(name)["receipt"]), self.evidence / f"{name}.json"):
            r = json.loads(rp.read_text())
            r["files_sha256"]["model.pkl"] = sha(out / "model.pkl")
            rp.write_text(json.dumps(r, indent=1, sort_keys=True))
        self.run_blocked("adopted assembly entry does not match its receipts")

    def test_m6_checkpoint_hash_file_changed(self):
        (self.prior_run / "armB_M6_scanvi_expected_sha256.json").write_text(json.dumps({"model.pt": "0" * 64}))
        self.run_blocked("checkpoint-hash file")

    def test_original_attempt_record_missing(self):
        Path(self.prior_step("B_M4_fit")["attempt_dir"], "attempt.json").unlink()
        self.run_blocked("original attempt record missing")

    def test_evidence_assembly_differs(self):
        a = json.loads((self.evidence / "assembly.json").read_text())
        a["armB"]["M4"]["fit_dir"] = "/elsewhere"
        (self.evidence / "assembly.json").write_text(json.dumps(a))
        self.run_blocked("evidence assembly.json differs")

    def test_two_ok_attempts_is_ambiguous(self):
        def dup(m):
            m["steps"].append(dict(m["steps"][0]))
        self.rewrite_prior(dup)
        self.run_blocked("ok attempts (need exactly 1)")

    def test_predict_not_from_adopted_fit(self):
        def mut(m):
            st = next(s for s in m["steps"] if s["name"] == "B_M4_predict")
            st["command"][st["command"].index("--model-dir") + 1] = "/other/fit"
        self.rewrite_prior(mut)
        self.run_blocked("receipt field command does not match")


class TestEligibilityNames(PriorRunFixture):
    def test_names_are_the_pinned_files(self):
        self.assertEqual(NAMES, ["totalvi_pbmc10k_protein_v3", "totalvi_pbmc5k_protein_v3"])
