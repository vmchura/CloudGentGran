#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_SYNC_BIN="/git-sync"
REPO_URL="https://github.com/vmchura/CloudGentGran.git"
GIT_SYNC_ROOT="/opt/airflow/git-sync"
GIT_SYNC_LINK="repo"

if [ -z "$AIRFLOW_VAR_ENVIRONMENT" ]; then
    echo "Error: AIRFLOW_VAR_ENVIRONMENT not set"
    exit 1
fi

case "$AIRFLOW_VAR_ENVIRONMENT" in
    prod|production)
        BRANCH="main"
        ;;
    dev|development|local)
        BRANCH="develop"
        ;;
    *)
        echo "error: Unknown environment '$AIRFLOW_VAR_ENVIRONMENT'"
	exit 1
        ;;
esac

echo "=========================================="
echo "git-sync Configuration"
echo "=========================================="
echo "Environment: $AIRFLOW_VAR_ENVIRONMENT"
echo "Branch:      $BRANCH"
echo "Repo URL:    $REPO_URL"
echo "Root:        $GIT_SYNC_ROOT"
echo "=========================================="

if [ ! -f "$GIT_SYNC_BIN" ]; then
    echo "Error: git-sync binary not found at $GIT_SYNC_BIN"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/sparse-checkout.txt" ]; then
    echo "Error: sparse-checkout.txt not found at $SCRIPT_DIR/sparse-checkout.txt"
    exit 1
fi

$GIT_SYNC_BIN \
    --repo="$REPO_URL" \
    --root="$GIT_SYNC_ROOT" \
    --link="$GIT_SYNC_LINK" \
    --ref="$BRANCH" \
    --one-time \
    --depth=1 \
    --sparse-checkout-file="$SCRIPT_DIR/sparse-checkout.txt" \
    --exechook-command="$SCRIPT_DIR/setup-links.sh" \
    --verbose=1

echo "=========================================="
echo "git-sync completed successfully"
echo "=========================================="
