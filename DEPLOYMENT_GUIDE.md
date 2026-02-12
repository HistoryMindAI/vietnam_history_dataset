# HistoryMindAI - Deployment Guide

## 📦 Docker Deployment

### Prerequisites
- Docker installed (version 20.10+)
- Docker Compose installed (version 2.0+)
- Git installed
- 4GB RAM minimum
- 10GB disk space

---

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/vietnam_history_dataset.git
cd vietnam_history_dataset
```

### 2. Build Docker Image
```bash
# Build the image
docker build -t historymindai:latest ./ai-service

# Or use docker-compose
docker-compose build
```

### 3. Run Container
```bash
# Using docker run
docker run -d -p 8000:8000 --name historymindai historymindai:latest

# Or using docker-compose
docker-compose up -d
```

### 4. Verify Deployment
```bash
# Check container status
docker ps

# Check logs
docker logs historymindai

# Test API
curl http://localhost:8000/health
```

---

## 🔧 Docker Commands

### Build Image
```bash
# Build with tag
docker build -t historymindai:v2.2.0 ./ai-service

# Build with no cache
docker build --no-cache -t historymindai:latest ./ai-service
```

### Run Container
```bash
# Run in detached mode
docker run -d -p 8000:8000 --name historymindai historymindai:latest

# Run with custom port
docker run -d -p 9000:8000 --name historymindai historymindai:latest

# Run with environment variables
docker run -d -p 8000:8000 \
  -e PORT=8000 \
  -e INDEX_VERSION=v6 \
  --name historymindai \
  historymindai:latest
```

### Manage Container
```bash
# Start container
docker start historymindai

# Stop container
docker stop historymindai

# Restart container
docker restart historymindai

# Remove container
docker rm historymindai

# View logs
docker logs historymindai

# Follow logs
docker logs -f historymindai

# Execute command in container
docker exec -it historymindai bash
```

### Docker Compose
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Rebuild and restart
docker-compose up -d --build
```

---

## 🐙 GitHub Deployment

### 1. Initialize Git (if not already)
```bash
cd vietnam_history_dataset
git init
git add .
git commit -m "Initial commit: HistoryMindAI v2.2.0"
```

### 2. Create GitHub Repository
1. Go to https://github.com/new
2. Repository name: `vietnam_history_dataset`
3. Description: "AI-powered Vietnamese history chatbot"
4. Public or Private (your choice)
5. Don't initialize with README (we already have one)
6. Click "Create repository"

### 3. Push to GitHub
```bash
# Add remote
git remote add origin https://github.com/YOUR_USERNAME/vietnam_history_dataset.git

# Push to main branch
git branch -M main
git push -u origin main
```

### 4. Push Docker Image to GitHub Container Registry (GHCR)

#### Login to GHCR
```bash
# Create Personal Access Token (PAT) at https://github.com/settings/tokens
# Permissions needed: write:packages, read:packages, delete:packages

# Login
echo YOUR_PAT | docker login ghcr.io -u YOUR_USERNAME --password-stdin
```

#### Tag and Push Image
```bash
# Tag image for GHCR
docker tag historymindai:latest ghcr.io/YOUR_USERNAME/historymindai:latest
docker tag historymindai:latest ghcr.io/YOUR_USERNAME/historymindai:v2.2.0

# Push to GHCR
docker push ghcr.io/YOUR_USERNAME/historymindai:latest
docker push ghcr.io/YOUR_USERNAME/historymindai:v2.2.0
```

#### Make Package Public (Optional)
1. Go to https://github.com/YOUR_USERNAME?tab=packages
2. Click on `historymindai` package
3. Click "Package settings"
4. Scroll to "Danger Zone"
5. Click "Change visibility" → "Public"

---

## 🌐 Deploy to Cloud Platforms

### Deploy to Railway

1. **Create Railway Account**: https://railway.app
2. **Create New Project**: Click "New Project"
3. **Deploy from GitHub**:
   - Connect GitHub repository
   - Select `vietnam_history_dataset`
   - Railway will auto-detect Dockerfile
4. **Configure**:
   - Root directory: `ai-service`
   - Port: 8000
5. **Deploy**: Railway will build and deploy automatically

### Deploy to Render

1. **Create Render Account**: https://render.com
2. **Create New Web Service**
3. **Connect Repository**: Link GitHub repo
4. **Configure**:
   - Name: `historymindai`
   - Environment: Docker
   - Dockerfile path: `ai-service/Dockerfile`
   - Port: 8000
5. **Deploy**: Click "Create Web Service"

