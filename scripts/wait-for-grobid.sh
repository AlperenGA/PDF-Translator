#!/usr/bin/env bash
set -e

HOST="localhost"
PORT="8070"
URL="http://${HOST}:${PORT}/api/isalive"
RETRIES=30
SLEEP=2

echo "Waiting for GROBID at ${URL} ..."
count=0
until curl -sSf "${URL}" >/dev/null 2>&1 || [ $count -ge $RETRIES ]; do
  count=$((count + 1))
  echo "  -> try $count/$RETRIES..."
  sleep $SLEEP
done

if curl -sSf "${URL}" >/dev/null 2>&1; then
  echo "GROBID is up!"
  curl -s "${URL}"
  echo
  exit 0
else
  echo "GROBID did not start within $((RETRIES * SLEEP)) seconds."
  exit 1
fi
