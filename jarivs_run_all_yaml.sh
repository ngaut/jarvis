#!/bin/bash

yaml_dir=./workspace

for file in ${yaml_dir}/*.yaml
do
    idx=$(basename "$file" .yaml)
    if [[ $idx =~ ^[0-9]+$ ]]
    then
        python main.py --continuous --timeout=3 --config=./config.yaml --startseq=0 --verbose --yaml="${idx}.yaml"
    fi
done
