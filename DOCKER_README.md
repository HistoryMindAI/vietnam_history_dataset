# 🐳 HistoryMindAI - Docker Deployment

Quick guide for deploying HistoryMindAI using Docker.

---

## 🚀 Quick Start (3 Steps)

### 1. Build Image
```bash
docker build -t historymindai:latest ./ai-service
```

### 2. Run Container
```bash
docker run -d -p 8000:8000 --name historymindai historymindai:latest
```

### 3. Test
```bash
curl http://localhost:8000/health
```

**Done! 🎉** Access API at http://localhost:8000

---

## 📦 Using Docker Compose

### Start
```bash
docker-compose up -d
```

### Stop
```bash
docker-compose down
```

### View Logs
```bash
docker-compose logs -f
```

---

## 🐙 Pull from GitHub Container Registry

### Public Image
```bash
# Pull latest
docker pull ghcr.io/YOUR_USERNAME/historymindai:latest

# Run
docker run -d -p 8000:8000 ghcr.io/YOUR_USERNAME/historymindai:latest
```

---

## 🔧 Configuration

### Environment Variables
```bash
docker run -d -p 8000:8000 \
  -e PORT=8000 \
  -e INDEX_VERSION=v6 \
  --name historymindai \
  historymindai:latest
```

### Custom Port
```bash
# Run on port 9000
docker run -d -p 9000:8000 --name historymindai historymindai:latest
```

### Memory Limit
```bash
docker run -d -p 8000:8000 --memory="4g" historymindai:latest
```

---

## 📊 Monitoring

### View Logs
```bash
docker logs historymindai
docker logs -f historymindai  # Follow logs
```

### Container Stats
```bash
docker stats historymindai
```

### Health Check
```bash
curl http://localhost:8000/health
```

---

## 🛠️ Management

### Start/Stop
```bash
docker start historymindai
docker stop historymindai
docker restart historymindai
```

### Remove
```bash
docker stop historymindai
docker rm historymindai
```

### Execute Commands
```bash
docker exec -it historymindai bash
```

---

## 🎯 API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Query
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Trận Bạch Đằng năm 1288"}'
```

### API Documentation
Open in browser: http://localhost:8000/docs

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Find process using port 8000
netstat -ano | findstr :8000  # Windows
lsof -i :8000                 # Linux/Mac

# Use different port
docker run -d -p 9000:8000 historymindai:latest
```

### Container Won't Start
```bash
# Check logs
docker logs historymindai

# Remove and recreate
docker rm -f historymindai
docker run -d -p 8000:8000 --name historymindai historymindai:latest
```

### Out of Memory
```bash
# Increase memory limit
docker run -d -p 8000:8000 --memory="4g" historymindai:latest
```

---

## 📈 Performance Tips

### Use BuildKit
```bash
DOCKER_BUILDKIT=1 docker build -t historymindai:latest ./ai-service
```

### Clean Up
```bash
# Remove unused images
docker image prune -a

# Remove unused containers
docker container prune

# Remove everything unused
docker system prune -a
```

---

## 🌐 Deploy to Cloud

### Railway
1. Connect GitHub repo
2. Select `ai-service` directory
3. Deploy automatically

### Render
1. Create Web Service
2. Connect repo
3. Set Dockerfile path: `ai-service/Dockerfile`

### Fly.io
```bash
flyctl launch
flyctl deploy
```

---

## 📞 Support

**Issues?** Check [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions.

**Creator**: Võ Đức Hiếu (h1eudayne)  
**Email**: voduchieu42@gmail.com

---

## ✅ Checklist

- [ ] Docker installed
- [ ] Image built successfully
- [ ] Container running
- [ ] Health check passes
- [ ] API responds correctly
- [ ] Logs look good

**All green? You're ready to go! 🚀**
