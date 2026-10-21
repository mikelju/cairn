IMAGE ?= cairn
PORT ?= 8000
# Lightsail runs linux/amd64; an arm64 laptop without emulation can pass PLATFORM=linux/arm64.
PLATFORM ?= linux/amd64

.PHONY: build demo demo-offline-check

build:
	docker build --platform $(PLATFORM) -t $(IMAGE) .

# Serves the app on loopback. The image holds the DuckDB file and the app makes no outbound calls,
# so it also works with the machine offline.
demo: build
	docker run --rm --platform $(PLATFORM) -p 127.0.0.1:$(PORT):8000 $(IMAGE)

# Docker cannot publish ports with --network none, so this target proves the offline claim
# by fetching the landing page and step 1 from inside a container that has no network.
demo-offline-check: build
	docker run --rm --platform $(PLATFORM) --network none $(IMAGE) python -c "import urllib.request as u, subprocess, time; p = subprocess.Popen(['uvicorn', 'cairn.app:create_app', '--factory', '--port', '8000']); time.sleep(5); [print(x, u.urlopen('http://127.0.0.1:8000' + x).status) for x in ('/', '/step/1', '/healthz')]; p.terminate()"
