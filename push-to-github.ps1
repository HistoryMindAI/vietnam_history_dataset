# Push to GitHub Script (PowerShell)
# Quick script to commit and push changes

$ErrorActionPreference = "Stop"

function Write-ColorOutput($ForegroundColor, $message) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    Write-Output $message
    $host.UI.RawUI.ForegroundColor = $fc
}

Write-ColorOutput Blue "╔════════════════════════════════════════════════════════════╗"
Write-ColorOutput Blue "║              Push to GitHub - HistoryMindAI                ║"
Write-ColorOutput Blue "╚════════════════════════════════════════════════════════════╝"
Write-Output ""

# Check if git repo
if (!(Test-Path .git)) {
    Write-ColorOutput Yellow "Not a git repository. Initializing..."
    git init
    Write-ColorOutput Green "✓ Git repository initialized"
}

# Check for remote
$remotes = git remote
if ($remotes -notcontains "origin") {
    Write-ColorOutput Yellow "No remote 'origin' found."
    $repoUrl = Read-Host "Enter GitHub repository URL"
    git remote add origin $repoUrl
    Write-ColorOutput Green "✓ Remote 'origin' added"
}

# Show status
Write-ColorOutput Blue "Current status:"
git status --short

# Add all files
Write-Output ""
$addFiles = Read-Host "Add all files? (y/n)"
if ($addFiles -eq "y" -or $addFiles -eq "Y") {
    git add .
    Write-ColorOutput Green "✓ Files added"
}

# Commit
Write-Output ""
$commitMsg = Read-Host "Enter commit message"
if ([string]::IsNullOrWhiteSpace($commitMsg)) {
    $commitMsg = "Update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
}

git commit -m $commitMsg
Write-ColorOutput Green "✓ Changes committed"

# Push
Write-Output ""
Write-ColorOutput Blue "Pushing to GitHub..."
git push -u origin main

Write-Output ""
Write-ColorOutput Green "╔════════════════════════════════════════════════════════════╗"
Write-ColorOutput Green "║                  ✓ Successfully Pushed!                    ║"
Write-ColorOutput Green "╚════════════════════════════════════════════════════════════╝"
Write-Output ""
Write-Output "Your code is now on GitHub! 🎉"
Write-Output ""
