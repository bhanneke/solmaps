#!/bin/zsh -l
# Third queue on the compute host (2026-11-12): the second and third independent run of every flyby search (FLYBY_RERUN=1 and 2:
# other seeds, own files routes3_..._rerun<k>.json), first the 29 routes of the first block, then the other 841. All runs stay,
# so contributors can verify any window against three results; the pages use the best of them.
# Needs: engine/fortran/flyby_fit.so, data/flyby_tables, flyby/horizons (copied from the release machine).
# Start: nohup zsh -l ~/solmaps-flyby/flyby/run_reruns_mini.sh > /dev/null 2>&1 &     Log: ~/solmaps-flyby/queue.log
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
    docker run --rm --name solmaps-$name --memory=2000m -e SOLMAPS_POOL=$POOL ${=RUNENV} -v ~/solmaps-flyby:/work -w /work $IMAGE "$@" >> flyby/q_$name.log 2>&1 &
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

RUNENV="-e FLYBY_RERUN=1"
run returns_ceres_r1 python flyby/routes3.py ceres earth,mars 2027 2097 8 1000 60 6 3
run returns_vesta_r1 python flyby/routes3.py vesta earth,mars 2027 2097 8 1000 60 6 3
run returns_psyche_r1 python flyby/routes3.py psyche earth,mars 2027 2097 8 1000 60 6 3
run returns_jupiter_r1 python flyby/routes3.py jupiter earth,mars 2027 2097 8 1000 60 6 3
run earth_outer_r1 python flyby/routes3.py earth jupiter,saturn,mercury 2027 2097 8 1000 60 6 3
run earth_belt_r1 python flyby/routes3.py earth ceres,vesta,psyche 2027 2097 8 1000 60 6 3
run earth_near_r1 python flyby/routes3.py earth mars,venus,433,101955,162173 2027 2097 8 1000 60 6 3
run mars_outer_r1 python flyby/routes3.py mars jupiter,saturn 2027 2097 8 1000 60 6 3
run mars_belt_r1 python flyby/routes3.py mars ceres,vesta,psyche 2027 2097 8 1000 60 6 3
run mars_inner_r1 python flyby/routes3.py mars earth,venus,mercury 2027 2097 8 1000 60 6 3
run saturn_back_r1 python flyby/routes3.py saturn earth,mars 2027 2097 8 1000 60 6 3
RUNENV="-e FLYBY_RERUN=2"
run returns_ceres_r2 python flyby/routes3.py ceres earth,mars 2027 2097 8 1000 60 6 3
run returns_vesta_r2 python flyby/routes3.py vesta earth,mars 2027 2097 8 1000 60 6 3
run returns_psyche_r2 python flyby/routes3.py psyche earth,mars 2027 2097 8 1000 60 6 3
run returns_jupiter_r2 python flyby/routes3.py jupiter earth,mars 2027 2097 8 1000 60 6 3
run earth_outer_r2 python flyby/routes3.py earth jupiter,saturn,mercury 2027 2097 8 1000 60 6 3
run earth_belt_r2 python flyby/routes3.py earth ceres,vesta,psyche 2027 2097 8 1000 60 6 3
run earth_near_r2 python flyby/routes3.py earth mars,venus,433,101955,162173 2027 2097 8 1000 60 6 3
run mars_outer_r2 python flyby/routes3.py mars jupiter,saturn 2027 2097 8 1000 60 6 3
run mars_belt_r2 python flyby/routes3.py mars ceres,vesta,psyche 2027 2097 8 1000 60 6 3
run mars_inner_r2 python flyby/routes3.py mars earth,venus,mercury 2027 2097 8 1000 60 6 3
run saturn_back_r2 python flyby/routes3.py saturn earth,mars 2027 2097 8 1000 60 6 3
RUNENV="-e FLYBY_RERUN=1"
run other_earth_r1 python flyby/routes3.py earth uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_venus_r1 python flyby/routes3.py venus earth,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_mercury_r1 python flyby/routes3.py mercury earth,venus,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_mars_r1 python flyby/routes3.py mars 433,101955,162173,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_ceres_r1 python flyby/routes3.py ceres venus,mercury,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_vesta_r1 python flyby/routes3.py vesta venus,mercury,ceres,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_psyche_r1 python flyby/routes3.py psyche venus,mercury,ceres,vesta,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_433_r1 python flyby/routes3.py 433 earth,venus,mercury,mars,ceres,vesta,psyche,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_101955_r1 python flyby/routes3.py 101955 earth,venus,mercury,mars,ceres,vesta,psyche,433,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_162173_r1 python flyby/routes3.py 162173 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_jupiter_r1 python flyby/routes3.py jupiter venus,mercury,ceres,vesta,psyche,433,101955,162173,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_saturn_r1 python flyby/routes3.py saturn venus,mercury,ceres,vesta,psyche,433,101955,162173,jupiter,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_uranus_r1 python flyby/routes3.py uranus earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_neptune_r1 python flyby/routes3.py neptune earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_pluto_r1 python flyby/routes3.py pluto earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_2_r1 python flyby/routes3.py 2 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_10_r1 python flyby/routes3.py 10 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_24_r1 python flyby/routes3.py 24 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_3_r1 python flyby/routes3.py 3 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_99942_r1 python flyby/routes3.py 99942 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_65803_r1 python flyby/routes3.py 65803 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_25143_r1 python flyby/routes3.py 25143 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_341843_r1 python flyby/routes3.py 341843 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_175706_r1 python flyby/routes3.py 175706 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_4660_r1 python flyby/routes3.py 4660 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_3548_r1 python flyby/routes3.py 3548 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_15094_r1 python flyby/routes3.py 15094 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,11351,21900,617 2027 2097 8 1000 60 6 3
run other_11351_r1 python flyby/routes3.py 11351 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,21900,617 2027 2097 8 1000 60 6 3
run other_21900_r1 python flyby/routes3.py 21900 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,617 2027 2097 8 1000 60 6 3
run other_617_r1 python flyby/routes3.py 617 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900 2027 2097 8 1000 60 6 3
RUNENV="-e FLYBY_RERUN=2"
run other_earth_r2 python flyby/routes3.py earth uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_venus_r2 python flyby/routes3.py venus earth,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_mercury_r2 python flyby/routes3.py mercury earth,venus,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_mars_r2 python flyby/routes3.py mars 433,101955,162173,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_ceres_r2 python flyby/routes3.py ceres venus,mercury,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_vesta_r2 python flyby/routes3.py vesta venus,mercury,ceres,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_psyche_r2 python flyby/routes3.py psyche venus,mercury,ceres,vesta,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_433_r2 python flyby/routes3.py 433 earth,venus,mercury,mars,ceres,vesta,psyche,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_101955_r2 python flyby/routes3.py 101955 earth,venus,mercury,mars,ceres,vesta,psyche,433,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_162173_r2 python flyby/routes3.py 162173 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_jupiter_r2 python flyby/routes3.py jupiter venus,mercury,ceres,vesta,psyche,433,101955,162173,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_saturn_r2 python flyby/routes3.py saturn venus,mercury,ceres,vesta,psyche,433,101955,162173,jupiter,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_uranus_r2 python flyby/routes3.py uranus earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_neptune_r2 python flyby/routes3.py neptune earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_pluto_r2 python flyby/routes3.py pluto earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_2_r2 python flyby/routes3.py 2 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_10_r2 python flyby/routes3.py 10 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_24_r2 python flyby/routes3.py 24 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_3_r2 python flyby/routes3.py 3 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_99942_r2 python flyby/routes3.py 99942 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_65803_r2 python flyby/routes3.py 65803 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_25143_r2 python flyby/routes3.py 25143 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_341843_r2 python flyby/routes3.py 341843 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_175706_r2 python flyby/routes3.py 175706 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_4660_r2 python flyby/routes3.py 4660 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_3548_r2 python flyby/routes3.py 3548 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_15094_r2 python flyby/routes3.py 15094 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,11351,21900,617 2027 2097 8 1000 60 6 3
run other_11351_r2 python flyby/routes3.py 11351 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,21900,617 2027 2097 8 1000 60 6 3
run other_21900_r2 python flyby/routes3.py 21900 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,617 2027 2097 8 1000 60 6 3
run other_617_r2 python flyby/routes3.py 617 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900 2027 2097 8 1000 60 6 3
log "rerun queue finished"
