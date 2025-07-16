#!/bin/bash
# Watch Tower Management Script
# This script provides convenient commands for managing the Watch Tower Docker infrastructure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to check if docker-compose is available
check_docker_compose() {
    if ! command -v docker > /dev/null 2>&1; then
        print_error "Docker is not installed. Please install Docker and try again."
        exit 1
    fi
    if ! docker compose version > /dev/null 2>&1; then
        print_error "docker compose (v2) is not available. Please install Docker Compose v2 and try again."
        exit 1
    fi
}

# Function to show help
show_help() {
    print_header "Watch Tower Management Script"
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Docker Infrastructure Commands:"
    echo "  start-container      Start the Watch Tower application (container)"
    echo "  stop-container       Stop the Watch Tower application (container)"
    echo "  restart-container    Restart the entire container"
    echo "  build               Build the Docker container"
    echo "  logs                Show application logs"
    echo "  shell               Open a shell inside the container"
    echo "  help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start-container"
    echo "  $0 logs"
    echo "  $0 shell"
    echo ""
    echo "Note: For application-level operations (business logic loop, status, config),
use the main CLI: docker compose exec watch-tower watch-tower --help"
}

# Function to start the application
start_container() {
    print_header "Starting Watch Tower"
    check_docker
    check_docker_compose
    
    print_status "Starting container..."
    docker compose up -d
    
    print_status "Container started successfully!"
    echo ""
    print_status "To check application status, run:"
    echo "  docker compose exec watch-tower watch-tower status"
}

# Function to stop the application
stop_container() {
    print_header "Stopping Watch Tower"
    check_docker
    check_docker_compose
    
    print_status "Stopping container..."
    docker compose down
    
    print_status "Container stopped successfully!"
}

# Function to restart the application
restart_container() {
    print_header "Restarting Watch Tower"
    check_docker
    check_docker_compose
    
    print_status "Restarting container..."
    docker compose restart watch-tower
    
    print_status "Container restarted successfully!"
}

# Function to build the container
build_container() {
    print_header "Building Watch Tower"
    check_docker
    check_docker_compose
    
    print_status "Building container..."
    docker compose build
    
    print_status "Container built successfully!"
}

# Function to show logs
show_logs() {
    print_header "Watch Tower Logs"
    check_docker
    check_docker_compose
    
    print_status "Showing logs (press Ctrl+C to exit)..."
    docker compose logs -f watch-tower
}

# Function to open shell in container
open_shell() {
    print_header "Opening Shell in Watch Tower Container"
    check_docker
    check_docker_compose
    
    print_status "Opening shell in container..."
    docker compose exec watch-tower /bin/bash
}

# Main script logic
case "${1:-help}" in
    start-container)
        start_container
        ;;
    stop-container)
        stop_container
        ;;
    restart-container)
        restart_container
        ;;
    build)
        build_container
        ;;
    logs)
        show_logs
        ;;
    shell)
        open_shell
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac