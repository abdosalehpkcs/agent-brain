#!/usr/bin/env bash
#
# agent-brain Setup Script
# ========================
# This script sets up the agent-brain project, validates configuration,
# runs tests, and ensures the system is ready to run.
#
# Usage:
#   ./setup.sh              # Full setup
#   ./setup.sh --clean      # Clean previous setup first
#   ./setup.sh --test-only  # Run tests only
#   ./setup.sh --help       # Show help
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default values
CLEAN_SETUP=false
TEST_ONLY=false
SKIP_DOCKER=false
VERBOSE=false

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  $1${NC}"
    echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "  ${BOLD}$1${NC}"
}

confirm() {
    local prompt="$1"
    local default="${2:-n}"
    
    if [[ "$default" == "y" ]]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi
    
    read -r -p "$prompt" response
    response="${response:-$default}"
    
    [[ "$response" =~ ^[Yy]$ ]]
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# Argument Parsing
# ============================================================================

show_help() {
    cat << EOF
agent-brain Setup Script

Usage: ./setup.sh [OPTIONS]

Options:
    --clean         Clean previous setup (removes containers, volumes, venv)
    --test-only     Run tests only (skip setup steps)
    --skip-docker   Skip Docker setup (use existing database)
    --verbose       Show detailed output
    -h, --help      Show this help message

Examples:
    ./setup.sh                  # Full setup
    ./setup.sh --clean          # Clean and reinstall
    ./setup.sh --test-only      # Just run tests
    ./setup.sh --skip-docker    # Setup without Docker (external DB)

Environment Variables:
    EMBEDDING_PROVIDER          ollama, openai, or azure (default: ollama)
    EMBEDDING_MODEL             Model name (default: nomic-embed-text)
    EMBEDDING_DIMENSIONS        768, 1536, or 3072 (default: 768)
    DATABASE_URL                PostgreSQL connection string
    OLLAMA_BASE_URL             Ollama API URL (for ollama provider)
    OPENAI_API_KEY              OpenAI API key (for openai provider)
    AZURE_OPENAI_*              Azure OpenAI settings (for azure provider)

EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --clean)
                CLEAN_SETUP=true
                shift
                ;;
            --test-only)
                TEST_ONLY=true
                shift
                ;;
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# ============================================================================
# Prerequisite Checks
# ============================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    local missing=()
    
    # Python 3.10+
    print_step "Checking Python..."
    if check_command python3; then
        local py_version
        py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        local py_major py_minor
        py_major=$(echo "$py_version" | cut -d. -f1)
        py_minor=$(echo "$py_version" | cut -d. -f2)
        
        if [[ "$py_major" -ge 3 && "$py_minor" -ge 10 ]]; then
            print_success "Python $py_version found"
        else
            print_error "Python 3.10+ required (found $py_version)"
            missing+=("python3.10+")
        fi
    else
        print_error "Python3 not found"
        missing+=("python3")
    fi
    
    # Docker (unless skipped)
    if [[ "$SKIP_DOCKER" == false ]]; then
        print_step "Checking Docker..."
        if check_command docker; then
            if docker info &> /dev/null; then
                print_success "Docker is running"
            else
                print_error "Docker is installed but not running"
                missing+=("docker (start daemon)")
            fi
        else
            print_error "Docker not found"
            missing+=("docker")
        fi
        
        print_step "Checking Docker Compose..."
        if docker compose version &> /dev/null; then
            print_success "Docker Compose found"
        elif check_command docker-compose; then
            print_success "Docker Compose (standalone) found"
        else
            print_error "Docker Compose not found"
            missing+=("docker-compose")
        fi
    fi
    
    # Git (optional but useful)
    print_step "Checking Git..."
    if check_command git; then
        print_success "Git found"
    else
        print_warning "Git not found (optional)"
    fi
    
    # jq (optional for audit log inspection)
    print_step "Checking jq..."
    if check_command jq; then
        print_success "jq found"
    else
        print_warning "jq not found (optional, for audit log inspection)"
    fi
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo ""
        print_error "Missing prerequisites:"
        for item in "${missing[@]}"; do
            echo "  - $item"
        done
        echo ""
        print_info "Please install missing prerequisites and run again."
        exit 1
    fi
    
    print_success "All prerequisites satisfied"
}

