#!/bin/sh

VENV=./venv

if [ ! -d ${VENV} ]; then
    mkdir venv
    python3 -m venv ${VENV}
fi
source ${VENV}/bin/activate
python3 -m pip install .
