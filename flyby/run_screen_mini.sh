#!/bin/zsh -l
# Catalogue screening on the Mac Mini (engine/screen.py): every object of the JPL Small-Body Database against Earth,
# Mars and Ceres. Runs in its own folder ~/solmaps-screen, next to the flyby queues in ~/solmaps, so those keep their
# code until they finish. Resumable: finished work units stay in ~/solmaps-screen/data/screen.
# Workers: SCREEN_WORKERS (default 4 while the flyby queues run; raise to 9 once they are done). Same disk guard as the
# queues: pause below 40 GB free on the root volume.
# Start: nohup zsh ~/solmaps-screen/flyby/run_screen_mini.sh > /dev/null 2>&1 &     Log: ~/solmaps-screen/screen.log
cd ~/solmaps-screen
IMAGE=solmaps-env:2
WORKERS=${SCREEN_WORKERS:-4}
log() { echo "$(date '+%F %T') $*" >> screen.log; }
room() { [ "$(df -g / | awk 'NR==2{print $4}')" -ge 40 ]; }
for attempt in 1 2 3; do
  while ! room; do log "waiting: root volume below 40 GB free"; sleep 1800; done
  log "start screening, $WORKERS workers (attempt $attempt)"
  docker run --rm --name solmaps-screen --cpus=$WORKERS --memory=1200m -v ~/solmaps-screen:/work -w /work $IMAGE \
    python -u -m engine.screen $WORKERS >> screen_run.log 2>&1 &
  pid=$!
  while kill -0 $pid 2>/dev/null; do
    if ! room; then log "stopping: root volume below 40 GB free"; docker stop solmaps-screen > /dev/null; fi
    sleep 600
  done
  wait $pid; code=$?
  log "end exit $code"
  [ $code -eq 0 ] && { log "screening finished"; break; }
done
