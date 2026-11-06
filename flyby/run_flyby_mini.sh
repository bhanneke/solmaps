#!/bin/zsh -l
# Flyby searches and the jobs after them on the compute host, one Docker run at a time, in its own clone ~/solmaps-flyby with the
# compiled fitness and the daily JPL Horizons files. Resumable: routes3 saves after every window. Pause below 40 GB free on the root volume.
# Needs: engine/fortran/flyby_fit.so, data/flyby_tables, flyby/horizons (copied from the release machine).
# Start: nohup zsh -l ~/solmaps-flyby/flyby/run_flyby_mini.sh > /dev/null 2>&1 &     Log: ~/solmaps-flyby/queue.log
cd ~/solmaps-flyby
IMAGE=solmaps-env:3; POOL=${FLYBY_POOL:-6}
log() { echo "$(date '+%F %T') $*" >> queue.log; }
room() { [ "$(df -g / | awk 'NR==2{print $4}')" -ge 40 ]; }
run() {   # run NAME CMD...: one container, guarded, up to three attempts
  name=$1; shift
  grep -q "^.* end $name exit 0$" queue.log 2>/dev/null && return 0
  for attempt in 1 2 3; do
    while ! room; do log "waiting: root volume below 40 GB free"; sleep 1800; done
    log "start $name (attempt $attempt)"
    docker run --rm --name solmaps-$name --memory=2000m -e SOLMAPS_POOL=$POOL -v ~/solmaps-flyby:/work -w /work $IMAGE "$@" >> flyby/q_$name.log 2>&1 &
    pid=$!
    while kill -0 $pid 2>/dev/null; do
      if ! room; then log "stopping $name: root volume below 40 GB free"; docker stop solmaps-$name > /dev/null; fi
      sleep 300
    done
    wait $pid; code=$?
    log "end $name exit $code"
    [ $code -eq 0 ] && return 0
  done
}
B="2027 2097 8 1000 60 6 3"
run returns_ceres   python flyby/routes3.py ceres earth,mars ${=B}
run returns_vesta   python flyby/routes3.py vesta earth,mars ${=B}
run returns_psyche  python flyby/routes3.py psyche earth,mars ${=B}
run returns_jupiter python flyby/routes3.py jupiter earth,mars ${=B}
run earth_outer     python flyby/routes3.py earth jupiter,saturn,mercury ${=B}
run earth_belt      python flyby/routes3.py earth ceres,vesta,psyche ${=B}
run earth_near      python flyby/routes3.py earth mars,venus,433,101955,162173 ${=B}
run mars_outer      python flyby/routes3.py mars jupiter,saturn ${=B}
run mars_belt       python flyby/routes3.py mars ceres,vesta,psyche ${=B}
run mars_inner      python flyby/routes3.py mars earth,venus,mercury ${=B}
run saturn_back     python flyby/routes3.py saturn earth,mars ${=B}
run cyclers         python flyby/cyclers.py 2027 2097 8 2000 30 6
run lowthrust       python -m engine.lt_atlas
run trajectories    python flyby/trajectories.py
log "queue finished"
