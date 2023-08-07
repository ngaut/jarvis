#!/bin/bash

work_dir=./workspace

for file in ${work_dir}/*.yaml
do
    idx=$(basename "$file" .yaml)
    if [[ $idx =~ ^[0-9]+$ ]]
    then
        python -m jarvis --continuous --timeout=3 --config=./config.yaml --startseq=0 --verbose --yaml="${idx}.yaml"
    fi
done
