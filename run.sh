#!/bin/bash

# Default models
GENERATE_MODEL="gemini/models/gemini-2.5-pro"
CHECK_MODEL="gemini/gemini-2.5-flash-lite"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --generate-model)
      GENERATE_MODEL="$2"
      shift 2
      ;;
    --check-model)
      CHECK_MODEL="$2"
      shift 2
      ;;
    --check-only)
      CHECK_ONLY=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

while :; do
  for model in $GENERATE_MODEL; do
    if [ "$CHECK_ONLY" = true ]; then
      # Only check existing content
      python src/generate.py --check-model "$CHECK_MODEL" --check-only adventure
      python src/generate.py --check-model "$CHECK_MODEL" --check-only log
      python src/generate.py --check-model "$CHECK_MODEL" --check-only location
      python src/generate.py --check-model "$CHECK_MODEL" --check-only area
      python src/generate.py --check-model "$CHECK_MODEL" --check-only locked_adventure
      python src/generate.py --check-model "$CHECK_MODEL" --check-only locked_log
      python src/generate.py --check-model "$CHECK_MODEL" --check-only locked_area
    else
      # Generate with separate check model (auto-regenerate if check fails)
      python src/generate.py --model "$model" --check-model "$CHECK_MODEL" adventure
      python src/generate.py --model "$model" --check-model "$CHECK_MODEL" log
      python src/generate.py --model "$model" --check-model "$CHECK_MODEL" location
      python src/generate.py --model "$model" --check-model "$CHECK_MODEL" area
      python src/generate.py --model "$model" --check-model "$CHECK_MODEL" locked_adventure
      python src/generate.py --model "$model" --check-model "$CHECK_MODEL" locked_log
      python src/generate.py --model "$model" --check-model "$CHECK_MODEL" locked_area
    fi
  done
done
