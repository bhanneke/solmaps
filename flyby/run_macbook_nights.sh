#!/bin/zsh
# Laptop help for the compute host's flyby queue (run_more_mini.sh). A LaunchAgent (com.solmaps.nights) calls this controller
# every 2 minutes (one call: under a second, ~55 MB for that moment); each call looks at the situation, adjusts the run and
# exits, so nothing has to be started or stopped by hand. The clock does not matter, only whether the laptop is in use:
#   nobody at the laptop                  all in: every core that other programs leave free, minus one
#   in use (input in the last IDLE_MIN    ACTIVE_CPUS cores; 1 core when other programs are busy as well
#   minutes, or a video or call keeps
#   the screen on)
#   on battery, or away from home         paused; it continues where it stopped once both hold again
# A lower cap applies at once; a higher one only when it is at least two cores higher, so the cap does not flutter.
# "At home" means the default router has the home router's hardware address (HOME_GW_MAC), so a hotel or a phone hotspot
# never counts, even on mains power. Origins come from the END of the queue's list, so the two machines meet only after
# weeks; an origin the compute host has started is skipped. A finished origin's result file goes to the compute host's
# flyby folder, where the queue finds every window done and moves on. routes3 saves after every window.
# The run folder sits outside ~/Documents, which macOS closes to processes that launchd starts.
# TEST=1 only checks the environment.      Log: $RUN/nights.log
export PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
RUN=${RUN:-$HOME/Library/Application Support/solmaps-nights}
MINI=${MINI:-bjoernmacmini}; REMOTE='~/solmaps-flyby'; POOL=${POOL:-12}
HOME_GW_MAC=${HOME_GW_MAC:-6c:15:db:34:c7:6c}; ACTIVE_CPUS=${ACTIVE_CPUS:-2}; IDLE_MIN=${IDLE_MIN:-10}
C=${C:-solmaps-nights}
# under launchd ssh does not find the default known_hosts by itself: name it
SSHO=(-o ConnectTimeout=15 -o BatchMode=yes -o UserKnownHostsFile=$HOME/.ssh/known_hosts)
log() { echo "$(date '+%F %T') $*" >> $RUN/nights.log; }
on_ac() { pmset -g batt | grep -q "AC Power"; }
at_home() { local gw=$(route -n get default 2>/dev/null | awk '/gateway/{print $2}'); [ -n "$gw" ] && arp -n "$gw" 2>/dev/null | grep -qi " $HOME_GW_MAC "; }
idle_s() { ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print int($NF / 1e9); exit}'; }      # seconds since keyboard/trackpad input
screen_kept() { pmset -g assertions | awk '$1 == "PreventUserIdleDisplaySleep" {exit !($2 > 0)}'; }   # video, calls, slides
in_use() { [ -n "$FORCE_IDLE" ] && return 1; [ -n "$FORCE_USE" ] && return 0; (( $(idle_s) < IDLE_MIN * 60 )) || screen_kept; }
# cores other programs use now (the Docker machine itself excluded), rounded up
others() { ps -A -o %cpu=,comm= | awk '!/Virtualization.VirtualMachine/ {s += $1} END {print int(s / 100 + 0.99)}'; }
CPUS_N=''
cpus() {                        # sets CPUS_N and MODE_TXT
  local n=$(docker info --format '{{.NCPU}}') o=$(others)
  if in_use; then CPUS_N=$ACTIVE_CPUS; (( o > 4 )) && CPUS_N=1; MODE_TXT="in use, $CPUS_N cores (others use $o)"
  else CPUS_N=$(( n - o - 1 )); (( CPUS_N < 1 )) && CPUS_N=1; (( CPUS_N > n )) && CPUS_N=$n; MODE_TXT="nobody at the laptop, $CPUS_N of $n cores (others use $o)"; fi
}
cd "$RUN" || exit 1
if [ -n "$TEST" ]; then log "test: docker $(docker info --format '{{.NCPU}} CPUs' 2>&1 | head -1), ssh $(ssh $SSHO $MINI echo ok 2>&1 | head -1), on AC: $(on_ac && echo yes || echo no), at home: $(at_home && echo yes || echo no), idle $(idle_s) s, screen kept on: $(screen_kept && echo yes || echo no), others $(others) cores"; exit 0; fi
# Docker must answer within 30 s. On 2026-11-20 its virtual machine died and every docker call hung for a day; now the
# controller logs it, and after three calls in a row without an answer (about 6 minutes) it restarts Docker Desktop.
docker info > /dev/null 2>&1 & dpid=$!
( sleep 30; kill $dpid 2>/dev/null ) > /dev/null 2>&1 &!
if ! wait $dpid; then
  n=$(( $(cat $RUN/docker_silent 2>/dev/null || echo 0) + 1 )); echo $n > $RUN/docker_silent
  if (( n >= 3 )); then
    log "Docker does not answer ($n checks): restarting Docker Desktop"; echo 0 > $RUN/docker_silent
    osascript -e 'quit app "Docker Desktop"' > /dev/null 2>&1; sleep 20; pkill -x "Docker Desktop"; open -a "Docker Desktop"
  else log "Docker does not answer (check $n)"; fi
  exit 0
fi
echo 0 > $RUN/docker_silent
[ -f $RUN/hold ] && exit 0                     # a test or maintenance holds the laptop: leave everything as it is
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
  cpus; have=$(( $(docker inspect -f '{{.HostConfig.NanoCpus}}' $C) / 1000000000 ))
  if (( CPUS_N < have || CPUS_N >= have + 2 )); then docker update --cpus $CPUS_N $C > /dev/null && log "$name: $MODE_TXT"; fi
  caffeinate -i -t 180 < /dev/null > /dev/null 2>&1 &!                     # no idle sleep until the next call
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
  cpus
  if docker run -d --name $C --label job=$name --label result=$res --cpus $CPUS_N --memory=6g -e SOLMAPS_POOL=$POOL \
       -v "$RUN":/work -w /work solmaps-env:3 sh -c "${cmd} >> flyby/n_$name.log 2>&1" > /dev/null; then
    log "start $name ($MODE_TXT)"; caffeinate -i -t 180 < /dev/null > /dev/null 2>&1 &!
  else log "could not start $name"; fi
  exit 0
done
grep -q "nothing left for the nights" nights.log || log "nothing left for the nights"
