#!make

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
	streamlit run streamlit_app.py

.PHONY: debug-start
debug-start:
	DEBUG=true streamlit run streamlit_app.py

.PHONY: test
test:
	python -m pytest preprocessing/tests -v
	python -m pytest app/tests -v
