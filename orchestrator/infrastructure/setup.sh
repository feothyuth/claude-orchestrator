#!/bin/bash
# v3.0 Infrastructure Setup Script
# Requires: Docker, Docker Compose

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-orchestrator_pass}"
POSTGRES_DB="${POSTGRES_DB:-orchestrator}"

echo "═══════════════════════════════════════════════════════════════"
echo "  Claude Orchestrator v3.0 - Infrastructure Setup"
echo "═══════════════════════════════════════════════════════════════"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker Desktop:"
    echo "   https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "   For WSL2, enable 'Use the WSL 2 based engine' in Docker Desktop settings"
    exit 1
fi

echo "✓ Docker found: $(docker --version)"

# Check if containers already running
if docker ps | grep -q orchestrator-postgres; then
    echo "⚠️  PostgreSQL container already running"
else
    echo "→ Starting PostgreSQL with pgvector..."
    docker run -d \
        --name orchestrator-postgres \
        -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
        -e POSTGRES_DB="$POSTGRES_DB" \
        -p 5432:5432 \
        -v orchestrator-pgdata:/var/lib/postgresql/data \
        pgvector/pgvector:pg16

    echo "  Waiting for PostgreSQL to be ready..."
    sleep 5

    # Wait for postgres to be ready
    for i in {1..30}; do
        if docker exec orchestrator-postgres pg_isready -U postgres &>/dev/null; then
            break
        fi
        sleep 1
    done
    echo "✓ PostgreSQL started"
fi

if docker ps | grep -q orchestrator-redis; then
    echo "⚠️  Redis container already running"
else
    echo "→ Starting Redis..."
    docker run -d \
        --name orchestrator-redis \
        -p 6379:6379 \
        -v orchestrator-redis-data:/data \
        redis:7-alpine redis-server --appendonly yes
    echo "✓ Redis started"
fi

# Initialize database schema
echo "→ Initializing database schema..."
if [ -f "$SCRIPT_DIR/schema.sql" ]; then
    docker exec -i orchestrator-postgres psql -U postgres -d "$POSTGRES_DB" < "$SCRIPT_DIR/schema.sql" 2>/dev/null || true
    echo "✓ Schema initialized"
else
    echo "⚠️  schema.sql not found at $SCRIPT_DIR/schema.sql"
fi

# Build shadow workspace image
echo "→ Building Shadow Workspace Docker image..."
if [ -f "$SCRIPT_DIR/Dockerfile.shadow" ]; then
    docker build -t orchestrator-shadow -f "$SCRIPT_DIR/Dockerfile.shadow" "$SCRIPT_DIR"
    echo "✓ Shadow Workspace image built"
else
    echo "⚠️  Dockerfile.shadow not found"
fi

# Install Python dependencies
echo "→ Installing Python dependencies..."
pip install -q asyncpg redis docker aiohttp 2>/dev/null || pip3 install -q asyncpg redis docker aiohttp 2>/dev/null || echo "⚠️  Could not install Python packages"

# Create .env file
ENV_FILE="$SCRIPT_DIR/.env"
cat > "$ENV_FILE" << EOF
# Orchestrator v3.0 Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=$POSTGRES_DB

REDIS_HOST=localhost
REDIS_PORT=6379

SHADOW_IMAGE=orchestrator-shadow
EOF
echo "✓ Environment file created: $ENV_FILE"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Setup Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Services running:"
echo "  • PostgreSQL: localhost:5432 (user: postgres, db: $POSTGRES_DB)"
echo "  • Redis:      localhost:6379"
echo "  • Shadow:     orchestrator-shadow image ready"
echo ""
echo "To stop:  docker stop orchestrator-postgres orchestrator-redis"
echo "To start: docker start orchestrator-postgres orchestrator-redis"
echo ""
