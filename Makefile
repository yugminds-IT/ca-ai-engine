.PHONY: install download-model dev worker flower test lint

# Read model ID from settings (respects VLM_MODEL_PATH env override)
MODEL_ID := $(shell python -c "from config.settings import get_settings; print(get_settings().vlm_model_path)" 2>/dev/null || echo "HuggingFaceTB/SmolVLM-256M-Instruct")

install:
	pip install -r requirements.txt

download-model:
	@python -c "\
from huggingface_hub import snapshot_download, try_to_load_from_cache; \
path = try_to_load_from_cache('$(MODEL_ID)', 'config.json'); \
already = path is not None and str(path) != '_CACHED_NO_EXIST'; \
print('VLM model already cached, skipping download.') if already else snapshot_download('$(MODEL_ID)', ignore_patterns=['*.msgpack','flax_model*','tf_model*']) or print('VLM model download complete.')"

dev: download-model
	uvicorn api.app:app --host 0.0.0.0 --port 4000 --reload

worker:
	celery -A workers.celery_app worker --loglevel=info --queues=tds --concurrency=4

flower:
	celery -A workers.celery_app flower --port=5555

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

test:
	pytest tests/ -v

lint:
	ruff check . && ruff format --check .
