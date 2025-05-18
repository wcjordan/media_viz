#!make

.PHONY: aider
aider:
	env $$(grep 'ANTHROPIC_API_KEY' .env | xargs) bash -c 'aider --model sonnet --api-key anthropic=$$ANTHROPIC_API_KEY'
