#!/usr/bin/env bash
while true
do
  echo "Starting smittestopp survey..."
  python3 -m survey.storage
  if [ "$?" -ne "8" ]; then
    break
  fi
  service bluetooth restart
done
