#!/bin/bash

# Enhanced Dokku deployment script for Catalunya Airflow Orchestration
# Usage: ./deploy-orchestration.sh [environment] [dokku-server] [ssh_key path] [dokku_domain]
# Environments: dev, prod

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1}
DOKKU_SERVER=${2}
SSH_KEY=${3}
DOKKU_DOMAIN=${4}

# Global variables
DEPLOYMENT_BRANCH="orchestration-main"
ORIGINAL_BRANCH=""
DEPLOYMENT_TAG=""
DEPLOY_START_TIME=$(date +%s)
CLEANUP_NEEDED=false

# Environment-specific configurations
if [ "$ENVIRONMENT" = "production" ]; then
    APP_NAME="cloudgentgran-orchestration-prod"
    DB_NAME="cloudgentgran-airflow-db-prod"
    SUBDOMAIN="airflow-prod"
    AIRFLOW_ENV="prod"
elif [ "$ENVIRONMENT" = "development" ]; then
    APP_NAME="cloudgentgran-orchestration-dev"
    DB_NAME="cloudgentgran-airflow-db-dev"
    SUBDOMAIN="airflow-dev"
    AIRFLOW_ENV="dev"
else
    echo -e "${RED}❌ Invalid environment. Use 'development' or 'production'${NC}"
    exit 1
fi

echo -e "${BLUE}🚀 Deploying Catalunya Airflow Orchestration to Dokku...${NC}"
echo -e "${BLUE}=====================================================${NC}"
echo -e "Environment: ${YELLOW}$ENVIRONMENT${NC}"
echo -e "App Name: ${YELLOW}$APP_NAME${NC}"
echo -e "Database: ${YELLOW}$DB_NAME${NC}"
echo -e "Server: ${YELLOW}$DOKKU_SERVER${NC}"
echo -e "Domain: ${YELLOW}$SUBDOMAIN.$DOKKU_DOMAIN${NC}"
echo -e "Deployment Branch: ${PURPLE}$DEPLOYMENT_BRANCH${NC}"
echo -e "Deploy Time: ${CYAN}$(date)${NC}"
echo ""
# Cleanup function - called on script exit
cleanup_deployment() {
    local exit_code=$?

    if [ "$CLEANUP_NEEDED" = true ]; then
        echo -e "${YELLOW}🧹 Cleaning up deployment artifacts...${NC}"

        # Return to original branch if we changed it
        if [ -n "$ORIGINAL_BRANCH" ]; then
            echo -e "${BLUE}🔄 Returning to original branch: $ORIGINAL_BRANCH${NC}"
            git checkout "$ORIGINAL_BRANCH" 2>/dev/null || {
                echo -e "${RED}⚠️  Warning: Could not return to original branch${NC}"
            }
        fi

        # Delete deployment branch if it exists
        if git show-ref --verify --quiet "refs/heads/$DEPLOYMENT_BRANCH"; then
            echo -e "${BLUE}🗑️  Deleting deployment branch: $DEPLOYMENT_BRANCH${NC}"
            git branch -D "$DEPLOYMENT_BRANCH" 2>/dev/null || {
                echo -e "${RED}⚠️  Warning: Could not delete deployment branch${NC}"
            }
        fi

        # Clean up any temporary dbt copy in orchestration
        if [ -d "orchestration/dbt" ]; then
            echo -e "${BLUE}🗑️  Removing temporary dbt copy from orchestration${NC}"
            rm -rf orchestration/dbt
        fi
    fi

    local end_time=$(date +%s)
    local duration=$((end_time - DEPLOY_START_TIME))

    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}🎉 Deployment completed successfully in ${duration}s${NC}"
        if [ -n "$DEPLOYMENT_TAG" ]; then
            echo -e "${CYAN}📋 Deployment tagged as: $DEPLOYMENT_TAG${NC}"
        fi
    else
        echo -e "${RED}💥 Deployment failed after ${duration}s (exit code: $exit_code)${NC}"
        echo -e "${RED}🔍 Check logs above for error details${NC}"
    fi
}

# Set up cleanup trap
trap cleanup_deployment EXIT

