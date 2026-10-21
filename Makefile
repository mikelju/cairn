IMAGE ?= cairn
PORT ?= 8000
# Lightsail runs linux/amd64; an arm64 laptop without emulation can pass PLATFORM=linux/arm64.
# On an ARM64 laptop the amd64 build needs emulation: docker run --privileged --rm tonistiigi/binfmt:qemu-v8.1.5 --install amd64
# (qemu v10 segfaults on "import duckdb").
PLATFORM ?= linux/amd64
SERVICE ?= cairn
REGION ?= eu-west-1
POWER ?= medium

.PHONY: build demo demo-offline-check deploy

build:
	docker build --platform $(PLATFORM) --build-arg COMMIT=$$(git rev-parse --short HEAD 2>/dev/null || echo unknown) -t $(IMAGE) .

# Serves the app on loopback. The image holds the DuckDB file and the app makes no outbound calls,
# so it also works with the machine offline.
demo: build
	docker run --rm --platform $(PLATFORM) -p 127.0.0.1:$(PORT):8000 $(IMAGE)

# Docker cannot publish ports with --network none, so this target proves the offline claim
# by fetching the landing page and step 1 from inside a container that has no network.
demo-offline-check: build
	docker run --rm --platform $(PLATFORM) --network none $(IMAGE) python -c "import urllib.request as u, subprocess, time; p = subprocess.Popen(['uvicorn', 'cairn.app:create_app', '--factory', '--port', '8000']); time.sleep(5); [print(x, u.urlopen('http://127.0.0.1:8000' + x).status) for x in ('/', '/step/1', '/healthz')]; p.terminate()"

# Deploys the image to one Lightsail container service (created on first run) and prints its state and URL.
# Needs the AWS CLI with Lightsail permissions and the lightsailctl plugin on PATH.
deploy: build
	aws lightsail get-container-services --service-name $(SERVICE) --region $(REGION) > /dev/null 2>&1 \
		|| aws lightsail create-container-service --service-name $(SERVICE) --power $(POWER) --scale 1 --region $(REGION)
	aws lightsail push-container-image --service-name $(SERVICE) --label app --image $(IMAGE) --region $(REGION)
	# MSYS_NO_PATHCONV stops Git Bash from rewriting /healthz into a Windows path.
	MSYS_NO_PATHCONV=1 aws lightsail create-container-service-deployment --service-name $(SERVICE) --region $(REGION) \
		--containers "app={image=$$(aws lightsail get-container-images --service-name $(SERVICE) --region $(REGION) --query 'containerImages[0].image' --output text),ports={8000=HTTP}}" \
		--public-endpoint "containerName=app,containerPort=8000,healthCheck={path=/healthz}"
	aws lightsail get-container-services --service-name $(SERVICE) --region $(REGION) --query 'containerServices[0].[state,url]' --output text
