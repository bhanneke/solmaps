#!/bin/zsh
# Overnight help for the compute host's flyby queue (run_more_mini.sh), on a laptop that runs only on mains power.
# It takes the queue's origin jobs from the END of the list, so the two machines meet only after weeks, and skips any origin the
# compute host has started. Each finished origin's result file goes to the compute host's flyby folder; when the queue reaches
# that origin it finds every window done and moves on. On battery the run stops; the next night resumes where it stopped
# (routes3 saves after every window). Same code, kernel and tables as the compute host, so the results are the same kind.
# A LaunchAgent (com.solmaps.nights) starts it every evening and hourly until 02:07; the run folder sits outside ~/Documents,
# which macOS closes to processes that launchd starts. TEST=1 only checks the environment.      Log: $RUN/nights.log
export PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
RUN=${RUN:-$HOME/Library/Application Support/solmaps-nights}
MINI=${MINI:-bjoernmacmini}; REMOTE='~/solmaps-flyby'; POOL=${POOL:-12}
# under launchd ssh does not find the default known_hosts by itself: name it
SSHO=(-o ConnectTimeout=15 -o BatchMode=yes -o UserKnownHostsFile=$HOME/.ssh/known_hosts)
log() { echo "$(date '+%F %T') $*" >> $RUN/nights.log; }
on_ac() { pmset -g batt | grep -q "AC Power"; }
cd "$RUN" || exit 1
if [ -n "$TEST" ]; then log "test: docker $(docker info --format '{{.NCPU}} CPUs' 2>&1 | head -1), ssh $(ssh $SSHO $MINI echo ok 2>&1 | head -1), on AC: $(on_ac && echo yes || echo no)"; exit 0; fi
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^solmaps-nights$'; then exit 0; fi       # a run is already going
# the queue's own commands, last origin first
jobs=("${(@f)$(grep '^run other_' flyby/run_more_mini.sh | sed 's/^run //' | tail -r)}")
for line in $jobs; do
  name=${line%% *}; cmd=${line#* }
  grep -q " end $name exit 0$" nights.log 2>/dev/null && continue
  if ssh $SSHO $MINI "grep -q 'start $name ' $REMOTE/queue.log"; then log "stop: the compute host has reached $name"; break; fi
  on_ac || { log "on battery: not starting $name"; exit 0; }
  log "start $name"
  caffeinate -i docker run --rm --name solmaps-nights --memory=6g -e SOLMAPS_POOL=$POOL -v "$RUN":/work -w /work solmaps-env:3 ${=cmd} >> flyby/n_$name.log 2>&1 &
  pid=$!
  while kill -0 $pid 2>/dev/null; do
    if ! on_ac; then log "on battery: stopping $name (resumes next night)"; docker stop solmaps-nights > /dev/null; wait $pid; exit 0; fi
    sleep 60
  done
  wait $pid; code=$?; log "end $name exit $code"
  [ $code -eq 0 ] || exit 1
  f=$(ls -t flyby/routes3_${${cmd#*routes3.py }%% *}_*_2027_2097.json | head -1)
  if ssh $SSHO $MINI "grep -q 'start $name ' $REMOTE/queue.log"; then log "not copied: the compute host has started $name meanwhile"
  else scp -q $SSHO "$f" $MINI:$REMOTE/flyby/ && log "copied $(basename $f) to the compute host"; fi
done
log "nothing left for the nights"
