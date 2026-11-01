# Build everything from a fresh checkout. Needs Docker, Python 3 and Node on the host; all orbital computation runs in
# the pinned container (env/Dockerfile).
#   make image   build the container
#   make data    daily transfer alternatives for 30 bodies (data/daily, about an hour on 12 cores), then the 12-site, 10-day
#                files the pages use (network/network.json, data/alternatives.npz)
#   make test    the test suite (needs make data)
#   make serve   the comparison page at http://localhost:8077/
#   make site    the public pages into docs/ (needs make data; station siting needs make stations)
#   make pairs   station-to-station edges from the committed station ranking (about 20 seconds; the 3D atlas needs them)
#   make depots  depot-orbit search for the growth map (Node, a few minutes)
#   make stations  recompute the station candidates and ranking from scratch (about 10 minutes), then the edges
IMAGE ?= solmaps-env:3
RUN = docker run --rm -v "$(CURDIR)":/work -w /work $(IMAGE)

.PHONY: all image data daily pages network-legacy alternatives test serve site stations pairs depots ephemeris
all: image data test

image:
	docker build -t $(IMAGE) env/

ephemeris:
	python3 flyby/fetch_horizons.py

data: daily pages

daily:
	$(RUN) python -m engine.daily 12

pages:
	$(RUN) python -m engine.daily pages

network-legacy:    # the earlier 30-flight-time network (0.3 to 1.8 Hohmann times); the pages no longer use it
	$(RUN) python flyby/network2.py

alternatives:
	$(RUN) python -m engine.alternatives 8

test:
	$(RUN) python -m pytest -q tests/

serve:
	docker run --rm -p 8077:8077 -v "$(CURDIR)":/work -w /work $(IMAGE) uvicorn engine.api:app --host 0.0.0.0 --port 8077

stations:
	$(RUN) python stations/precompute.py 4140 8
	$(RUN) python stations/evaluate.py
	$(RUN) python stations/pairs.py 8

pairs:
	$(RUN) python stations/pairs.py 8

depots:
	cd network && node stations.js > stations.log

site: data pairs depots
	python3 site/build_site.py
