"""Time/attempt carry-forward, R4' single remaining attempt, CITE pool, R5 disk floor, eligibility-driven
R5/R7 (SYNTHETIC prior run, fake interpreter; no real step runs)."""
import contextlib
import io
import json
from pathlib import Path

from tests_amended_recovery._support import PriorRunFixture, R, RM, NAMES, w

GiB = 1 << 30


def by_name(man, name):
    return [s for s in man["steps"] if s["name"] == name]


class TestCarryForward(PriorRunFixture):
    def test_time_carried_once(self):
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake, extra=["--dry-run"])), 0)
        man = self.manifest()
        c = man["adoption"]["carried"]
        self.assertEqual(c["prior_stage_seconds_used"], self.PRIOR_STAGE)
        self.assertEqual(c["prior_r4_seconds"], self.R4_SECONDS)
        # start = prior stage (already includes the prior run's own --prior-seconds) + R4 attempt 1; nothing else
        self.assertEqual(man["stage_seconds_used"], self.PRIOR_STAGE + self.R4_SECONDS)
        self.assertEqual(c["counted_prior_attempts"], {"cite_build": 1})

    def test_prior_seconds_or_attempts_refused(self):
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake, extra=["--prior-seconds", "60"])), 3)
        self.assertEqual(R.main(self.args(fake, run="r2", extra=["--prior-attempts", '{"B_M4_fit": 1}'])), 3)
        self.assertEqual(R.main(self.args(fake, run="r3", r4=False)), 3)  # R4 time must be supplied, not guessed
        self.assertEqual(self.calls(st), [])

    def test_adopted_wall_time_not_recharged(self):
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake)), 0)
        man = self.manifest()
        new = sum(s["wall_seconds"] for s in man["steps"] if s["status"] != "adopted")
        # elapsed is measured around each attempt, so allow driver overhead but never the adopted 51 s again
        self.assertGreaterEqual(man["stage_seconds_used"], self.PRIOR_STAGE + self.R4_SECONDS + new - 1e-6)
        self.assertLess(man["stage_seconds_used"], self.PRIOR_STAGE + self.R4_SECONDS + new + 20)
        self.assertTrue(all(s["charged"].startswith("in carried prior") for s in man["steps"]
                            if s["status"] == "adopted"))

    def test_stage_ceiling_includes_carried_time(self):
        fake, st = self.fake_python()
        ceiling = self.PRIOR_STAGE + self.R4_SECONDS + 1.0
        self.assertEqual(R.main(self.args(fake, extra=["--stage-ceiling", str(ceiling)])), 3)
        man = self.manifest()
        cb = by_name(man, "cite_build")
        self.assertEqual(len(cb), 1)
        self.assertLessEqual(cb[0]["timeout_s"], 1.0 + 1e-6)

    def test_carried_cite_pool(self):
        self.rewrite_prior(lambda m: m.update(pool_seconds_used={"cite_predict": 1790.0}))
        fake, st = self.fake_python()
        R.main(self.args(fake))
        man = self.manifest()
        a1 = by_name(man, "A_M1_cite")
        self.assertTrue(a1)
        self.assertLessEqual(a1[0]["timeout_s"], 10.0 + 1e-6)  # 30 min pool minus 1790 s already used
        self.assertGreaterEqual(man["pool_seconds_used"]["cite_predict"], 1790.0)

    def test_unrecorded_prior_attempt_charged_and_counted(self):
        adir = self.prior_run / "attempts" / "cite_build" / "attempt-1-20261006T180000000000Z"
        w(adir / "attempt.json", json.dumps({"status": "timeout", "wall_seconds": 7.0}))
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake)), 3)
        man = self.manifest()
        self.assertEqual(man["adoption"]["carried"]["unrecorded_prior_attempts_charged"][0]["charged_seconds"], 7.0)
        self.assertEqual(man["stage_seconds_used"], self.PRIOR_STAGE + self.R4_SECONDS + 7.0)
        # R4 attempt 1 (403) + this attempt = 2: no R4 attempt remains, nothing is launched
        self.assertIn("failed after 2 attempts", man["blocker"])
        self.assertEqual(self.calls(st), [])


