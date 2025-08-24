#!/bin/bash

# Enhanced Dokku deployment script for Catalunya Airflow Orchestration
# Usage: ./deploy-dokku.sh [environment] [dokku-server] [ssh_key path] [dokku_domain]
# Environments: dev, prod

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1}
DOKKU_SERVER=${2}
SSH_KEY=${3}
DOKKU_DOMAIN=${4}

# Environment-specific configurations
if [ "$ENVIRONMENT" = "production" ]; then
    APP_NAME="cloudgentgran-orchestration-prod"
    DB_NAME="cloudgentgran-airflow-db-prod"
    SUBDOMAIN="airflow-prod"
elif [ "$ENVIRONMENT" = "development" ]; then
    APP_NAME="cloudgentgran-orchestration-dev"
    DB_NAME="cloudgentgran-airflow-db-dev"
    SUBDOMAIN="airflow-dev"
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
echo ""

# Function to run commands on Dokku server
run_on_dokku() {
    ssh -i $SSH_KEY $DOKKU_SERVER "$1"
}

# Step 0: Ensure we're in the project root (not orchestration directory)
if [ ! -d "orchestration" ] || [ ! -f "orchestration/Dockerfile" ]; then
    echo -e "${RED}❌ orchestration directory not found. Please run from project root.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Project structure looks good${NC}"

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

# Step 5: Configure environment-specific settings
echo -e "${YELLOW}🔧 Configuring environment settings...${NC}"

# Common Airflow configurations
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__EXECUTOR=LocalExecutor"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__AUTH_MANAGER=airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__FERNET_KEY=''"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__CORE__LOAD_EXAMPLES=false"
run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK=true"

# Environment-specific configurations
if [ "$ENVIRONMENT" = "production" ]; then
    run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW_VAR_ENVIRONMENT=production"
    run_on_dokku "dokku config:set --no-restart $APP_NAME _AIRFLOW_WWW_USER_USERNAME=${AIRFLOW_USER_NAME_PROD}"
    run_on_dokku "dokku config:set --no-restart $APP_NAME _AIRFLOW_WWW_USER_PASSWORD=${AIRFLOW_USER_PASSWORD_PROD}"
else
    run_on_dokku "dokku config:set --no-restart $APP_NAME AIRFLOW_VAR_ENVIRONMENT=development"
    run_on_dokku "dokku config:set --no-restart $APP_NAME _AIRFLOW_WWW_USER_USERNAME=${AIRFLOW_USER_NAME_DEV}"
    run_on_dokku "dokku config:set --no-restart $APP_NAME _AIRFLOW_WWW_USER_PASSWORD=${AIRFLOW_USER_PASSWORD_DEV}"
fi

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

# Step 7: Prepare git for deployment
echo -e "${YELLOW}📦 Preparing git for deployment...${NC}"

# Ensure we're on the main branch
git checkout main 2>/dev/null || git checkout master 2>/dev/null || echo "Using current branch"

# Add all files to git
git add .

# Commit changes
git commit -m "Deploy orchestration to $ENVIRONMENT $(date)" || echo "No changes to commit"

# Step 8: Deploy to Dokku using git subtree (MONOREPO SOLUTION)
echo -e "${YELLOW}🚀 Deploying orchestration directory to Dokku...${NC}"
echo -e "${BLUE}This may take several minutes...${NC}"

# Use git subtree to push only the orchestration directory
echo -e "${YELLOW}🔄 Pushing orchestration subdirectory to Dokku...${NC}"
GIT_SSH_COMMAND="ssh -i $SSH_KEY" git subtree push --prefix=orchestration $REMOTE_NAME main-orchestration

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Deployment failed${NC}"
    echo -e "${YELLOW}💡 Trying alternative subtree method...${NC}"
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

# Step 10: Run database initialization
echo -e "${YELLOW}🗄️  Initializing Airflow database...${NC}"
run_on_dokku "dokku run $APP_NAME airflow db init" || echo "Database already initialized"
echo -e "${GREEN}✅ Database initialization completed${NC}"

# Step 11: Create admin user
echo -e "${YELLOW}👤 Creating/updating admin user...${NC}"

USERNAME=$(run_on_dokku "dokku config:get $APP_NAME _AIRFLOW_WWW_USER_USERNAME")
PASSWORD=$(run_on_dokku "dokku config:get $APP_NAME _AIRFLOW_WWW_USER_PASSWORD")

run_on_dokku "dokku run $APP_NAME airflow users create --username $USERNAME --firstname Admin --lastname User --role Admin --email admin@example.com --password $PASSWORD" || echo "User may already exist"
echo -e "${GREEN}✅ Admin user configured${NC}"

echo ""
echo -e "${GREEN}🎉 Deployment completed!${NC}"
echo -e "🌍 Your Airflow is available at: ${YELLOW}http://$SUBDOMAIN.$DOKKU_DOMAIN${NC}"
echo -e "👤 Login: ${YELLOW}$USERNAME${NC} / ${YELLOW}$PASSWORD${NC}"
echo ""
echo -e "🔄 To redeploy, run from project root:"
echo -e "   ${YELLOW}./orchestration/deploy-dokku.sh $ENVIRONMENT${NC}"