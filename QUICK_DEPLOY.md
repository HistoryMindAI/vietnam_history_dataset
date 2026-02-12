# 🚀 Quick Deploy Guide

## Option 1: Automated Script (Recommended)

### Windows (PowerShell)
```powershell
.\deploy.ps1
```

### Linux/Mac (Bash)
```bash
chmod +x deploy.sh
./deploy.sh
```

This will:
- ✅ Run tests
- ✅ Build Docker image
- ✅ Test Docker image
- ✅ Commit and push to GitHub
- ✅ Push Docker image to registry

---

## Option 2: Manual Steps

### Step 1: Build Docker Image
```bash
docker build -t historymindai:latest ./ai-service
```

### Step 2: Test Locally
```bash
docker run -d -p 8000:8000 --name historymindai historymindai:latest
curl http://localhost:8000/health
```

### Step 3: Push to GitHub

#### Windows
```powershell
.\push-to-github.ps1
```

#### Linux/Mac
```bash
chmod +x push-to-github.sh
./push-to-github.sh
```

### Step 4: Push Docker Image to GHCR

#### Login
```bash
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin
```

#### Tag and Push
```bash
docker tag historymindai:latest ghcr.io/YOUR_USERNAME/historymindai:latest
docker push ghcr.io/YOUR_USERNAME/historymindai:latest
```

---

## Option 3: GitHub Actions (Automatic)

Just push to GitHub and Actions will automatically:
- ✅ Run tests
- ✅ Build Docker image
- ✅ Push to GitHub Container Registry

```bash
git add .
git commit -m "Deploy: HistoryMindAI v2.2.0"
git push origin main
```

Check progress at: https://github.com/YOUR_USERNAME/vietnam_history_dataset/actions

---

## 🎯 Quick Commands

### Build
```bash
docker build -t historymindai:latest ./ai-service
```

### Run
```bash
docker run -d -p 8000:8000 --name historymindai historymindai:latest
```

### Test
```bash
curl http://localhost:8000/health
```

### Push to GitHub
```bash
git add .
git commit -m "Your message"
git push origin main
```

### Push to GHCR
```bash
docker tag historymindai:latest ghcr.io/USERNAME/historymindai:latest
docker push ghcr.io/USERNAME/historymindai:latest
```

---

## 📊 Verify Deployment

### Local
```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

### GitHub
Check: https://github.com/YOUR_USERNAME/vietnam_history_dataset

### GHCR
Check: https://github.com/YOUR_USERNAME?tab=packages

---

## 🐛 Troubleshooting

### Docker Build Fails
```bash
# Clean build
docker build --no-cache -t historymindai:latest ./ai-service
```

### Port Already in Use
```bash
# Use different port
docker run -d -p 9000:8000 historymindai:latest
```

### Git Push Fails
```bash
# Check remote
git remote -v

# Set remote
git remote set-url origin https://github.com/YOUR_USERNAME/vietnam_history_dataset.git
```

---

## 📞 Need Help?

See detailed guides:
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Complete deployment guide
- [DOCKER_README.md](DOCKER_README.md) - Docker quick reference

**Creator**: Võ Đức Hiếu (h1eudayne)  
**Email**: voduchieu42@gmail.com

---

**Ready? Let's deploy! 🚀**