# ============================================================================
# Clean Previous Setup
# ============================================================================

clean_setup() {
    print_header "Cleaning Previous Setup"
    
    if ! confirm "This will remove Docker containers, volumes, and virtualenv. Continue?"; then
        print_info "Cleanup cancelled"
        return
    fi
    
    # Stop and remove Docker containers
    print_step "Stopping Docker containers..."
    if docker compose ps -q &> /dev/null; then
        docker compose down -v 2>/dev/null || true
        print_success "Docker containers and volumes removed"
    else
        print_info "No Docker containers to remove"
    fi
    
    # Remove virtualenv
    print_step "Removing virtualenv..."
    if [[ -d ".venv" ]]; then
        rm -rf .venv
        print_success "Virtualenv removed"
    else
        print_info "No virtualenv to remove"
    fi
    
    # Remove audit logs
    print_step "Removing audit logs..."
    rm -f agent-brain-audit.jsonl
    print_success "Audit logs removed"
    
    # Remove __pycache__
    print_step "Removing Python cache..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    print_success "Python cache removed"
    
    print_success "Cleanup complete"
}

# ============================================================================
# Environment Validation
# ============================================================================

check_env_file() {
    print_header "Checking Environment Configuration"
    
    # Check if .env exists
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            print_warning ".env file not found"
            if confirm "Create .env from .env.example?"; then
                cp .env.example .env
                print_success "Created .env from .env.example"
                print_warning "Please edit .env with your settings before continuing"
                echo ""
                print_info "Required settings depend on your embedding provider:"
                echo "  - ollama:  OLLAMA_BASE_URL"
                echo "  - openai:  OPENAI_API_KEY"
                echo "  - azure:   AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, etc."
                echo ""
                exit 1
            else
                print_error "Cannot continue without .env file"
                exit 1
            fi
        else
            print_error "No .env or .env.example found"
            create_default_env
        fi
    fi
    
    print_success ".env file found"
    
    # Source the .env file
    set -a
    source .env
    set +a
    
    # Validate provider-specific settings
    validate_provider_config
}

create_default_env() {
    print_step "Creating default .env file..."
    
    cat > .env << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://agent:agentpass@localhost:5432/agent_brain

# Embedding Provider: ollama, openai, or azure
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSIONS=768

# Ollama Configuration (for EMBEDDING_PROVIDER=ollama)
OLLAMA_BASE_URL=http://localhost:11434

# OpenAI Configuration (for EMBEDDING_PROVIDER=openai)
# OPENAI_API_KEY=sk-your-key-here

# Azure OpenAI Configuration (for EMBEDDING_PROVIDER=azure)
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
# AZURE_OPENAI_API_KEY=your-key-here
# AZURE_OPENAI_API_VERSION=2024-02-01
# AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# Audit Log Directory (optional)
# AUDIT_LOG_DIR=.
EOF
    
    print_success "Created default .env file (configured for Ollama)"
    print_warning "Edit .env if you need different settings"
}

