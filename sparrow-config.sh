# Configures environment for WiscAr lab

export PROJECT_DIR="$SPARROW_CONFIG_DIR"
export SPARROW_BACKUP_DIR="$PROJECT_DIR/backups"
export SPARROW_LAB_NAME="WiscAr"
export SPARROW_VERSION=">=2.0.0.beta14"

export SPARROW_SITE_CONTENT="$PROJECT_DIR/site-content"

pipeline="$PROJECT_DIR/import-pipeline"
export SPARROW_INIT_SQL="$PROJECT_DIR/init-sql"
export SPARROW_PLUGIN_DIR="$PROJECT_DIR/plugins"

export SPARROW_ENV="development"
# Keep volumes for this project separate from those for different labs
export COMPOSE_PROJECT_NAME="WiscAr"

# We have to set some environment variables for the Sparrow PyChron importer
export SPARROW_COMPOSE_OVERRIDES="$SPARROW_CONFIG_DIR/docker-compose.overrides.yaml"
export SPARROW_DOMAIN="wiscar-sparrow.geoscience.wisc.edu"
export SPARROW_DATA_DIR="$PROJECT_DIR/Data"

overrides="$SPARROW_CONFIG_DIR/sparrow-config.overrides.sh"
[ -f "$overrides" ] && source "$overrides"

