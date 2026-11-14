#!/bin/zsh
# Overnight help for the compute host's flyby queue (run_more_mini.sh), on a laptop that runs only on mains power.
# It takes the queue's origin jobs from the END of the list, so the two machines meet only after weeks, and skips any origin the
# compute host has started. Each finished origin's result file goes to the compute host's flyby folder; when the queue reaches
# that origin it finds every window done and moves on. On battery the run stops; the next night resumes where it stopped
# (routes3 saves after every window). Same code, kernel and tables as the compute host, so the results are the same kind.
#   Start (on mains power): nohup zsh flyby/run_macbook_nights.sh > /dev/null 2>&1 &      Log: $RUN/nights.log
RUN=${RUN:-$HOME/Documents/Projects/Deep-Space-Strategy/solmaps/flyby-nights}
HOST=${HOST:-bjoernmacmini}; REMOTE='~/solmaps-flyby'; POOL=${POOL:-12}
log() { echo "$(date '+%F %T') $*" >> $RUN/nights.log; }
on_ac() { pmset -g batt | grep -q "AC Power"; }
cd $RUN || exit 1
# the queue's own commands, last origin first
jobs=("${(@f)$(grep '^run other_' flyby/run_more_mini.sh | sed 's/^run //' | tail -r)}")
for line in $jobs; do
  name=${line%% *}; cmd=${line#* }
  grep -q " end $name exit 0$" nights.log 2>/dev/null && continue
  if ssh -o ConnectTimeout=15 $HOST "grep -q 'start $name ' $REMOTE/queue.log"; then log "stop: the compute host has reached $name"; break; fi
  on_ac || { log "on battery: not starting $name"; exit 0; }
  log "start $name"
  caffeinate -i docker run --rm --name solmaps-nights --memory=6g -e SOLMAPS_POOL=$POOL -v $RUN:/work -w /work solmaps-env:3 ${=cmd} >> flyby/n_$name.log 2>&1 &
  pid=$!
  while kill -0 $pid 2>/dev/null; do
    if ! on_ac; then log "on battery: stopping $name (resumes next night)"; docker stop solmaps-nights > /dev/null; wait $pid; exit 0; fi
    sleep 60
  done
  wait $pid; code=$?; log "end $name exit $code"
  [ $code -eq 0 ] || exit 1
  f=$(ls -t flyby/routes3_${${cmd#*routes3.py }%% *}_*_2027_2097.json | head -1)
  if ssh -o ConnectTimeout=15 $HOST "grep -q 'start $name ' $REMOTE/queue.log"; then log "not copied: the compute host has started $name meanwhile"
  else scp -q "$f" $HOST:$REMOTE/flyby/ && log "copied $(basename $f) to the compute host"; fi
done
log "nothing left for the nights"