validate_provider_config() {
    print_step "Validating provider configuration..."
    
    local provider="${EMBEDDING_PROVIDER:-ollama}"
    local errors=()
    
    print_info "Embedding provider: $provider"
    
    case "$provider" in
        ollama)
            # Check OLLAMA_BASE_URL
            local ollama_url="${OLLAMA_BASE_URL:-http://localhost:11434}"
            print_info "Ollama URL: $ollama_url"
            
            # Check model
            local model="${EMBEDDING_MODEL:-nomic-embed-text}"
            print_info "Embedding model: $model"
            
            # Validate dimensions for common Ollama models
            local dims="${EMBEDDING_DIMENSIONS:-768}"
            if [[ "$dims" != "768" && "$model" == "nomic-embed-text" ]]; then
                print_warning "nomic-embed-text typically uses 768 dimensions (configured: $dims)"
            fi
            ;;
            
        openai)
            # Check OPENAI_API_KEY
            if [[ -z "${OPENAI_API_KEY:-}" ]]; then
                errors+=("OPENAI_API_KEY is required for openai provider")
            else
                # Mask the key for display
                local masked="${OPENAI_API_KEY:0:7}...${OPENAI_API_KEY: -4}"
                print_info "OpenAI API Key: $masked"
            fi
            
            # Check model
            local model="${EMBEDDING_MODEL:-text-embedding-3-small}"
            print_info "Embedding model: $model"
            
            # Validate dimensions
            local dims="${EMBEDDING_DIMENSIONS:-1536}"
            if [[ "$model" == "text-embedding-3-small" && "$dims" != "1536" ]]; then
                print_warning "text-embedding-3-small typically uses 1536 dimensions (configured: $dims)"
            fi
            ;;
            
        azure)
            # Check required Azure settings
            if [[ -z "${AZURE_OPENAI_ENDPOINT:-}" ]]; then
                errors+=("AZURE_OPENAI_ENDPOINT is required for azure provider")
            else
                print_info "Azure endpoint: $AZURE_OPENAI_ENDPOINT"
            fi
            
            if [[ -z "${AZURE_OPENAI_API_KEY:-}" ]]; then
                errors+=("AZURE_OPENAI_API_KEY is required for azure provider")
            else
                local masked="${AZURE_OPENAI_API_KEY:0:4}...${AZURE_OPENAI_API_KEY: -4}"
                print_info "Azure API Key: $masked"
            fi
            
            if [[ -z "${AZURE_OPENAI_EMBEDDING_DEPLOYMENT:-}" ]]; then
                errors+=("AZURE_OPENAI_EMBEDDING_DEPLOYMENT is required for azure provider")
            else
                print_info "Azure deployment: $AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
            fi
            
            local api_version="${AZURE_OPENAI_API_VERSION:-2024-02-01}"
            print_info "Azure API version: $api_version"
            ;;
            
        *)
            errors+=("Unknown embedding provider: $provider (expected: ollama, openai, azure)")
            ;;
    esac
    
    # Check DATABASE_URL
    if [[ -z "${DATABASE_URL:-}" ]]; then
        errors+=("DATABASE_URL is required")
    else
        print_info "Database URL: ${DATABASE_URL//:*@/:***@}"
    fi
    
    # Check dimensions
    local dims="${EMBEDDING_DIMENSIONS:-768}"
    if [[ ! "$dims" =~ ^(768|1536|3072)$ ]]; then
        errors+=("EMBEDDING_DIMENSIONS must be 768, 1536, or 3072 (got: $dims)")
    else
        print_info "Embedding dimensions: $dims"
    fi
    
    if [[ ${#errors[@]} -gt 0 ]]; then
        echo ""
        print_error "Configuration errors:"
        for err in "${errors[@]}"; do
            echo "  - $err"
        done
        echo ""
        print_info "Please fix .env and run again"
        exit 1
    fi
    
    print_success "Provider configuration valid"
}

# ============================================================================
# Python Environment Setup
# ============================================================================

setup_python_env() {
    print_header "Setting Up Python Environment"
    
    # Create virtualenv if it doesn't exist
    if [[ ! -d ".venv" ]]; then
        print_step "Creating virtualenv..."
        python3 -m venv .venv
        print_success "Virtualenv created"
    else
        print_info "Virtualenv already exists"
    fi
    
    # Activate virtualenv
    print_step "Activating virtualenv..."
    source .venv/bin/activate
    print_success "Virtualenv activated"
    
    # Upgrade pip
    print_step "Upgrading pip..."
    pip install --upgrade pip --quiet
    print_success "pip upgraded"
    
    # Install requirements
    print_step "Installing requirements..."
    pip install -r requirements.txt --quiet
    print_success "Requirements installed"
    
    # Verify imports
    print_step "Verifying module imports..."
    python -c "
from app.config import EMBEDDING_PROVIDER
from app.policy import get_policy
from app.audit import get_audit_logger
from app.mcp_server import build_server
print('All modules imported successfully')
" || {
        print_error "Module import failed"
        exit 1
    }
    print_success "All modules verified"
}

# ============================================================================
# Docker Setup
# ============================================================================

setup_docker() {
    print_header "Setting Up Docker Services"
    
    # Check if docker-compose.yml exists
    if [[ ! -f "docker-compose.yml" ]]; then
        print_error "docker-compose.yml not found"
        exit 1
    fi
    
    # Start services
    print_step "Starting Docker services..."
    docker compose up -d
    print_success "Docker services started"
    
    # Wait for PostgreSQL
    print_step "Waiting for PostgreSQL to be ready..."
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if docker compose exec -T postgres pg_isready -U agent -d agent_brain &> /dev/null; then
            print_success "PostgreSQL is ready"
            break
        fi
        
        if [[ $attempt -eq $max_attempts ]]; then
            print_error "PostgreSQL failed to start after $max_attempts attempts"
            print_info "Check logs with: docker compose logs postgres"
            exit 1
        fi
        
        echo -n "."
        sleep 1
        ((attempt++))
    done
    
    # Check Ollama if using it
    local provider="${EMBEDDING_PROVIDER:-ollama}"
    if [[ "$provider" == "ollama" ]]; then
        print_step "Waiting for Ollama to be ready..."
        local ollama_url="${OLLAMA_BASE_URL:-http://localhost:11434}"
        attempt=1
        
        while [[ $attempt -le $max_attempts ]]; do
            if curl -s "${ollama_url}/api/tags" &> /dev/null; then
                print_success "Ollama is ready"
                break
            fi
            
            if [[ $attempt -eq $max_attempts ]]; then
                print_warning "Ollama not responding at $ollama_url"
                print_info "If using external Ollama, ensure it's running"
                break
            fi
            
            echo -n "."
            sleep 1
            ((attempt++))
        done
        
        # Check if model is available
        print_step "Checking embedding model..."
        local model="${EMBEDDING_MODEL:-nomic-embed-text}"
        if curl -s "${ollama_url}/api/tags" | grep -q "\"name\":\"$model" 2>/dev/null; then
            print_success "Model '$model' is available"
        else
            print_warning "Model '$model' not found in Ollama"
            if confirm "Pull model '$model' now?"; then
                print_step "Pulling model (this may take a while)..."
                docker compose exec -T ollama ollama pull "$model" || {
                    print_warning "Could not pull model via Docker"
                    print_info "Try: ollama pull $model"
                }
            fi
        fi
    fi
}

# ============================================================================
# Database Setup
# ============================================================================

setup_database() {
    print_header "Setting Up Database"
    
    print_step "Applying database schema..."
    
    # Check if schema file exists
    if [[ ! -f "sql/schema.sql" ]]; then
        print_error "sql/schema.sql not found"
        exit 1
    fi
    
    # Apply schema
    if [[ "$SKIP_DOCKER" == true ]]; then
        # Use psql directly
        psql "$DATABASE_URL" -f sql/schema.sql -q || {
            print_error "Failed to apply schema"
            exit 1
        }
    else
        # Use Docker
        docker compose exec -T postgres psql -U agent -d agent_brain -f /dev/stdin < sql/schema.sql || {
            print_error "Failed to apply schema"
            exit 1
        }
    fi
    
    print_success "Database schema applied"
    
    # Verify connection from Python
    print_step "Verifying database connection from Python..."
    python -c "
from psycopg import connect
from app.config import DATABASE_URL
with connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM projects')
        print(f'Database connected, {cur.fetchone()[0]} projects found')
" || {
        print_error "Database connection failed from Python"
        exit 1
    }
    
    print_success "Database connection verified"
}

