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

.PHONY: preprocess
preprocess:
	env $$(grep -v 'ANTHROPIC' .env | xargs) python -m preprocessing.preprocess

.PHONY: start
start:
	streamlit run app/streamlit_app.py

.PHONY: test
test:
	python -m pytest tests -v
	python -m pytest app/tests -v
