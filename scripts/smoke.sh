#!/usr/bin/env bash
# G016. Usage: scripts/smoke.sh <api> <web>
set -euo pipefail

API="${1:?api base url}"
WEB="${2:?web base url}"

health="$(curl -fsS "$API/api/health")"
printf '%s' "$health" | grep -Eq '"falkordb": ?"up"'

curl -fsS "$API/api/releases" >/dev/null

release="$(curl -fsS "$API/api/releases" | python3 -c 'import json,sys; rows=json.load(sys.stdin); print(rows[-1]["release"] if rows else "")')"
if [[ -z "$release" ]]; then
  echo "no releases loaded" >&2
  exit 1
fi

submitter="$(curl -fsS "$API/api/releases/$release/submitters?limit=1" | python3 -c 'import json,sys; rows=json.load(sys.stdin); print(rows[0]["submitter_id"] if rows else "")')"
if [[ -z "$submitter" ]]; then
  echo "no submitter with changes in $release" >&2
  exit 1
fi
curl -fsS "$API/api/releases/$release/submitters/$submitter/changes" >/dev/null

curl -fsS "$API/api/variants/51579" >/dev/null

change_id="$(curl -fsS "$API/api/releases/$release/submitters/$submitter/changes" | python3 -c 'import json,sys; body=json.load(sys.stdin); changes=body["changes"]; ups=[c for c in changes if c["kind"]=="UP_TO_ACTIONABLE"]; print((ups or changes)[0]["change_id"] if changes else "")')"
if [[ -z "$change_id" ]]; then
  echo "no class change to map" >&2
  exit 1
fi
curl -fsS -X POST "$API/api/duty-map" \
  -H 'content-type: application/json' \
  -d "{\"change_id\":\"$change_id\",\"tenant\":\"demo\",\"dry_run\":true}" >/dev/null

curl -fsS -X POST "$API/mcp" \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | grep -q 'variant_status'

curl -fsS "$WEB" >/dev/null
echo "smoke ok"