# ============================================================================
# Run Tests
# ============================================================================

run_tests() {
    print_header "Running Tests"
    
    # Ensure virtualenv is active
    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        source .venv/bin/activate
    fi
    
    print_step "Running pytest..."
    echo ""
    
    # Run tests
    if [[ "$VERBOSE" == true ]]; then
        pytest -v
    else
        pytest
    fi
    
    local exit_code=$?
    
    echo ""
    if [[ $exit_code -eq 0 ]]; then
        print_success "All tests passed"
    else
        print_error "Some tests failed (exit code: $exit_code)"
        print_info "Run 'pytest -v' for detailed output"
    fi
    
    return $exit_code
}

# ============================================================================
# Verify Full Setup
# ============================================================================

verify_setup() {
    print_header "Verifying Setup"
    
    local checks_passed=0
    local checks_total=0
    
    # Check database
    print_step "Checking database..."
    ((checks_total++))
    if python -c "
from psycopg import connect
from app.config import DATABASE_URL
with connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT 1')
" 2>/dev/null; then
        print_success "Database: OK"
        ((checks_passed++))
    else
        print_error "Database: FAILED"
    fi
    
    # Check embedding provider
    print_step "Checking embedding provider..."
    ((checks_total++))
    local provider="${EMBEDDING_PROVIDER:-ollama}"
    
    if [[ "$provider" == "ollama" ]]; then
        local ollama_url="${OLLAMA_BASE_URL:-http://localhost:11434}"
        if curl -s "${ollama_url}/api/tags" &> /dev/null; then
            print_success "Ollama: OK"
            ((checks_passed++))
        else
            print_error "Ollama: NOT REACHABLE"
        fi
    else
        # For cloud providers, just check config exists
        print_success "Provider ($provider): Configured"
        ((checks_passed++))
    fi
    
    # Check write policy
    print_step "Checking write policy..."
    ((checks_total++))
    if [[ -f "brain-write-policy.yml" ]]; then
        if python -c "from app.policy import load_policy; load_policy('brain-write-policy.yml')" 2>/dev/null; then
            print_success "Write policy: OK"
            ((checks_passed++))
        else
            print_error "Write policy: INVALID"
        fi
    else
        print_warning "Write policy: NOT FOUND (using defaults)"
        ((checks_passed++))
    fi
    
    # Check MCP server builds
    print_step "Checking MCP server..."
    ((checks_total++))
    if python -c "from app.mcp_server import build_server; build_server()" 2>/dev/null; then
        print_success "MCP server: OK"
        ((checks_passed++))
    else
        print_error "MCP server: FAILED TO BUILD"
    fi
    
    # Summary
    echo ""
    if [[ $checks_passed -eq $checks_total ]]; then
        print_success "All checks passed ($checks_passed/$checks_total)"
    else
        print_warning "$checks_passed/$checks_total checks passed"
    fi
}

