#!make

.PHONY: aider
aider:
	env $$(grep 'ANTHROPIC_API_KEY' .env | xargs) bash -c 'aider --model sonnet --api-key anthropic=$$ANTHROPIC_API_KEY'

.PHONY: init
init:
	bash setup.sh

.PHONY: lint
lint:
	black --check .
	flake8 .
	pylint -j 0 .

.PHONY: format
format:
	black .

.PHONY: test
test:
	python -m pytest tests -v
