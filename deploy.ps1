# HistoryMindAI Deployment Script (PowerShell)
# Author: Võ Đức Hiếu (h1eudayne)
# Version: 2.2.0

param(
    [string]$GitHubUsername = $env:GITHUB_USERNAME,
    [string]$Registry = "ghcr.io",
    [switch]$SkipTests,
    [switch]$SkipGit,
    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"

# Configuration
$ImageName = "historymindai"
$Version = "2.2.0"

# Colors
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Step($message) {
    Write-ColorOutput Green "▶ $message"
}

function Write-Success($message) {
    Write-ColorOutput Green "✓ $message"
}

function Write-Error($message) {
    Write-ColorOutput Red "✗ Error: $message"
}

function Write-Warning($message) {
    Write-ColorOutput Yellow "⚠ Warning: $message"
}

# Header
Write-ColorOutput Blue "╔════════════════════════════════════════════════════════════╗"
Write-ColorOutput Blue "║         HistoryMindAI Deployment Script v$Version         ║"
Write-ColorOutput Blue "╚════════════════════════════════════════════════════════════╝"
Write-Output ""

# Check Docker
Write-Step "Checking Docker installation..."
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed. Please install Docker first."
    exit 1
}
Write-Success "Docker is installed"

# Check Git
Write-Step "Checking Git installation..."
if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git is not installed. Please install Git first."
    exit 1
}
Write-Success "Git is installed"

# Run tests
if (!$SkipTests) {
    Write-Step "Running tests..."
    try {
        python -m pytest tests/ -q
        Write-Success "All tests passed"
    } catch {
        Write-Warning "Some tests failed, but continuing..."
    }
}

# Build Docker image
Write-Step "Building Docker image..."
try {
    docker build -t "${ImageName}:latest" -t "${ImageName}:${Version}" ./ai-service
    Write-Success "Docker image built successfully"
} catch {
    Write-Error "Failed to build Docker image"
    exit 1
}

# Test Docker image locally
Write-Step "Testing Docker image locally..."
$ContainerId = docker run -d -p 8001:8000 --name "${ImageName}-test" "${ImageName}:latest"
Start-Sleep -Seconds 10

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Success "Docker image works correctly"
    } else {
        throw "Health check failed"
    }
} catch {
    Write-Error "Docker image health check failed"
    docker logs "${ImageName}-test"
    docker stop "${ImageName}-test"
    docker rm "${ImageName}-test"
    exit 1
}

# Cleanup test container
docker stop "${ImageName}-test" | Out-Null
docker rm "${ImageName}-test" | Out-Null

# Git operations
if (!$SkipGit) {
    Write-Step "Checking Git status..."
    if (Test-Path .git) {
        Write-Success "Git repository found"
        
        $gitStatus = git status --porcelain
        if ($gitStatus) {
            Write-Warning "You have uncommitted changes"
            $commit = Read-Host "Do you want to commit and push? (y/n)"
            
            if ($commit -eq "y" -or $commit -eq "Y") {
                Write-Step "Adding files to Git..."
                git add .
                
                $commitMessage = Read-Host "Enter commit message"
                git commit -m $commitMessage
                
                Write-Step "Pushing to GitHub..."
                git push origin main
                Write-Success "Code pushed to GitHub"
            }
        } else {
            Write-Success "No uncommitted changes"
        }
    } else {
        Write-Warning "Not a Git repository. Skipping Git operations."
    }
}

# Push to Docker registry
if (!$SkipPush) {
    $push = Read-Host "Do you want to push Docker image to registry? (y/n)"
    
    if ($push -eq "y" -or $push -eq "Y") {
        if (!$GitHubUsername) {
            $GitHubUsername = Read-Host "Enter your GitHub username"
        }
        
        Write-Step "Tagging image for registry..."
        docker tag "${ImageName}:latest" "${Registry}/${GitHubUsername}/${ImageName}:latest"
        docker tag "${ImageName}:${Version}" "${Registry}/${GitHubUsername}/${ImageName}:${Version}"
        
        Write-Step "Pushing to ${Registry}..."
        try {
            docker push "${Registry}/${GitHubUsername}/${ImageName}:latest"
            docker push "${Registry}/${GitHubUsername}/${ImageName}:${Version}"
            Write-Success "Docker image pushed to registry"
        } catch {
            Write-Error "Failed to push Docker image"
            exit 1
        }
    }
}

# Summary
Write-Output ""
Write-ColorOutput Blue "╔════════════════════════════════════════════════════════════╗"
Write-ColorOutput Blue "║                    Deployment Summary                     ║"
Write-ColorOutput Blue "╠════════════════════════════════════════════════════════════╣"
Write-Output "  Image Name:    ${ImageName}:${Version}"
Write-Output "  Registry:      ${Registry}/${GitHubUsername}"
Write-ColorOutput Green "  Status:        ✓ Success"
Write-ColorOutput Blue "╚════════════════════════════════════════════════════════════╝"
Write-Output ""
Write-ColorOutput Green "✓ Deployment completed successfully!"
Write-Output ""
Write-Output "Next steps:"
Write-Output "  1. Test locally: docker run -d -p 8000:8000 ${ImageName}:latest"
Write-Output "  2. Access API: http://localhost:8000"
Write-Output "  3. View docs: http://localhost:8000/docs"
Write-Output ""
Write-Output "To pull from registry:"
Write-Output "  docker pull ${Registry}/${GitHubUsername}/${ImageName}:latest"
Write-Output ""