# Function to run commands on Dokku server
run_on_dokku() {
    ssh -i $SSH_KEY $DOKKU_SERVER "$1"
}

# Function to create admin user (replaces entrypoint.sh functionality)
create_admin_user() {
    echo -e "${YELLOW}👤 Creating/updating admin user...${NC}"

    # Get admin credentials from environment
    if [ "$ENVIRONMENT" = "production" ]; then
        ADMIN_USERNAME="${AIRFLOW_USER_NAME_PROD:-admin}"
        ADMIN_PASSWORD="${AIRFLOW_USER_PASSWORD_PROD:?Set password prod}"
    else
        ADMIN_USERNAME="${AIRFLOW_USER_NAME_DEV:-admin}"
        ADMIN_PASSWORD="${AIRFLOW_USER_PASSWORD_DEV:?Set password dev}"
    fi

    # Create admin user via dokku run (replaces entrypoint.sh user creation)
    run_on_dokku "dokku run $APP_NAME bash -c '
        if ! airflow users list | awk \"{print \\\$1}\" | grep -qx \"$ADMIN_USERNAME\"; then
            echo \"Creating Airflow admin user: $ADMIN_USERNAME\"
            airflow users create \
                --username \"$ADMIN_USERNAME\" \
                --password \"$ADMIN_PASSWORD\" \
                --firstname \"Admin\" \
                --lastname \"User\" \
                --role Admin \
                --email \"admin@example.com\"
        else
            echo \"Admin user $ADMIN_USERNAME already exists\"
        fi
    '"

    echo -e "${GREEN}✅ Admin user setup completed${NC}"
}

# Step 0: Pre-flight checks
echo -e "${YELLOW}🔍 Pre-flight checks...${NC}"

# Ensure we're in the project root
if [ ! -d "orchestration" ] || [ ! -d "dbt" ]; then
    echo -e "${RED}❌ Required directories not found. Please run from project root.${NC}"
    echo -e "${RED}   Expected: orchestration/ and dbt/ directories${NC}"
    exit 1
fi

if [ ! -f "orchestration/Dockerfile" ]; then
    echo -e "${RED}❌ orchestration/Dockerfile not found${NC}"
    exit 1
fi


# Store original branch
ORIGINAL_BRANCH=$(git branch --show-current)
echo -e "${BLUE}📍 Current branch: $ORIGINAL_BRANCH${NC}"

echo -e "${GREEN}✅ Pre-flight checks passed${NC}"

echo -e "${YELLOW}🌿 Creating deployment branch strategy...${NC}"

# Delete existing deployment branch if it exists
if git show-ref --verify --quiet "refs/heads/$DEPLOYMENT_BRANCH"; then
    echo -e "${BLUE}🗑️  Deleting existing deployment branch${NC}"
    git branch -D "$DEPLOYMENT_BRANCH"
fi

# Create deployment branch from current HEAD
echo -e "${BLUE}🆕 Creating deployment branch: $DEPLOYMENT_BRANCH${NC}"
git checkout -b "$DEPLOYMENT_BRANCH"
CLEANUP_NEEDED=true

# Copy dbt directory into orchestration
echo -e "${YELLOW}📦 Integrating dbt models into deployment...${NC}"

# Remove any existing dbt copy in orchestration
if [ -d "orchestration/dbt" ]; then
    echo -e "${BLUE}🗑️  Removing old dbt integration${NC}"
    rm -rf orchestration/dbt
fi

# Copy dbt directory into orchestration
echo -e "${BLUE}📁 Copying dbt/ -> orchestration/dbt/${NC}"
cp -r dbt orchestration/

# Verify dbt copy
if [ ! -d "orchestration/dbt" ]; then
    echo -e "${RED}❌ Failed to copy dbt directory${NC}"
    exit 1
fi

echo -e "${GREEN}✅ dbt integration completed ($(du -sh orchestration/dbt | cut -f1))${NC}"

# Commit deployment artifacts
echo -e "${YELLOW}💾 Committing deployment artifacts...${NC}"
DEPLOYMENT_TAG="deployment-$(date +%Y%m%d-%H%M%S)-$ENVIRONMENT"

