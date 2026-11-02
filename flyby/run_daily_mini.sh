#!/bin/zsh -l
# Daily transfer data (engine/daily.py) on the Mac Mini, in its own folder ~/solmaps-daily next to the flyby queues and
# the catalogue screening. Resumable: finished origins stay in ~/solmaps-daily/data/daily; an interrupted origin
# starts again. Needs the Horizons files in flyby/horizons (copied from the release machine, not fetched again, so the
# positions match the audited data) and the image solmaps-env:3.
# Processes: DAILY_PROCS (default 3 while the other jobs run). Same disk guard as the queues: pause below 40 GB free.
# Start: nohup zsh -l ~/solmaps-daily/flyby/run_daily_mini.sh > /dev/null 2>&1 &     Log: ~/solmaps-daily/daily.log
cd ~/solmaps-daily
IMAGE=solmaps-env:3
PROCS=${DAILY_PROCS:-3}
log() { echo "$(date '+%F %T') $*" >> daily.log; }
room() { [ "$(df -g / | awk 'NR==2{print $4}')" -ge 40 ]; }
for attempt in 1 2 3 4 5; do
  while ! room; do log "waiting: root volume below 40 GB free"; sleep 1800; done
  log "start daily, $PROCS processes (attempt $attempt)"
  docker run --rm --name solmaps-daily --cpus=$PROCS --memory=1400m -v ~/solmaps-daily:/work -w /work $IMAGE \
    python -u -m engine.daily $PROCS >> daily_run.log 2>&1 &
  pid=$!
  while kill -0 $pid 2>/dev/null; do
    if ! room; then log "stopping: root volume below 40 GB free"; docker stop solmaps-daily > /dev/null; fi
    sleep 300
  done
  wait $pid; code=$?
  log "end exit $code"
  [ $code -eq 0 ] && { log "daily finished"; break; }
  sleep 60
done
