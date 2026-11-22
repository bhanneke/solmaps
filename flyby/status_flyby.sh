#!/bin/zsh
# Daily status of the flyby search on both machines: what finished in the last 24 hours, what runs now and how far it is,
# and anything wrong (failed jobs, failed copies, low disk, stopped containers). Read-only.
export PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
R="$HOME/Library/Application Support/solmaps-nights"; MINI=${MINI:-bjoernmacmini}
SSHO=(-o ConnectTimeout=15 -o BatchMode=yes)
since=$(date -v-24H '+%F %T'); echo "now $(date '+%F %T'), events since $since"
progress() {   # $1 log file: routes so far, destinations started of 29, current destination
  local n=$(grep -c '^{' "$1" 2>/dev/null) d=$(grep '^sequences' "$1" 2>/dev/null | awk '{print $3}' | awk "!seen[\$0]++")
  echo "$n routes, destination $(echo "$d" | grep -c .) of 29 ($(echo "$d" | tail -1))"
}
echo "== MacBook"
awk -v s="$since" '($1 " " $2) >= s && /end |start |copied|COPY|could not|paused|resumed|stop:|nothing left/' "$R/nights.log" | grep -v "test:"
c=$(docker inspect -f '{{.State.Status}} {{index .Config.Labels "job"}} cores={{.HostConfig.NanoCpus}}' solmaps-nights 2>/dev/null)
if [ -n "$c" ]; then j=$(echo $c | awk '{print $2}'); echo "container: ${c/000000000/}; $(progress "$R/flyby/n_$j.log")"; else echo "container: none"; fi
launchctl print gui/$(id -u)/com.solmaps.nights 2>/dev/null | grep -E "last exit code" | head -1
echo "== Mac Mini"
ssh $SSHO $MINI "since='$since'"'; export PATH=/usr/local/bin:/opt/homebrew/bin:$PATH; uptime; df -h / | tail -1 | awk "{print \"disk free \" \$4}"
  awk -v s="$since" "(\$1 \" \" \$2) >= s" ~/solmaps-flyby/queue.log
  c=$(docker ps --format "{{.Names}} {{.Status}}" | grep solmaps); echo "container: ${c:-none}"
  j=$(echo "$c" | sed -E "s/^solmaps-([^ ]+).*/\1/"); f=$(ls -t ~/solmaps-flyby/flyby/*$j*.log 2>/dev/null | head -1)
  [ -n "$f" ] && echo "log $(basename $f): $(grep -c "^{" $f) routes, destination $(grep "^sequences" $f | awk "{print \$3}" | sort -u | grep -c .) of 29 ($(grep "^sequences" $f | awk "{print \$3}" | tail -1))"
  grep -c "^20.* end .* exit 0" ~/solmaps-flyby/queue.log | sed "s/^/jobs finished in total: /"' 2>&1
