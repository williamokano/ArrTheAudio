.PHONY: help build build-test test test-unit test-integration test-coverage clean run daemon

help:
	@echo "ArrTheAudio - Available commands:"
	@echo ""
	@echo "  make build          - Build production Docker image"
	@echo "  make build-test     - Build test Docker image with test dependencies"
	@echo "  make test           - Run all tests in Docker"
	@echo "  make test-unit      - Run only unit tests"
	@echo "  make test-integration - Run only integration tests"
	@echo "  make test-coverage  - Run tests with coverage report"
	@echo "  make daemon         - Start daemon with docker-compose"
	@echo "  make clean          - Stop daemon and clean up"
	@echo ""

build:
	docker build -t arrtheaudio:latest .

build-test:
	docker build -f Dockerfile.test -t arrtheaudio:test .

test: build-test
	docker run --rm \
		-v $(PWD)/tests:/app/tests \
		-v $(PWD)/src:/app/src \
		arrtheaudio:test \
		pytest tests/ -v

test-unit: build-test
	docker run --rm \
		-v $(PWD)/tests:/app/tests \
		-v $(PWD)/src:/app/src \
		arrtheaudio:test \
		pytest tests/unit/ -v

test-integration: build-test
	docker run --rm \
		-v $(PWD)/tests:/app/tests \
		-v $(PWD)/src:/app/src \
		arrtheaudio:test \
		pytest tests/integration/ -v

test-coverage: build-test
	docker run --rm \
		-v $(PWD)/tests:/app/tests \
		-v $(PWD)/src:/app/src \
		arrtheaudio:test \
		pytest tests/ -v --cov=arrtheaudio --cov-report=term-missing --cov-report=html

daemon: build
	docker-compose up -d
	@echo ""
	@echo "Daemon started! Check status with: docker-compose logs -f"
	@echo "Health check: curl http://localhost:9393/health"

clean:
	docker-compose down
	docker rmi arrtheaudio:latest arrtheaudio:test 2>/dev/null || true
	rm -rf htmlcov/ .coverage .pytest_cache/
