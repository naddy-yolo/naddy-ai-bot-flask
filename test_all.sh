#!/bin/bash
set -e

ADMIN_TOKEN="dev-admin-token"   # .env に合わせる
USER_ID="U72a7f79cdca51f15e6536106d89c414f"
DAY="2025-08-09"
START="2025-08-01"
END="2025-08-09"
BASE="http://127.0.0.1:8888"

echo "=== /test-caromil ==="
curl -s -X POST "$BASE/test-caromil" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER_ID\",\"start_date\":\"$DAY\",\"end_date\":\"$DAY\"}" | jq .

echo "=== /test-meal-basis ==="
curl -s -X POST "$BASE/test-meal-basis" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER_ID\",\"start_date\":\"$DAY\",\"end_date\":\"$DAY\"}" | jq .

echo "=== /backfill-daily ==="
curl -s -X POST "$BASE/backfill-daily" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -d "{\"user_id\":\"$USER_ID\",\"start\":\"$START\",\"end\":\"$END\"}" | jq .

echo "=== /user/weights ==="
curl -s "$BASE/user/weights?user_id=$USER_ID&start=$START&end=$END" \
  -H "X-Admin-Token: $ADMIN_TOKEN" | jq .

echo "=== /user/intake ==="
curl -s "$BASE/user/intake?user_id=$USER_ID&start=$START&end=$END" \
  -H "X-Admin-Token: $ADMIN_TOKEN" | jq .
