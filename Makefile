.PHONY: run tar dist clean


run:
	python -m ohmyddl -v


tar: 
	tar --exclude=".git" --exclude=".gitignore" --exclude-from=".gitignore" -cvf source.tar.gz ./


dist: clean
	python setup.py sdist bdist_wheel


upload: dist
	proxychains4 twine upload --repository-url https://test.pypi.org/legacy/ dist/*


exe: dist
	./pyinstaller/run.sh


cloc:
	cloc ./ --not-match-f=bottle.py --exclude-dir=build,dist,temp,webroot


clean:
	find . -type f -name '*.py[co]' -delete
	find . -type d -name '__pycache__' -delete
	rm -f source.tar
	rm -rf build dist *.egg-info
