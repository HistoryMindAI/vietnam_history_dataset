#!/bin/bash

# HistoryMindAI Deployment Script
# Author: Võ Đức Hiếu (h1eudayne)
# Version: 2.2.0

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="historymindai"
VERSION="2.2.0"
GITHUB_USERNAME="${GITHUB_USERNAME:-YOUR_USERNAME}"
REGISTRY="${REGISTRY:-ghcr.io}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         HistoryMindAI Deployment Script v${VERSION}         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print step
print_step() {
    echo -e "${GREEN}▶ $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}✗ Error: $1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠ Warning: $1${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Check if Docker is installed
print_step "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi
print_success "Docker is installed"

# Check if Git is installed
print_step "Checking Git installation..."
if ! command -v git &> /dev/null; then
    print_error "Git is not installed. Please install Git first."
    exit 1
fi
print_success "Git is installed"

# Run tests
print_step "Running tests..."
if python -m pytest tests/ -q; then
    print_success "All tests passed"
else
    print_warning "Some tests failed, but continuing..."
fi

# Build Docker image
print_step "Building Docker image..."
if docker build -t ${IMAGE_NAME}:latest -t ${IMAGE_NAME}:${VERSION} ./ai-service; then
    print_success "Docker image built successfully"
else
    print_error "Failed to build Docker image"
    exit 1
fi

# Test Docker image locally
print_step "Testing Docker image locally..."
CONTAINER_ID=$(docker run -d -p 8001:8000 --name ${IMAGE_NAME}-test ${IMAGE_NAME}:latest)
sleep 10  # Wait for container to start

if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    print_success "Docker image works correctly"
else
    print_error "Docker image health check failed"
    docker logs ${IMAGE_NAME}-test
    docker stop ${IMAGE_NAME}-test
    docker rm ${IMAGE_NAME}-test
    exit 1
fi

# Cleanup test container
docker stop ${IMAGE_NAME}-test
docker rm ${IMAGE_NAME}-test

# Git operations
print_step "Checking Git status..."
if [ -d .git ]; then
    print_success "Git repository found"
    
    # Check for uncommitted changes
    if [[ -n $(git status -s) ]]; then
        print_warning "You have uncommitted changes"
        read -p "Do you want to commit and push? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_step "Adding files to Git..."
            git add .
            
            read -p "Enter commit message: " commit_message
            git commit -m "${commit_message}"
            
            print_step "Pushing to GitHub..."
            git push origin main
            print_success "Code pushed to GitHub"
        fi
    else
        print_success "No uncommitted changes"
    fi
else
    print_warning "Not a Git repository. Skipping Git operations."
fi

# Push to Docker registry
read -p "Do you want to push Docker image to registry? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_step "Tagging image for registry..."
    docker tag ${IMAGE_NAME}:latest ${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:latest
    docker tag ${IMAGE_NAME}:${VERSION} ${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:${VERSION}
    
    print_step "Pushing to ${REGISTRY}..."
    if docker push ${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:latest && \
       docker push ${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:${VERSION}; then
        print_success "Docker image pushed to registry"
    else
        print_error "Failed to push Docker image"
        exit 1
    fi
fi

# Summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Deployment Summary                     ║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║${NC}  Image Name:    ${IMAGE_NAME}:${VERSION}                        ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}  Registry:      ${REGISTRY}/${GITHUB_USERNAME}                  ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}  Status:        ${GREEN}✓ Success${NC}                                ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ Deployment completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Test locally: docker run -d -p 8000:8000 ${IMAGE_NAME}:latest"
echo "  2. Access API: http://localhost:8000"
echo "  3. View docs: http://localhost:8000/docs"
echo ""
echo "To pull from registry:"
echo "  docker pull ${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:latest"
echo ""
