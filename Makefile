#!make

.PHONY: aider
aider:
	env $$(grep 'ANTHROPIC_API_KEY' .env | xargs) bash -c 'aider --model sonnet --api-key anthropic=$$ANTHROPIC_API_KEY'

.PHONY: init
init:
	bash setup.sh

.PHONY: test
test:
	pytest tests/test_setup.py -v
