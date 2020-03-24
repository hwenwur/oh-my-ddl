run:
	python -m ohmyddl


tar:
	tar --exclude=".git" --exclude=".gitignore" --exclude-from=".gitignore" -cvf source.tar ./


clean:
	find . -type f -name '*.py[co]' -delete
	find . -type d -name '__pycache__' -delete
	rm -f source.tar
	rm -rf build dist *.egg-info
