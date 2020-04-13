#!/bin/bash

set -e

# 检测是否在容器里面
if ! cat /proc/1/cgroup | grep docker >/dev/null; then
    echo 'You must run this script in a container.'
    exit 1
fi

echo "Installing $1..."

pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "$1"

pyinstaller --clean --onefile --name 'Ohmyddl' --add-data 'C:\\Python37\\lib\\site-packages\\ohmyddl\\webroot;ohmyddl\\webroot' bootstrap.py

chown -R  --reference=run.sh dist 

rm -rf build *.spec *.whl __pycache__

echo 'File output at ./pyinstaller/dist'
echo 'Done'
