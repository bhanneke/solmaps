#!/bin/zsh -l
# Second queue on the compute host (2026-11-10), same rules as run_flyby_mini.sh: position tables for all 30 bodies, the low-thrust
# atlas (resumes), an independent second run of the 34 flyby windows that came out dearer than the older searches (FLYBY_RERUN=1:
# other seeds, own files), then the flyby search for every other pair of the 30 bodies (contrib.jobs.OTHER), one origin per job.
# Needs: engine/fortran/flyby_fit.so, data/flyby_tables, flyby/horizons (copied from the release machine).
# Start: nohup zsh -l ~/solmaps-flyby/flyby/run_more_mini.sh > /dev/null 2>&1 &     Log: ~/solmaps-flyby/queue.log
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

RUNENV=""
run tables_all     python flyby/make_tables.py
run lowthrust      python -m engine.lt_atlas
RUNENV="-e FLYBY_RERUN=1"
run verify_ceres_earth_2049 python flyby/routes3.py ceres earth 2049 2049 8 1000 60 6 3
run verify_ceres_earth_2051 python flyby/routes3.py ceres earth 2051 2051 8 1000 60 6 3
run verify_ceres_earth_2083 python flyby/routes3.py ceres earth 2083 2083 8 1000 60 6 3
run verify_ceres_earth_2087 python flyby/routes3.py ceres earth 2087 2087 8 1000 60 6 3
run verify_earth_101955_2091 python flyby/routes3.py earth 101955 2091 2091 8 1000 60 6 3
run verify_earth_433_2031 python flyby/routes3.py earth 433 2031 2031 8 1000 60 6 3
run verify_earth_433_2037 python flyby/routes3.py earth 433 2037 2037 8 1000 60 6 3
run verify_earth_433_2055 python flyby/routes3.py earth 433 2055 2055 8 1000 60 6 3
run verify_earth_433_2061 python flyby/routes3.py earth 433 2061 2061 8 1000 60 6 3
run verify_earth_433_2095 python flyby/routes3.py earth 433 2095 2095 8 1000 60 6 3
run verify_earth_venus_2029 python flyby/routes3.py earth venus 2029 2029 8 1000 60 6 3
run verify_earth_venus_2037 python flyby/routes3.py earth venus 2037 2037 8 1000 60 6 3
run verify_earth_venus_2053 python flyby/routes3.py earth venus 2053 2053 8 1000 60 6 3
run verify_earth_venus_2061 python flyby/routes3.py earth venus 2061 2061 8 1000 60 6 3
run verify_earth_venus_2077 python flyby/routes3.py earth venus 2077 2077 8 1000 60 6 3
run verify_mars_earth_2083 python flyby/routes3.py mars earth 2083 2083 8 1000 60 6 3
run verify_mars_earth_2087 python flyby/routes3.py mars earth 2087 2087 8 1000 60 6 3
run verify_mars_mercury_2035 python flyby/routes3.py mars mercury 2035 2035 8 1000 60 6 3
run verify_mars_mercury_2053 python flyby/routes3.py mars mercury 2053 2053 8 1000 60 6 3
run verify_mars_mercury_2069 python flyby/routes3.py mars mercury 2069 2069 8 1000 60 6 3
run verify_mars_venus_2053 python flyby/routes3.py mars venus 2053 2053 8 1000 60 6 3
run verify_mars_venus_2059 python flyby/routes3.py mars venus 2059 2059 8 1000 60 6 3
run verify_mars_venus_2089 python flyby/routes3.py mars venus 2089 2089 8 1000 60 6 3
run verify_mars_venus_2097 python flyby/routes3.py mars venus 2097 2097 8 1000 60 6 3
run verify_psyche_earth_2041 python flyby/routes3.py psyche earth 2041 2041 8 1000 60 6 3
run verify_psyche_earth_2043 python flyby/routes3.py psyche earth 2043 2043 8 1000 60 6 3
run verify_psyche_earth_2057 python flyby/routes3.py psyche earth 2057 2057 8 1000 60 6 3
run verify_psyche_earth_2065 python flyby/routes3.py psyche earth 2065 2065 8 1000 60 6 3
run verify_psyche_earth_2075 python flyby/routes3.py psyche earth 2075 2075 8 1000 60 6 3
run verify_saturn_earth_2063 python flyby/routes3.py saturn earth 2063 2063 8 1000 60 6 3
run verify_saturn_earth_2083 python flyby/routes3.py saturn earth 2083 2083 8 1000 60 6 3
run verify_vesta_earth_2037 python flyby/routes3.py vesta earth 2037 2037 8 1000 60 6 3
run verify_vesta_earth_2047 python flyby/routes3.py vesta earth 2047 2047 8 1000 60 6 3
run verify_vesta_earth_2085 python flyby/routes3.py vesta earth 2085 2085 8 1000 60 6 3
RUNENV=""
run other_earth python flyby/routes3.py earth uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_venus python flyby/routes3.py venus earth,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_mercury python flyby/routes3.py mercury earth,venus,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_mars python flyby/routes3.py mars 433,101955,162173,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_ceres python flyby/routes3.py ceres venus,mercury,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_vesta python flyby/routes3.py vesta venus,mercury,ceres,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_psyche python flyby/routes3.py psyche venus,mercury,ceres,vesta,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_433 python flyby/routes3.py 433 earth,venus,mercury,mars,ceres,vesta,psyche,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_101955 python flyby/routes3.py 101955 earth,venus,mercury,mars,ceres,vesta,psyche,433,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_162173 python flyby/routes3.py 162173 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_jupiter python flyby/routes3.py jupiter venus,mercury,ceres,vesta,psyche,433,101955,162173,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_saturn python flyby/routes3.py saturn venus,mercury,ceres,vesta,psyche,433,101955,162173,jupiter,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_uranus python flyby/routes3.py uranus earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_neptune python flyby/routes3.py neptune earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_pluto python flyby/routes3.py pluto earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_2 python flyby/routes3.py 2 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_10 python flyby/routes3.py 10 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_24 python flyby/routes3.py 24 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_3 python flyby/routes3.py 3 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_99942 python flyby/routes3.py 99942 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,65803,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_65803 python flyby/routes3.py 65803 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,25143,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_25143 python flyby/routes3.py 25143 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,341843,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_341843 python flyby/routes3.py 341843 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,175706,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_175706 python flyby/routes3.py 175706 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,4660,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_4660 python flyby/routes3.py 4660 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,3548,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_3548 python flyby/routes3.py 3548 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,15094,11351,21900,617 2027 2097 8 1000 60 6 3
run other_15094 python flyby/routes3.py 15094 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,11351,21900,617 2027 2097 8 1000 60 6 3
run other_11351 python flyby/routes3.py 11351 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,21900,617 2027 2097 8 1000 60 6 3
run other_21900 python flyby/routes3.py 21900 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,617 2027 2097 8 1000 60 6 3
run other_617 python flyby/routes3.py 617 earth,venus,mercury,mars,ceres,vesta,psyche,433,101955,162173,jupiter,saturn,uranus,neptune,pluto,2,10,24,3,99942,65803,25143,341843,175706,4660,3548,15094,11351,21900 2027 2097 8 1000 60 6 3
log "queue finished"
