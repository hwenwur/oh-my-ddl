run:
	python -m ohmyddl


clean:
	find . -type f -name '*.py[co]' -delete
	find . -type d -name '__pycache__' -delete
