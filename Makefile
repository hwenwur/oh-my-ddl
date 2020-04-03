.PHONY: run tar dist clean


run:
	python -m ohmyddl -v


tar: clean
	tar --exclude=".git" --exclude=".gitignore" --exclude-from=".gitignore" -cvf source.tar.gz ./


dist: clean
	python setup.py sdist bdist_wheel


upload: dist
	proxychains4 twine upload dist/*


cloc:
	cloc ./ --not-match-f=bottle.py --exclude-dir=build,dist,temp,web


clean:
	find . -type f -name '*.py[co]' -delete
	find . -type d -name '__pycache__' -delete
	rm -f source.tar
	rm -rf build dist *.egg-info
