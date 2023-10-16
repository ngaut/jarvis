#!/bin/bash

if [ "$#" -eq 1 ]; then
    work_dir=$1
else
    work_dir=./workspace
fi

for file in ${work_dir}/*.yaml
do
    idx=$(basename "$file" .yaml)
    if [[ $idx =~ ^[0-9]+$ ]]
    then
        python -m jarvis --workspace=${work_dir} --yaml="${idx}.yaml"
    fi
done
