#!/usr/bin/env python3
"""Foreground resource-guard launcher (OA-4/OA-5, protocol/resume-plan-reviewed.md).

Standard library only. Runs ONE attempt of a command in a fresh, immutable attempt
directory, in its own process group, and polls:
  * aggregate memory over the process group + descendants: macOS phys_footprint via
    proc_pid_rusage (primary); RSS from `ps` as a labelled fallback (status
    `memory-watchdog-rss` when an RSS reading triggers the stop);
  * growth of `sysctl vm.swapusage` used (> swap_growth limit -> memory-stop);
  * free disk (start floor, running floor) and study storage cap (du over cap paths);
  * wall-clock timeout.
Env: OMP/MKL/OPENBLAS/NUMEXPR/VECLIB threads = 4 (configurable), TMPDIR/JOBLIB_TEMP_FOLDER
into the attempt scratch dir (deleted after the attempt), caches via --env.

Usage:
  resource_guard.py --attempt-root DIR --name STEP [limits...] -- cmd args...
Writes DIR/<STEP>/attempt-<n>-<UTC>/{attempt.json,stdout.log,stderr.log,samples.jsonl}.
Exit code: 0 ok; otherwise non-zero with attempt.json "status" in
{failed, memory-stop, memory-watchdog-rss, swap-stop, disk-start, disk-stop,
 storage-cap, timeout, launch-error}.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import datetime as dt
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

GiB = 1 << 30
INFRA_STATUSES = {"memory-stop", "memory-watchdog-rss", "swap-stop", "disk-stop", "timeout", "launch-error"}

# ---------------------------------------------------------------- measurement


class _RusageV0(ctypes.Structure):
    _fields_ = [("ri_uuid", ctypes.c_uint8 * 16)] + [(n, ctypes.c_uint64) for n in (
        "ri_user_time", "ri_system_time", "ri_pkg_idle_wkups", "ri_interrupt_wkups", "ri_pageins",
        "ri_wired_size", "ri_resident_size", "ri_phys_footprint", "ri_proc_start_abstime",
        "ri_proc_exit_abstime")]


_libproc = None
if sys.platform == "darwin":
    try:
        _libproc = ctypes.CDLL(ctypes.util.find_library("proc") or "/usr/lib/libproc.dylib")
        _libproc.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(_RusageV0)]
    except OSError:
        _libproc = None


def phys_footprint(pid: int) -> int | None:
    """Bytes of macOS phys_footprint for pid, or None if unavailable."""
    if _libproc is None:
        return None
    ri = _RusageV0()
    if _libproc.proc_pid_rusage(pid, 0, ctypes.byref(ri)) != 0:
        return None
    return int(ri.ri_phys_footprint)


def process_table() -> list[tuple[int, int, int, int]]:
    """(pid, ppid, pgid, rss_bytes) for all processes."""
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,pgid=,rss="], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        f = line.split()
        if len(f) == 4 and all(x.isdigit() for x in f):
            rows.append((int(f[0]), int(f[1]), int(f[2]), int(f[3]) * 1024))
    return rows


def group_members(root_pid: int, pgid: int) -> list[tuple[int, int]]:
    """Members of the process group plus all descendants of root (even if they changed group)."""
    table = process_table()
    children: dict[int, list[int]] = {}
    for pid, ppid, _, _ in table:
        children.setdefault(ppid, []).append(pid)
    desc, stack = set(), [root_pid]
    while stack:
        p = stack.pop()
        if p in desc:
            continue
        desc.add(p)
        stack.extend(children.get(p, []))
    return [(pid, rss) for pid, _, g, rss in table if g == pgid or pid in desc]


def aggregate_memory(root_pid: int, pgid: int) -> dict:
    members = group_members(root_pid, pgid)
    fp_total, rss_total, fp_ok = 0, 0, True
    for pid, rss in members:
        rss_total += rss
        fp = phys_footprint(pid)
        if fp is None:
            fp_ok = False
        else:
            fp_total += fp
    return {"pids": [p for p, _ in members], "rss_bytes": rss_total,
            "phys_footprint_bytes": fp_total if fp_ok and members else None,
            "measure": "phys_footprint" if fp_ok and members else "rss-fallback"}


def swap_used_bytes() -> int | None:
    try:
        out = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
    except OSError:
        return None
    m = re.search(r"used\s*=\s*([\d.]+)([KMGT])", out)
    if not m:
        return None
    return int(float(m.group(1)) * {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30, "T": 1 << 40}[m.group(2)])


def free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def tree_bytes(paths: list[Path]) -> int:
    total = 0
    for root in paths:
        if not root.exists():
            continue
        for dp, _, fns in os.walk(root, followlinks=False):
            for fn in fns:
                try:
                    st = os.lstat(os.path.join(dp, fn))
                    total += st.st_blocks * 512
                except OSError:
                    pass
    return total


# ---------------------------------------------------------------- launcher


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def new_attempt_dir(root: Path, name: str) -> tuple[Path, int]:
    base = root / name
    base.mkdir(parents=True, exist_ok=True)
    n = len([p for p in base.iterdir() if p.name.startswith("attempt-")]) + 1
    d = base / f"attempt-{n}-{utc()}"
    d.mkdir(parents=False, exist_ok=False)  # immutable: never reuse an existing attempt dir
    return d, n


def kill_group(pgid: int, root_pid: int, grace: float = 5.0, proc=None) -> None:
    targets = {pid for pid, _ in group_members(root_pid, pgid)} - {root_pid}
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            pass
        for pid in targets:  # descendants that left the group
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
        t0 = time.time()
        while time.time() - t0 < grace:
            root_done = proc is None or proc.poll() is not None  # Popen reaps root, keeping its returncode
            if root_done and not any(_alive(p) for p in targets):
                return
            time.sleep(0.1)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_guarded(cmd: list[str], *, attempt_root: Path, name: str, mem_limit: int = 12 * GiB,
                swap_growth_limit: int = 4 * GiB, disk_start_min: int = 3 * GiB,
                disk_run_min: int = int(1.5 * GiB), disk_path: Path | None = None,
                storage_cap: int = 7 * GiB, cap_paths: list[Path] | None = None,
                timeout: float = 3600.0, mem_poll: float = 5.0, disk_poll: float = 30.0,
                threads: int = 4, extra_env: dict | None = None, cwd: Path | None = None,
                meta: dict | None = None) -> dict:
    adir, n = new_attempt_dir(attempt_root, name)
    scratch = adir / "scratch"
    scratch.mkdir()
    disk_path = disk_path or attempt_root
    cap_paths = cap_paths or []
    rec = {"name": name, "attempt": n, "attempt_dir": str(adir), "command": cmd, "cwd": str(cwd or os.getcwd()),
           "limits": {"mem_limit_bytes": mem_limit, "swap_growth_limit_bytes": swap_growth_limit,
                      "disk_start_min_bytes": disk_start_min, "disk_run_min_bytes": disk_run_min,
                      "storage_cap_bytes": storage_cap, "cap_paths": [str(p) for p in cap_paths],
                      "timeout_s": timeout, "mem_poll_s": mem_poll, "disk_poll_s": disk_poll, "threads": threads},
           "meta": meta or {}, "start_utc": utc(), "status": None, "returncode": None,
           "peak_phys_footprint_bytes": 0, "peak_rss_bytes": 0, "measure_used": set(),
           "measurement_note": ("phys_footprint summed over process group+descendants via proc_pid_rusage; "
                                "RSS is a fallback that double-counts shared pages and is labelled when used")}
    env = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS"):
        env[k] = str(threads)
    env.update({"TMPDIR": str(scratch), "JOBLIB_TEMP_FOLDER": str(scratch), "TEMP": str(scratch),
                "TMP": str(scratch), "PYTHONDONTWRITEBYTECODE": "1"})
    env.update(extra_env or {})
    rec["env_overrides"] = {k: env[k] for k in sorted(set(env) - set(os.environ) | set(extra_env or {}) |
                                                      {"OMP_NUM_THREADS", "TMPDIR", "JOBLIB_TEMP_FOLDER"})}

    def finish(status, rc=None):
        rec["status"], rec["returncode"] = status, rc
        rec["end_utc"] = utc()
        rec["wall_seconds"] = round(time.time() - t_start, 3)
        rec["measure_used"] = sorted(rec["measure_used"])
        shutil.rmtree(scratch, ignore_errors=True)
        rec["scratch_deleted"] = not scratch.exists()
        (adir / "attempt.json").write_text(json.dumps(rec, indent=1, default=str))
        return rec

    t_start = time.time()
    free0 = free_bytes(disk_path)
    rec["free_bytes_start"] = free0
    if free0 < disk_start_min:
        return finish("disk-start")
    used0 = tree_bytes(cap_paths)
    if cap_paths and used0 > storage_cap:
        return finish("storage-cap")
    swap0 = swap_used_bytes()
    rec["swap_used_start_bytes"] = swap0
    out = open(adir / "stdout.log", "wb")
    err = open(adir / "stderr.log", "wb")
    samples = open(adir / "samples.jsonl", "w")
    try:
        proc = subprocess.Popen(cmd, stdout=out, stderr=err, env=env, cwd=cwd, start_new_session=True)
    except OSError as e:
        rec["launch_error"] = repr(e)
        out.close(); err.close(); samples.close()
        return finish("launch-error")
    pgid = proc.pid  # start_new_session -> pid == pgid
    rec["pid"] = pgid
    status = None
    last_disk = 0.0
    try:
        while True:
            rc = proc.poll()
            if rc is not None:
                break
            now = time.time()
            if now - t_start > timeout:
                status = "timeout"
                break
            m = aggregate_memory(proc.pid, pgid)
            rec["measure_used"].add(m["measure"])
            rec["peak_rss_bytes"] = max(rec["peak_rss_bytes"], m["rss_bytes"])
            if m["phys_footprint_bytes"] is not None:
                rec["peak_phys_footprint_bytes"] = max(rec["peak_phys_footprint_bytes"], m["phys_footprint_bytes"])
            s = {"t": round(now - t_start, 2), **m}
            swap = swap_used_bytes()
            s["swap_used_bytes"] = swap
            if m["phys_footprint_bytes"] is not None:
                if m["phys_footprint_bytes"] > mem_limit:
                    status = "memory-stop"
            elif m["rss_bytes"] > mem_limit:
                status = "memory-watchdog-rss"
            if status is None and swap is not None and swap0 is not None and swap - swap0 > swap_growth_limit:
                status = "swap-stop"
            if status is None and now - last_disk >= disk_poll:
                last_disk = now
                s["free_bytes"] = fb = free_bytes(disk_path)
                if fb < disk_run_min:
                    status = "disk-stop"
                elif cap_paths:
                    s["cap_used_bytes"] = cu = tree_bytes(cap_paths)
                    if cu > storage_cap:
                        status = "storage-cap"
            samples.write(json.dumps(s) + "\n"); samples.flush()
            if status:
                break
            time.sleep(mem_poll)
    except KeyboardInterrupt:
        status = "interrupted"
    finally:
        if status is not None:
            kill_group(pgid, proc.pid, proc=proc)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        else:
            # leftover descendants after a normal exit are also killed and recorded
            left = [p for p, _ in group_members(proc.pid, pgid) if p != proc.pid]
            if left:
                rec["leftover_descendants_killed"] = left
                kill_group(pgid, proc.pid, proc=proc)
        out.close(); err.close(); samples.close()
    if status is None:
        status = "ok" if proc.returncode == 0 else "failed"
    rec["swap_used_end_bytes"] = swap_used_bytes()
    return finish(status, proc.returncode)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--attempt-root", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--mem-limit-gib", type=float, default=12.0)
    ap.add_argument("--swap-growth-gib", type=float, default=4.0)
    ap.add_argument("--disk-start-gib", type=float, default=3.0)
    ap.add_argument("--disk-run-gib", type=float, default=1.5)
    ap.add_argument("--disk-path", default=None)
    ap.add_argument("--storage-cap-gib", type=float, default=7.0)
    ap.add_argument("--cap-path", action="append", default=[])
    ap.add_argument("--timeout", type=float, default=3600)
    ap.add_argument("--mem-poll", type=float, default=5.0)
    ap.add_argument("--disk-poll", type=float, default=30.0)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--env", action="append", default=[], help="KEY=VALUE")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        ap.error("missing command after --")
    rec = run_guarded(cmd, attempt_root=Path(a.attempt_root), name=a.name, mem_limit=int(a.mem_limit_gib * GiB),
                      swap_growth_limit=int(a.swap_growth_gib * GiB), disk_start_min=int(a.disk_start_gib * GiB),
                      disk_run_min=int(a.disk_run_gib * GiB), disk_path=Path(a.disk_path) if a.disk_path else None,
                      storage_cap=int(a.storage_cap_gib * GiB), cap_paths=[Path(p) for p in a.cap_path],
                      timeout=a.timeout, mem_poll=a.mem_poll, disk_poll=a.disk_poll, threads=a.threads,
                      extra_env=dict(e.split("=", 1) for e in a.env))
    print(json.dumps({k: rec[k] for k in ("name", "attempt", "attempt_dir", "status", "returncode", "wall_seconds")}))
    return 0 if rec["status"] == "ok" else (2 if rec["status"] in INFRA_STATUSES else 1)


if __name__ == "__main__":
    sys.exit(main())
