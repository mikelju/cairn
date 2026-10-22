IMAGE ?= cairn
PORT ?= 8000
# Lightsail runs linux/amd64; an arm64 laptop without emulation can pass PLATFORM=linux/arm64.
# On an ARM64 laptop the amd64 build needs emulation: docker run --privileged --rm tonistiigi/binfmt:qemu-v8.1.5 --install amd64
# (qemu v10 segfaults on "import duckdb").
PLATFORM ?= linux/amd64
SERVICE ?= cairn
REGION ?= eu-west-1
POWER ?= medium

.PHONY: build demo demo-offline-check deploy guidance

build:
	docker build --platform $(PLATFORM) --build-arg COMMIT=$$(git rev-parse --short HEAD 2>/dev/null || echo unknown) -t $(IMAGE) .

# Serves the app on loopback. The image holds the DuckDB file and the app makes no outbound calls,
# so it also works with the machine offline.
demo: build
	docker run --rm --platform $(PLATFORM) -p 127.0.0.1:$(PORT):8000 $(IMAGE)

# Docker cannot publish ports with --network none, so this target proves the offline claim
# from inside a container that has no network: it fetches the landing page, steps 1 and 2 and /healthz,
# then posts question Q2 to step 2 and requires a 200 whose page carries the RECORDED badge.
demo-offline-check: build
	docker run --rm --platform $(PLATFORM) --network none $(IMAGE) python -c "import urllib.request as u, socket, subprocess, sys, time; p = subprocess.Popen(['uvicorn', 'cairn.app:create_app', '--factory', '--port', '8000']); [time.sleep(1) for _ in range(120) if socket.socket().connect_ex(('127.0.0.1', 8000))]; [print(x, u.urlopen('http://127.0.0.1:8000' + x).status) for x in ('/', '/step/1', '/step/2', '/healthz')]; r = u.urlopen('http://127.0.0.1:8000/step/2/run', data=b'question=Q2'); b = r.read(); ok = r.status == 200 and b'RECORDED' in b; print('POST /step/2/run', r.status, 'RECORDED' if ok else 'missing RECORDED'); p.terminate(); sys.exit(0 if ok else 1)"

# Deploys the image to one Lightsail container service (created on first run), waits up to 5 minutes
# (30 tries, 10 s apart) for RUNNING, and prints its state and URL.
# Needs the AWS CLI with Lightsail permissions and the lightsailctl plugin on PATH.
# MSYS_NO_PATHCONV stops Git Bash from rewriting /healthz into a Windows path; exported by make so cmd runs it too.
deploy: export MSYS_NO_PATHCONV := 1
deploy: build
	aws lightsail get-container-services --service-name $(SERVICE) --region $(REGION) > /dev/null 2>&1 \
		|| aws lightsail create-container-service --service-name $(SERVICE) --power $(POWER) --scale 1 --region $(REGION)
	aws lightsail push-container-image --service-name $(SERVICE) --label app --image $(IMAGE) --region $(REGION)
	aws lightsail create-container-service-deployment --service-name $(SERVICE) --region $(REGION) \
		--containers "app={image=$$(aws lightsail get-container-images --service-name $(SERVICE) --region $(REGION) --query 'containerImages[0].image' --output text),ports={8000=HTTP}}" \
		--public-endpoint "containerName=app,containerPort=8000,healthCheck={path=/healthz}"
	uv run python -m cairn.wait_running $(SERVICE) $(REGION)
	aws lightsail get-container-services --service-name $(SERVICE) --region $(REGION) --query 'containerServices[0].[state,url]' --output text

# Laptop-only commands that call Bedrock (decision D8). Each prints its estimated spending ceiling first.
# Usage: make smoke AWS_PROFILE=<profile>; make record AWS_PROFILE=<profile> [MODEL=sonnet-4-6 QUESTIONS=Q6]
# Without MODEL the commands use DEFAULT_MODEL from src/cairn/gateway.py.
MODEL ?=
MODEL_FLAG = $(if $(MODEL),--model $(MODEL))
QUESTIONS ?= Q2 Q6
QUESTION ?= Q2

.PHONY: record live smoke

# Environment is exported by make itself (not inline VAR=value prefixes), so the recipes run the same under sh and cmd.
record live smoke: export AWS_PROFILE := $(AWS_PROFILE)
record: export CAIRN_LLM_MODE := record
live smoke: export CAIRN_LLM_MODE := live

record:
	$(if $(AWS_PROFILE),,$(error set AWS_PROFILE=<profile>))
	uv run cairn record $(QUESTIONS) $(MODEL_FLAG)

live:
	$(if $(AWS_PROFILE),,$(error set AWS_PROFILE=<profile>))
	uv run cairn ask "$(QUESTION)" --live $(MODEL_FLAG)

smoke:
	$(if $(AWS_PROFILE),,$(error set AWS_PROFILE=<profile>))
	uv run cairn smoke

# Rebuilds the generated guidance files from the pinned guideline PDFs (never edit them by hand).
guidance:
	uv run cairn guidance build
