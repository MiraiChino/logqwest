#!/bin/bash
while :; do
  for model in models/gemini-2.0-flash-001 models/gemini-2.0-flash-exp; do
    python generate.py --model "$model" area 1
    python generate.py --model "$model" adventures
    python generate.py --model "$model" logs
  done
done