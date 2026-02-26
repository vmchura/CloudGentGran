#!/bin/bash

set -e

REPO_DIR="/opt/airflow/git-sync/repo"
AIRFLOW_DAGS="/opt/airflow/dags"
AIRFLOW_PLUGINS="/opt/airflow/plugins"
AIRFLOW_CONFIG="/opt/airflow/config"
AIRFLOW_DBT="/opt/airflow/dbt"

echo "=========================================="
echo "Setting up symlinks from git-sync"
echo "=========================================="
echo "Repo directory: $REPO_DIR"
echo "Synced hash:    $GITSYNC_HASH"
echo "=========================================="

if [ ! -d "$REPO_DIR" ]; then
    echo "Error: Repo directory not found at $REPO_DIR"
    exit 1
fi

setup_link() {
    local src="$1"
    local dest="$2"
    local name="$3"
    
    if [ -d "$src" ]; then
        if [ -L "$dest" ]; then
            echo "Removing existing symlink: $dest"
            rm -f "$dest"
        elif [ -d "$dest" ]; then
            echo "Removing existing directory: $dest"
            rm -rf "$dest"
        fi
        
        echo "Creating symlink: $dest -> $src"
        ln -s "$src" "$dest"
        echo "✓ $name linked successfully"
    else
        echo "⚠ Source directory not found for $name: $src"
    fi
}

setup_link "$REPO_DIR/dbt" "$AIRFLOW_DBT" "dbt"
setup_link "$REPO_DIR/orchestration/dags" "$AIRFLOW_DAGS" "dags"
setup_link "$REPO_DIR/orchestration/plugins" "$AIRFLOW_PLUGINS" "plugins"
setup_link "$REPO_DIR/orchestration/config" "$AIRFLOW_CONFIG" "config"

if [ -f "$AIRFLOW_DBT/mart/profiles_template.yml" ]; then
    if [ ! -f "$AIRFLOW_DBT/profiles.yml" ]; then
        echo "Copying profiles_template.yml to profiles.yml"
        cp "$AIRFLOW_DBT/mart/profiles_template.yml" "$AIRFLOW_DBT/profiles.yml"
    fi
fi

if [ -f "$AIRFLOW_DBT/mart/packages.yml" ]; then
    echo "Running dbt deps..."
    cd "$AIRFLOW_DBT/mart" && dbt deps
    echo "✓ dbt deps completed"
fi

echo "=========================================="
echo "Symlinks setup completed"
echo "=========================================="
