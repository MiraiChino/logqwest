#!/bin/bash
while :; do
  for model in models/gemini-2.0-flash-001 models/gemini-2.0-flash-exp; do
    python src/generate.py --model "$model" adventure
    python src/generate.py --model "$model" log
    python src/generate.py --model "$model" location
    python src/generate.py --model "$model" area
  done
done
