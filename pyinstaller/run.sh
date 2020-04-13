#!/bin/bash

set -e

DIR="$PWD/pyinstaller"
version=$(grep '__version__' ohmyddl/__init__.py | awk -F\" '{print $2}')
whl_file=$(ls dist | grep "$version" | grep "\.whl")

cp -f "dist/$whl_file" "pyinstaller/$whl_file"

docker run --rm -v $DIR:/src/ cdrx/pyinstaller-windows "./setup.sh $whl_file"