# ============================================================================
# Print Final Instructions
# ============================================================================

print_final_instructions() {
    print_header "Setup Complete!"
    
    echo -e "${GREEN}agent-brain is ready to use.${NC}"
    echo ""
    
    echo -e "${BOLD}Quick Start:${NC}"
    echo ""
    echo "  # Activate virtualenv"
    echo "  source .venv/bin/activate"
    echo ""
    echo "  # Index a project"
    echo "  python -m app.indexer examples/project-configs/test-docs.yaml"
    echo ""
    echo "  # Search"
    echo "  python -m app.search test-docs 'Why use pgvector?'"
    echo ""
    echo "  # Run MCP server"
    echo "  python -m app.mcp_server"
    echo ""
    
    echo -e "${BOLD}Useful Commands:${NC}"
    echo ""
    echo "  pytest                    # Run tests"
    echo "  docker compose logs -f    # View Docker logs"
    echo "  docker compose down       # Stop services"
    echo "  docker compose up -d      # Start services"
    echo ""
    
    local provider="${EMBEDDING_PROVIDER:-ollama}"
    if [[ "$provider" != "ollama" ]]; then
        echo -e "${YELLOW}⚠ Privacy Notice:${NC}"
        echo "  Using $provider provider - text will be sent to external APIs"
        echo ""
    fi
}

# ============================================================================
# Main
# ============================================================================

main() {
    print_header "agent-brain Setup"
    
    echo "Working directory: $SCRIPT_DIR"
    echo ""
    
    parse_args "$@"
    
    # Clean if requested
    if [[ "$CLEAN_SETUP" == true ]]; then
        clean_setup
    fi
    
    # Test-only mode
    if [[ "$TEST_ONLY" == true ]]; then
        check_env_file
        source .venv/bin/activate 2>/dev/null || {
            print_error "Virtualenv not found. Run setup first."
            exit 1
        }
        run_tests
        exit $?
    fi
    
    # Full setup
    check_prerequisites
    check_env_file
    setup_python_env
    
    if [[ "$SKIP_DOCKER" == false ]]; then
        setup_docker
    fi
    
    setup_database
    run_tests || true  # Continue even if some tests fail
    verify_setup
    print_final_instructions
}

# Run main
main "$@"