### Deploy to Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
flyctl auth login

# Launch app
cd ai-service
flyctl launch

# Deploy
flyctl deploy
```

### Deploy to Google Cloud Run

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Login
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Build and push to GCR
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/historymindai ./ai-service

# Deploy to Cloud Run
gcloud run deploy historymindai \
  --image gcr.io/YOUR_PROJECT_ID/historymindai \
  --platform managed \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --port 8000 \
  --memory 2Gi
```

---

## 📊 Monitoring & Health Checks

### Health Check Endpoint
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "2.2.0",
  "index_version": "v6"
}
```

### API Endpoints
```bash
# Query endpoint
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Trận Bạch Đằng năm 1288"}'

# Docs endpoint
curl http://localhost:8000/docs
```

---

## 🔒 Security Best Practices

### 1. Environment Variables
Never commit sensitive data. Use `.env` file:

```bash
# .env
PORT=8000
INDEX_VERSION=v6
API_KEY=your_secret_key_here
```

Add to `.gitignore`:
```
.env
*.env
```

### 2. Docker Security
```dockerfile
# Use non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Scan for vulnerabilities
docker scan historymindai:latest
```

### 3. Network Security
```bash
# Use Docker networks
docker network create historymind-network
docker run --network historymind-network historymindai
```

---

## 🐛 Troubleshooting

### Container Won't Start
```bash
# Check logs
docker logs historymindai

# Check if port is in use
netstat -ano | findstr :8000  # Windows
lsof -i :8000                 # Linux/Mac

# Remove and recreate
docker rm -f historymindai
docker run -d -p 8000:8000 --name historymindai historymindai:latest
```

### ONNX Model Issues
```bash
# Verify model size in container
docker exec historymindai ls -lh /app/onnx_model/

# Expected: ~130MB
# If < 1MB, it's a Git LFS pointer
```

### FAISS Index Issues
```bash
# Verify index exists
docker exec historymindai ls -lh /app/faiss_index/

# Expected: index.bin should exist
```

### Memory Issues
```bash
# Increase Docker memory limit
docker run -d -p 8000:8000 --memory="4g" historymindai:latest

# Or in docker-compose.yml
services:
  historymindai:
    mem_limit: 4g
```

---

## 📈 Performance Optimization

### 1. Multi-stage Build (Optional)
```dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
WORKDIR /app
COPY . .
CMD ["python", "start_server.py"]
```

### 2. Docker Layer Caching
```bash
# Build with BuildKit
DOCKER_BUILDKIT=1 docker build -t historymindai:latest ./ai-service
```

### 3. Resource Limits
```yaml
# docker-compose.yml
services:
  historymindai:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

---

## 📝 Deployment Checklist

### Pre-deployment
- [ ] All tests passing (467/470)
- [ ] Docker image builds successfully
- [ ] Container runs locally
- [ ] Health check endpoint works
- [ ] API endpoints tested
- [ ] Documentation updated

### GitHub
- [ ] Repository created
- [ ] Code pushed to main branch
- [ ] README.md updated
- [ ] .gitignore configured
- [ ] Git LFS configured (for large files)

### Docker Registry
- [ ] Image tagged correctly
- [ ] Image pushed to registry (GHCR/Docker Hub)
- [ ] Package visibility set (public/private)
- [ ] Image pull tested

### Production
- [ ] Environment variables configured
- [ ] SSL/TLS certificate installed
- [ ] Domain name configured
- [ ] Monitoring setup
- [ ] Backup strategy defined
- [ ] Rollback plan ready

---

## 🎯 Quick Commands Reference

```bash
# Build
docker build -t historymindai:latest ./ai-service

# Run
docker run -d -p 8000:8000 --name historymindai historymindai:latest

# Logs
docker logs -f historymindai

# Stop
docker stop historymindai

# Remove
docker rm historymindai

# Push to GitHub
git add .
git commit -m "Update: description"
git push origin main

# Push to GHCR
docker tag historymindai:latest ghcr.io/USERNAME/historymindai:latest
docker push ghcr.io/USERNAME/historymindai:latest
```

---

## 📞 Support

**Creator**: Võ Đức Hiếu (h1eudayne)  
**Email**: voduchieu42@gmail.com  
**GitHub**: [h1eudayne](https://github.com/h1eudayne)

---

## 🎉 Success!

Your HistoryMindAI is now deployed! 🚀

Access your API at: `http://localhost:8000`  
API Documentation: `http://localhost:8000/docs`

**Happy deploying! 🎊**