class TestR4PrimeSingleAttempt(PriorRunFixture):
    def test_infrastructure_failure_not_retried(self):
        fake, st = self.fake_python(sleep_on="build_cite_totalvi")
        self.assertEqual(R.main(self.args(fake, extra=["--ceilings", json.dumps({"cite_build": 0.5})])), 3)
        man = self.manifest()
        cb = by_name(man, "cite_build")
        self.assertEqual([(s["attempt"], s["status"]) for s in cb], [(2, "timeout")])  # attempt 2 is the last
        self.assertIn("replacement ended", man["blocker"])
        self.assertEqual(man["protein_check"]["status"], "not_run")
        self.assertEqual(len(self.calls(st)), 1)
        self.assertTrue(Path(cb[0]["attempt_dir"], "attempt.json").is_file())  # failed attempt preserved

    def test_deterministic_failure(self):
        fake, st = self.fake_python(fail_on="build_cite_totalvi")
        self.assertEqual(R.main(self.args(fake)), 3)
        self.assertEqual(len(self.calls(st)), 1)
        self.assertIn("replacement ended", self.manifest()["blocker"])

    def test_missing_builder_consumes_no_attempt(self):
        (self.ws / R.REPLACEMENT_BUILDER).unlink()
        fake, st = self.fake_python()
        self.assertEqual(R.main(self.args(fake)), 3)
        self.assertEqual(self.calls(st), [])
        self.assertEqual(by_name(self.manifest(), "cite_build"), [])

    def test_invalid_eligibility_ends_replacement(self):
        fake, st = self.fake_python(elig={"__missing__": True})
        self.assertEqual(R.main(self.args(fake)), 3)
        man = self.manifest()
        self.assertIn("no valid eligibility.json", man["blocker"])
        self.assertEqual([Path(c[0]).name for c in self.calls(st)], ["build_cite_totalvi.py"])

    def test_resume_after_r4_failure_cannot_retry(self):
        fake, st = self.fake_python(fail_on="build_cite_totalvi")
        self.assertEqual(R.main(self.args(fake)), 3)
        used = self.manifest()["stage_seconds_used"]
        self.assertEqual(R.main(self.args(fake, extra=["--resume"])), 3)
        man = self.manifest()
        self.assertEqual(len(self.calls(st)), 1)
        self.assertEqual(man["stage_seconds_used"], used)  # carried time not re-added on resume

    def test_resume_requires_same_r4_seconds(self):
        fake, st = self.fake_python(fail_on="score_all")
        self.assertEqual(R.main(self.args(fake)), 3)
        before = self.manifest()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(R.main(self.args(fake, r4=1.0, extra=["--resume"])), 3)
        self.assertIn("--prior-r4-seconds differs", err.getvalue())
        self.assertEqual(self.manifest(), before)  # refused before touching the run record
        other = self.d / "other_prior.json"
        other.write_text(self.prior_manifest.read_text() + "\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            a = self.args(fake, extra=["--resume"])
            a[a.index("--adopt-from") + 1] = str(other)
            self.assertEqual(R.main(a), 3)
        self.assertIn("--adopt-from manifest differs", err.getvalue())


class TestEligibilityDrivenSteps(PriorRunFixture):
    def tags(self, st):
        return [Path(c[0]).name + (":" + c[c.index("--method") + 1] if "--method" in c else "")
                for c in self.calls(st)]

    def test_zero_eligible_is_explicitly_not_run(self):
        fake, st = self.fake_python(elig={n: "ineligible:4" for n in NAMES})
        self.assertEqual(R.main(self.args(fake)), 0)
        self.assertEqual(self.tags(st), ["build_cite_totalvi.py", "score_all.py"])
        man = self.manifest()
        self.assertEqual(man["status"], "complete")
        pc = man["protein_check"]
        self.assertEqual((pc["status"], pc["n_eligible"]), ("not_run", 0))
        self.assertEqual(sorted(pc["steps_not_run"]), sorted([f"A_{m}_cite" for m in R.ALL_M] + ["protein"]))
        self.assertEqual(pc["first_failing_criterion"], {n: {"number": 4, "name": "coverage"} for n in NAMES})
        self.assertFalse((self.d / "run" / "armA_cite").exists())

    def test_one_eligible(self):
        fake, st = self.fake_python(elig={"totalvi_pbmc10k_protein_v3": "ineligible:5"})
        self.assertEqual(R.main(self.args(fake)), 0)
        man = self.manifest()
        self.assertEqual(man["eligibility"]["eligible"], ["totalvi_pbmc5k_protein_v3"])
        self.assertEqual(man["protein_check"]["status"], "run")
        self.assertEqual(self.tags(st)[-1], "protein_check.py")

    def test_r5_disk_floor(self):
        fake, st = self.fake_python()
        a = [x for x in self.args(fake)]
        a[a.index("--r5-disk-gib") + 1] = "1000000"
        self.assertEqual(R.main(a), 3)
        man = self.manifest()
        a1 = by_name(man, "A_M1_cite")
        self.assertEqual(a1[0]["status"], "disk-start")
        lim = json.loads(Path(a1[0]["attempt_dir"], "attempt.json").read_text())["limits"]
        self.assertEqual(lim["disk_start_min_bytes"], 1000000 * GiB)
        cb = json.loads(Path(by_name(man, "cite_build")[0]["attempt_dir"], "attempt.json").read_text())["limits"]
        self.assertEqual(cb["disk_start_min_bytes"], 0)  # floor applies to R5 only
        self.assertEqual(R.R5_DISK_GIB, 4.0)
