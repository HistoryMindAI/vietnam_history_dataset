#!/bin/bash

# Push to GitHub Script
# Quick script to commit and push changes

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              Push to GitHub - HistoryMindAI                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if git repo
if [ ! -d .git ]; then
    echo -e "${YELLOW}Not a git repository. Initializing...${NC}"
    git init
    echo -e "${GREEN}✓ Git repository initialized${NC}"
fi

# Check for remote
if ! git remote | grep -q origin; then
    echo -e "${YELLOW}No remote 'origin' found.${NC}"
    read -p "Enter GitHub repository URL: " repo_url
    git remote add origin "$repo_url"
    echo -e "${GREEN}✓ Remote 'origin' added${NC}"
fi

# Show status
echo -e "${BLUE}Current status:${NC}"
git status --short

# Add all files
echo ""
read -p "Add all files? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git add .
    echo -e "${GREEN}✓ Files added${NC}"
fi

# Commit
echo ""
read -p "Enter commit message: " commit_msg
if [ -z "$commit_msg" ]; then
    commit_msg="Update: $(date '+%Y-%m-%d %H:%M:%S')"
fi

git commit -m "$commit_msg"
echo -e "${GREEN}✓ Changes committed${NC}"

# Push
echo ""
echo -e "${BLUE}Pushing to GitHub...${NC}"
git push -u origin main

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ✓ Successfully Pushed!                    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Your code is now on GitHub! 🎉"
echo ""