git add -f orchestration/dbt/

if git commit -m "🚀 Deployment artifacts for $ENVIRONMENT

- Integrated dbt models from dbt/ directory
- Environment: $ENVIRONMENT
- Timestamp: $(date)
- Original branch: $ORIGINAL_BRANCH
- Tag: $DEPLOYMENT_TAG

This is an automated deployment commit.
"; then
    echo -e "${GREEN}✅ Deployment artifacts committed${NC}"
else
    echo -e "${YELLOW}ℹ️  No changes to commit (deployment artifacts already up to date)${NC}"
fi

# Tag the deployment for rollback capability
git tag "$DEPLOYMENT_TAG"
echo -e "${CYAN}🏷️  Tagged deployment: $DEPLOYMENT_TAG${NC}"

# Step 1: Create PostgreSQL database if it doesn't exist
echo -e "${YELLOW}🗄️  Setting up PostgreSQL database...${NC}"
if ! run_on_dokku "dokku postgres:exists $DB_NAME" 2>/dev/null; then
    echo -e "${YELLOW}🆕 Creating PostgreSQL database: $DB_NAME${NC}"
    run_on_dokku "dokku postgres:create $DB_NAME"
    echo -e "${GREEN}✅ Database created successfully${NC}"
else
    echo -e "${GREEN}✅ Database $DB_NAME already exists${NC}"
fi

# Step 2: Create Dokku app if it doesn't exist
echo -e "${YELLOW}📋 Checking if Dokku app exists...${NC}"
if ! run_on_dokku "dokku apps:exists $APP_NAME" 2>/dev/null; then
    echo -e "${YELLOW}🆕 Creating Dokku app: $APP_NAME${NC}"
    run_on_dokku "dokku apps:create $APP_NAME"
    echo -e "${GREEN}✅ App created successfully${NC}"
else
    echo -e "${GREEN}✅ App $APP_NAME already exists${NC}"
fi

# Step 3: Link PostgreSQL to the app
echo -e "${YELLOW}🔗 Linking PostgreSQL database to app...${NC}"
if ! run_on_dokku "dokku postgres:linked $DB_NAME $APP_NAME" 2>/dev/null; then
    run_on_dokku "dokku postgres:link $DB_NAME $APP_NAME"
    echo -e "${GREEN}✅ Database linked to app${NC}"
else
    echo -e "${GREEN}✅ Database already linked to app${NC}"
fi

# Step 4: Get database URL for configuration
echo -e "${YELLOW}🔧 Getting database connection details...${NC}"
DB_URL=$(run_on_dokku "dokku postgres:info $DB_NAME --dsn" | tail -1)
echo -e "${GREEN}✅ Database URL retrieved${NC}"

# Step 5: Configure environment-specific settings
echo -e "${YELLOW}🔧 Configuring environment settings...${NC}"

# Configure Airflow to use PostgreSQL
POSTGRESQL_ALCHEMY=$(run_on_dokku "dokku postgres:info $DB_NAME --dsn | sed 's/postgres:/postgresql:/'")
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=$POSTGRESQL_ALCHEMY"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__SQL_ALCHEMY_CONN=$POSTGRESQL_ALCHEMY"

# Common Airflow configurations
if [ "$ENVIRONMENT" = "production" ]; then
    run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW_ADMIN_USERNAME=${AIRFLOW_USER_NAME_PROD:-admin}"
    run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW_ADMIN_PASSWORD=${AIRFLOW_USER_PASSWORD_PROD:?Set password prod}"
else
    run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW_ADMIN_USERNAME=${AIRFLOW_USER_NAME_DEV:-admin}"
    run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW_ADMIN_PASSWORD=${AIRFLOW_USER_PASSWORD_DEV:?Set password dev}"
fi

run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW_ADMIN_EMAIL=admin@example.com"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__EXECUTOR=LocalExecutor"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__AUTH_MANAGER=airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__LOAD_EXAMPLES=false"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK=true"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__API__BASE_URL=http://$SUBDOMAIN.$DOKKU_DOMAIN:8080"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__API__PORT=8080"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__HOSTNAME_CALLABLE=airflow.utils.net.get_host_ip_address"

