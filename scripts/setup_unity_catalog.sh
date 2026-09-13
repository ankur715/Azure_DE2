#!/usr/bin/env bash
# One-time Unity Catalog setup so Databricks serverless compute can read/write
# ADLS via a governed storage credential instead of a raw account key.
#
# Why: this pattern exists because our subscription's default 4-vCPU total
# regional compute quota made classic (VM-based) Databricks clusters
# unusable — every cluster attempt stalled or hit SkuNotAvailable regardless
# of VM size or region. Serverless compute bypasses that quota entirely, but
# serverless can't set the fs.azure.account.key spark_conf that classic
# clusters use, so storage access has to go through Unity Catalog instead.
#
# Prereqs: infra/main.bicep already deployed (creates the access connector
# and its role assignments). Run `az login` first.
#
# Usage:
#   RESOURCE_GROUP=nypa-de2-rg \
#   WORKSPACE_URL=https://<your-workspace>.azuredatabricks.net \
#   STORAGE_ACCOUNT=<your-storage-account> \
#   ACCESS_CONNECTOR_NAME=<name-prefix>-uc-connector \
#   ./scripts/setup_unity_catalog.sh

set -euo pipefail

: "${RESOURCE_GROUP:?set RESOURCE_GROUP}"
: "${WORKSPACE_URL:?set WORKSPACE_URL}"
: "${STORAGE_ACCOUNT:?set STORAGE_ACCOUNT}"
: "${ACCESS_CONNECTOR_NAME:?set ACCESS_CONNECTOR_NAME}"

CONNECTOR_ID=$(az databricks access-connector show -g "$RESOURCE_GROUP" -n "$ACCESS_CONNECTOR_NAME" --query id -o tsv)
DBX_TOKEN=$(az account get-access-token --resource 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d --query accessToken -o tsv)

# Databricks also requires the *caller* registering the credential to have
# Contributor (not just Owner-via-inheritance) on the connector resource.
MY_OID=$(az ad signed-in-user show --query id -o tsv)
az role assignment create \
  --assignee-object-id "$MY_OID" --assignee-principal-type User \
  --role "Contributor" --scope "$CONNECTOR_ID" -o none || true

echo "Creating storage credential..."
curl -s -X POST "$WORKSPACE_URL/api/2.1/unity-catalog/storage-credentials" \
  -H "Authorization: Bearer $DBX_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\": \"nypa_storage_cred\", \"azure_managed_identity\": {\"access_connector_id\": \"$CONNECTOR_ID\"}}"
echo ""

echo "Creating external locations..."
for container in bronze silver gold raw-csv; do
  safe_name=$(echo "$container" | tr '-' '_')
  curl -s -X POST "$WORKSPACE_URL/api/2.1/unity-catalog/external-locations" \
    -H "Authorization: Bearer $DBX_TOKEN" -H "Content-Type: application/json" \
    -d "{\"name\": \"ext_loc_${safe_name}\", \"url\": \"abfss://${container}@${STORAGE_ACCOUNT}.dfs.core.windows.net/\", \"credential_name\": \"nypa_storage_cred\"}"
  echo ""
done

echo "Done. If you see UC_CREDENTIAL_MI_IS_MISSING_READER_ROLE or a Contributor"
echo "permission error, the role assignments from main.bicep haven't propagated"
echo "yet — this can take anywhere from a couple minutes to (rarely) 15-20+."
echo "Just re-run this script; it's idempotent."
