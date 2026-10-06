#!/bin/zsh
# Sequential main-analysis queue. Usage: queue_main.sh <workspace> <data_run_dir>
# Each step is timed with /usr/bin/time -l; a step is skipped when its .done marker exists,
# so the queue can be relaunched after an interruption without redoing finished work.
set -u
W=$1; D=$2
cd $W
PY=$W/companion/.venv/bin/python
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 PYTHONWARNINGS=ignore
Q=$W/runs/queue-main; mkdir -p $Q
log() { echo "[$(date -u +%FT%TZ)] $*" >> $Q/queue.log }
step() {  # step <name> <outdir> <cmd...>
  local name=$1 out=$2; shift 2
  if [[ -f $Q/$name.done ]]; then log "skip $name (done)"; return 0; fi
  local free=$(df -k $W | tail -1 | awk '{print $4/1048576}') waited=0
  while (( free < 0.4 )); do
    (( waited == 0 )) && log "disk guard: ${free} GiB free before $name; waiting"
    (( waited >= 7200 )) && { log "STOP disk guard before $name: ${free} GiB after 2 h"; exit 3; }
    sleep 30; waited=$((waited+30)); free=$(df -k $W | tail -1 | awk '{print $4/1048576}')
  done
  mkdir -p $out
  log "start $name -> $out"
  /usr/bin/time -l "$@" > $out/$name.stdout 2> $out/$name.stderr
  local rc=$?
  if [[ $rc -ne 0 ]]; then log "FAIL $name rc=$rc (see $out/$name.stderr)"; echo $rc > $out/$name.FAILED; return $rc; fi
  echo "$out" > $Q/$name.done; log "done $name"
}
dirvar() { [[ -f $Q/$1.dir ]] || echo "$W/runs/$1-$(date -u +%Y%m%dT%H%M%SZ)" > $Q/$1.dir; cat $Q/$1.dir }

[[ -f $D/receipt.json ]] || { log "data run incomplete: $D"; exit 2; }
TA=$(dirvar T01-matched-armA); TB=$(dirvar T02-matched-armB)
for arm in A B; do
  T=$TA; [[ $arm == B ]] && T=$TB
  for m in M1 M2 M3 M4 M5 M6; do
    step ${arm}_${m}_fit $T/$m $PY companion/scripts/run_matched.py --workspace $W --data $D --arm $arm --method $m --stage fit --out $T/$m || exit 1
    step ${arm}_${m}_predict $T/$m $PY companion/scripts/run_matched.py --workspace $W --data $D --arm $arm --method $m --stage predict --out $T/$m || exit 1
  done
done
CI=$(dirvar C01-cite-build)
step cite_build $CI $PY companion/scripts/build_cite.py --workspace $W --data $D --out $CI || log "cite build failed; continuing without protein check"
TC=$(dirvar T03-matched-armA-cite)
if [[ -f $Q/cite_build.done ]]; then
  for m in M1 M2 M3 M4 M5 M6; do
    step A_${m}_cite $TC/$m $PY companion/scripts/run_matched.py --workspace $W --data $CI --arm A --method $m --stage predict --model-dir $TA/$m --out $TC/$m || log "cite predict $m failed"
  done
fi
SC=$(dirvar SC01-score)
step score $SC $PY companion/scripts/score_all.py --workspace $W --data $D --matched A=$TA B=$TB --out $SC || exit 1
if [[ -f $Q/cite_build.done ]]; then
  PC=$(dirvar PC01-protein)
  step protein $PC $PY companion/scripts/protein_check.py --workspace $W --cite $CI --matched A=$TC --thresholds $SC/thresholds_validation.csv --out $PC
fi
log "queue complete"