run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW_VAR_ENVIRONMENT=$AIRFLOW_ENV"

echo -e "${GREEN}✅ Environment settings configured${NC}"

# Step 6: Add/Update Dokku git remote
echo -e "${YELLOW}🔗 Setting up git remote...${NC}"
REMOTE_NAME="dokku-cloudgentgran-$ENVIRONMENT"
if git remote | grep -q $REMOTE_NAME; then
    echo -e "${YELLOW}🔄 Updating existing Dokku remote...${NC}"
    git remote set-url $REMOTE_NAME dokku@$(echo $DOKKU_SERVER | cut -d'@' -f2):$APP_NAME
else
    echo -e "${YELLOW}➕ Adding new Dokku remote...${NC}"
    git remote add $REMOTE_NAME dokku@$(echo $DOKKU_SERVER | cut -d'@' -f2):$APP_NAME
fi
echo -e "${GREEN}✅ Dokku remote configured as '$REMOTE_NAME'${NC}"

# Step 8: Deploy to Dokku using git subtree (MONOREPO SOLUTION)
echo -e "${YELLOW}🚀 Deploying orchestration directory to Dokku...${NC}"
echo -e "${BLUE}This may take several minutes...${NC}"

# Use git subtree to push only the orchestration directory
echo -e "${YELLOW}🔄 Pushing orchestration subdirectory to Dokku...${NC}"
git subtree split --prefix=orchestration $DEPLOYMENT_BRANCH -b tmp-deploy
GIT_SSH_COMMAND="ssh -i $SSH_KEY" git push $REMOTE_NAME tmp-deploy:main --force
git branch -D tmp-deploy

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Deployment failed${NC}"
    exit 1
fi

# Step 9: Set up domain
echo -e "${YELLOW}🌐 Setting up domain...${NC}"
if ! run_on_dokku "dokku domains:report $APP_NAME | grep -q '$SUBDOMAIN.$DOKKU_DOMAIN'"; then
    run_on_dokku "dokku domains:add $APP_NAME $SUBDOMAIN.$DOKKU_DOMAIN"
    echo -e "${GREEN}✅ Domain added: $SUBDOMAIN.$DOKKU_DOMAIN${NC}"
else
    echo -e "${GREEN}✅ Domain already configured${NC}"
fi

# Step 9.1: Configure port 8080 access
echo -e "${YELLOW}🔌 Configuring port 8080 access...${NC}"
run_on_dokku "dokku ports:clear $APP_NAME"
run_on_dokku "dokku ports:add $APP_NAME http:8080:8080"
echo -e "${GREEN}✅ Port 8080 configured${NC}"

# Step 9.5: Scale processes
echo -e "${YELLOW}⚖️  Scaling Airflow processes...${NC}"
run_on_dokku "dokku ps:scale $APP_NAME web=1"
echo -e "${GREEN}✅ Processes scaled${NC}"

# Step 10: Run database initialization
echo -e "${YELLOW}🗄️  Initializing Airflow database...${NC}"
run_on_dokku "dokku run $APP_NAME airflow db migrate"
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Database migration failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Database migration completed${NC}"

# Step 11: Create admin user
create_admin_user

# Step 12: Restart the app to ensure all changes take effect
echo -e "${YELLOW}🔄 Restarting application...${NC}"
run_on_dokku "dokku ps:restart $APP_NAME"
echo -e "${GREEN}✅ Application restarted${NC}"

echo ""
echo -e "${GREEN}🎉 Deployment completed!${NC}"
echo -e "🌍 Your Airflow is available at: ${YELLOW}http://$SUBDOMAIN.$DOKKU_DOMAIN:8080${NC}"
echo ""
echo -e "🔄 To redeploy, run from project root:"
echo -e "   ${YELLOW}./scripts/deploy/deploy-orchestration.sh $ENVIRONMENT${NC}"

# After the first deployment is very important to add the fernet key:
# dokku config:set $APP_NAME AIRFLOW__CORE__FERNET_KEY=fernet_key_value
# as well the output of the script in roles-deployment.sh, which are aws credentials
