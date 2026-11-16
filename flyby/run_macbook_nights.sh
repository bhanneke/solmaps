#!/bin/zsh
# Laptop help for the compute host's flyby queue (run_more_mini.sh). A LaunchAgent (com.solmaps.nights) calls this controller
# every 10 minutes; each call looks at the situation, adjusts the run and exits, so nothing has to be started or stopped by hand:
#   at home on mains power, 22:00-07:00   all in: no CPU cap
#   at home on mains power, daytime       capped at DAY_CPUS cores (changed live on the running container)
#   on battery, or away from home         paused; it continues where it stopped once both hold again
# "At home" means the default router has the home router's hardware address (HOME_GW_MAC), so a hotel or a phone hotspot
# never counts, even on mains power. Origins come from the END of the queue's list, so the two machines meet only after
# weeks; an origin the compute host has started is skipped. A finished origin's result file goes to the compute host's
# flyby folder, where the queue finds every window done and moves on. routes3 saves after every window.
# The run folder sits outside ~/Documents, which macOS closes to processes that launchd starts.
# TEST=1 only checks the environment.      Log: $RUN/nights.log
export PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
RUN=${RUN:-$HOME/Library/Application Support/solmaps-nights}
MINI=${MINI:-bjoernmacmini}; REMOTE='~/solmaps-flyby'; POOL=${POOL:-12}
HOME_GW_MAC=${HOME_GW_MAC:-6c:15:db:34:c7:6c}; DAY_CPUS=${DAY_CPUS:-3}; NIGHT_FROM=${NIGHT_FROM:-22}; NIGHT_TO=${NIGHT_TO:-7}
C=${C:-solmaps-nights}
# under launchd ssh does not find the default known_hosts by itself: name it
SSHO=(-o ConnectTimeout=15 -o BatchMode=yes -o UserKnownHostsFile=$HOME/.ssh/known_hosts)
log() { echo "$(date '+%F %T') $*" >> $RUN/nights.log; }
on_ac() { pmset -g batt | grep -q "AC Power"; }
at_home() { local gw=$(route -n get default 2>/dev/null | awk '/gateway/{print $2}'); [ -n "$gw" ] && arp -n "$gw" 2>/dev/null | grep -qi " $HOME_GW_MAC "; }
night() { local h=$(date +%H); h=$((10#$h)); (( h >= NIGHT_FROM || h < NIGHT_TO )); }
cpus() { night && docker info --format '{{.NCPU}}' || echo $DAY_CPUS; }   # all of Docker's cores; 'update --cpus 0' keeps a cap
mode() { night && echo "night, all in" || echo "day, $DAY_CPUS cores"; }
cd "$RUN" || exit 1
if [ -n "$TEST" ]; then log "test: docker $(docker info --format '{{.NCPU}} CPUs' 2>&1 | head -1), ssh $(ssh $SSHO $MINI echo ok 2>&1 | head -1), on AC: $(on_ac && echo yes || echo no), at home: $(at_home && echo yes || echo no), $(mode)"; exit 0; fi
docker info > /dev/null 2>&1 || exit 0                                     # Docker not up yet (after a restart): next call
ok=1; on_ac || ok=0; at_home || ok=0
why() { on_ac || { echo "on battery"; return; }; echo "away from home"; }
state=$(docker inspect -f '{{.State.Status}}' $C 2>/dev/null)
name=$(docker inspect -f '{{index .Config.Labels "job"}}' $C 2>/dev/null)

# a run exists: finished, or to be paused, resumed or re-capped
if [ "$state" = exited ]; then
  code=$(docker inspect -f '{{.State.ExitCode}}' $C); res=$(docker inspect -f '{{index .Config.Labels "result"}}' $C)
  docker rm $C > /dev/null; log "end $name exit $code"
  [ "$code" -eq 0 ] || exit 1
  f=$(ls -t flyby/routes3_${res}_*_2027_2097.json | head -1)
  if ssh $SSHO $MINI "grep -q 'start $name ' $REMOTE/queue.log"; then log "not copied: the compute host has started $name meanwhile"
  elif scp -q $SSHO "$f" $MINI:$REMOTE/flyby/; then log "copied $(basename $f) to the compute host"
  else log "COPY FAILED: $(basename $f) is still only on this laptop"; fi
  state=''
fi
if [ "$state" = running ] || [ "$state" = paused ]; then
  if [ $ok = 0 ]; then
    [ "$state" = running ] && { docker pause $C > /dev/null; log "paused $name: $(why)"; }
    exit 0
  fi
  [ "$state" = paused ] && { docker unpause $C > /dev/null; log "resumed $name"; }
  want=$(cpus); have=$(docker inspect -f '{{.HostConfig.NanoCpus}}' $C)
  if [ "$have" != "$((want * 1000000000))" ]; then docker update --cpus $want $C > /dev/null && log "$name: $(mode)"; fi
  caffeinate -i -t 660 < /dev/null > /dev/null 2>&1 &!                                                  # no idle sleep until the next call
  exit 0
fi
[ -n "$state" ] && exit 0                                                  # created/restarting: leave it to the next call
[ $ok = 1 ] || exit 0

# no run: start the next origin, last first
jobs=("${(@f)$(grep '^run other_' flyby/run_more_mini.sh | sed 's/^run //' | tail -r)}")
for line in $jobs; do
  name=${line%% *}; cmd=${line#* }
  grep -q " end $name exit 0$" nights.log 2>/dev/null && continue
  if ssh $SSHO $MINI "grep -q 'start $name ' $REMOTE/queue.log"; then log "stop: the compute host has reached $name"; break; fi
  res=${${cmd#*routes3.py }%% *}
  if docker run -d --name $C --label job=$name --label result=$res --cpus $(cpus) --memory=6g -e SOLMAPS_POOL=$POOL \
       -v "$RUN":/work -w /work solmaps-env:3 sh -c "${cmd} >> flyby/n_$name.log 2>&1" > /dev/null; then
    log "start $name ($(mode))"; caffeinate -i -t 660 < /dev/null > /dev/null 2>&1 &!
  else log "could not start $name"; fi
  exit 0
done
grep -q "nothing left for the nights" nights.log || log "nothing left for the nights"
