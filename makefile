BACKEND_URL ?= http://127.0.0.1:8000
CHILD_ID ?= 1
DEVICE_TOKEN ?= innovaraspberrytoken
PYTHON ?= .venv/bin/python
UVICORN ?= .venv/bin/uvicorn

.PHONY: client

client:
	$(PYTHON) examples/raspberry_webrtc_client.py --backend-url $(BACKEND_URL) --child-id $(CHILD_ID) --device-token $(DEVICE_TOKEN)
