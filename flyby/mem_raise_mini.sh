#!/bin/zsh -l
# Temporary helper (2026-11-20): the queue process that started on 2026-11-09 read run_more_mini.sh with a 2 GB limit per job,
# which a long job outgrows (Ceres: exit 137 three times). The file now says 3 GB, but that running process keeps its old copy.
# This loop lifts every solmaps job it starts to 3 GB, every 2 minutes, and ends with that process.
# Start: nohup zsh -l ~/solmaps-flyby/flyby/mem_raise_mini.sh <queue pid> > /dev/null 2>&1 &
QPID=$1; LIMIT=3145728000
cd ~/solmaps-flyby
while kill -0 $QPID 2>/dev/null; do
  for c in $(docker ps --format '{{.Names}}' | grep '^solmaps-'); do
    m=$(docker inspect -f '{{.HostConfig.Memory}}' $c 2>/dev/null)
    if [ -n "$m" ] && [ "$m" -lt $LIMIT ]; then
      docker update --memory 3000m --memory-swap 6000m $c > /dev/null && echo "$(date '+%F %T') raised $c to 3 GB" >> queue.log
    fi
  done
  sleep 120
done
