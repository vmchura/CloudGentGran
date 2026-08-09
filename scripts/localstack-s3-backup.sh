#!/bin/bash
# S3 Data Backup/Restore Script for LocalStack Community Edition
# Since persistence is a Pro feature, this script provides a workaround

set -e

ENDPOINT_URL="http://localhost:4566"
BACKUP_DIR="./localstack/s3-backup"
PROFILE="${AWS_PROFILE:-localstack}"

usage() {
    echo "Usage: $0 {backup|restore|list} [bucket_name]"
    echo ""
    echo "Commands:"
    echo "  backup [bucket]  - Backup S3 bucket(s) to local filesystem"
    echo "  restore [bucket] - Restore S3 bucket(s) from local filesystem"
    echo "  list             - List available backups"
    echo ""
    echo "Examples:"
    echo "  $0 backup                     # Backup all buckets"
    echo "  $0 backup catalunya-data-dev  # Backup specific bucket"
    echo "  $0 restore                    # Restore all buckets"
    echo "  $0 restore catalunya-data-dev # Restore specific bucket"
    exit 1
}

check_localstack() {
    if ! curl -s "${ENDPOINT_URL}/_localstack/health" > /dev/null 2>&1; then
        echo "Error: LocalStack is not running at ${ENDPOINT_URL}"
        exit 1
    fi
}

list_buckets() {
    aws --profile "${PROFILE}" --endpoint-url="${ENDPOINT_URL}" s3 ls | awk '{print $3}'
}

backup_bucket() {
    local bucket=$1
    local backup_path="${BACKUP_DIR}/${bucket}"
    
    echo "Backing up bucket: ${bucket}"
    mkdir -p "${backup_path}"
    
    # Sync bucket to local
    aws --profile "${PROFILE}" --endpoint-url="${ENDPOINT_URL}" s3 sync "s3://${bucket}" "${backup_path}" --delete
    echo "  ✓ Backed up to ${backup_path}"
}

restore_bucket() {
    local bucket=$1
    local backup_path="${BACKUP_DIR}/${bucket}"
    
    if [[ ! -d "${backup_path}" ]]; then
        echo "  ✗ No backup found for ${bucket}"
        return 1
    fi
    
    echo "Restoring bucket: ${bucket}"
    
    # Create bucket if it doesn't exist
    if ! aws --profile "${PROFILE}" --endpoint-url="${ENDPOINT_URL}" s3 ls "s3://${bucket}" 2>/dev/null; then
        aws --profile "${PROFILE}" --endpoint-url="${ENDPOINT_URL}" s3 mb "s3://${bucket}"
    fi
    
    # Sync local to bucket
    aws --profile "${PROFILE}" --endpoint-url="${ENDPOINT_URL}" s3 sync "${backup_path}" "s3://${bucket}" --delete
    echo "  ✓ Restored from ${backup_path}"
}

case "${1:-}" in
    backup)
        check_localstack
        mkdir -p "${BACKUP_DIR}"
        
        if [[ -n "${2:-}" ]]; then
            backup_bucket "$2"
        else
            for bucket in $(list_buckets); do
                backup_bucket "${bucket}"
            done
        fi
        echo ""
        echo "Backup complete!"
        ;;
        
    restore)
        check_localstack
        
        if [[ -n "${2:-}" ]]; then
            restore_bucket "$2"
        else
            for backup_path in "${BACKUP_DIR}"/*; do
                if [[ -d "${backup_path}" ]]; then
                    bucket=$(basename "${backup_path}")
                    restore_bucket "${bucket}"
                fi
            done
        fi
        echo ""
        echo "Restore complete!"
        ;;
        
    list)
        if [[ -d "${BACKUP_DIR}" ]]; then
            echo "Available backups in ${BACKUP_DIR}:"
            for backup_path in "${BACKUP_DIR}"/*; do
                if [[ -d "${backup_path}" ]]; then
                    bucket=$(basename "${backup_path}")
                    size=$(du -sh "${backup_path}" 2>/dev/null | cut -f1)
                    files=$(find "${backup_path}" -type f | wc -l)
                    echo "  ${bucket} (${size}, ${files} files)"
                fi
            done
        else
            echo "No backups found. Run '$0 backup' first."
        fi
        ;;
        
    *)
        usage
        ;;
esac
