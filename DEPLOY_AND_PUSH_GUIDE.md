# 🚀 Deploy Docker và Push lên GitHub - Hướng dẫn Đầy đủ

## 📋 Mục lục
1. [Chuẩn bị](#chuẩn-bị)
2. [Build Docker Image](#build-docker-image)
3. [Test Docker Image](#test-docker-image)
4. [Push lên GitHub](#push-lên-github)
5. [Push Docker Image lên GHCR](#push-docker-image-lên-ghcr)
6. [Tự động hóa với GitHub Actions](#tự-động-hóa-với-github-actions)

---

## 🎯 Chuẩn bị

### Yêu cầu
- ✅ Docker đã cài đặt
- ✅ Git đã cài đặt
- ✅ Tài khoản GitHub
- ✅ GitHub Personal Access Token (cho GHCR)

### Kiểm tra cài đặt
```bash
# Kiểm tra Docker
docker --version

# Kiểm tra Git
git --version

# Kiểm tra Python
python --version
```

---

## 🐳 Build Docker Image

### Cách 1: Sử dụng Script Tự động (Khuyến nghị)

#### Windows (PowerShell)
```powershell
# Chạy script deploy
.\deploy.ps1

# Hoặc với options
.\deploy.ps1 -GitHubUsername "your-username" -SkipTests
```

#### Linux/Mac (Bash)
```bash
# Cấp quyền thực thi
chmod +x deploy.sh

# Chạy script
./deploy.sh

# Hoặc với biến môi trường
GITHUB_USERNAME=your-username ./deploy.sh
```

### Cách 2: Build Thủ công

```bash
# Di chuyển vào thư mục project
cd vietnam_history_dataset

# Build Docker image
docker build -t historymindai:latest ./ai-service

# Build với version tag
docker build -t historymindai:2.2.0 ./ai-service

# Build không dùng cache (nếu cần)
docker build --no-cache -t historymindai:latest ./ai-service
```

### Kiểm tra Image đã Build
```bash
# Xem danh sách images
docker images | grep historymindai

# Kết quả mong đợi:
# historymindai   latest   abc123def456   2 minutes ago   1.2GB
```

---

## 🧪 Test Docker Image

### Test 1: Chạy Container
```bash
# Chạy container
docker run -d -p 8000:8000 --name historymindai-test historymindai:latest

# Đợi 10 giây để container khởi động
# Windows
timeout /t 10

# Linux/Mac
sleep 10
```

### Test 2: Health Check
```bash
# Kiểm tra health endpoint
curl http://localhost:8000/health

# Kết quả mong đợi:
# {"status":"healthy","version":"2.2.0","index_version":"v6"}
```

### Test 3: Query API
```bash
# Test query endpoint
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Trận Bạch Đằng năm 1288\"}"
```

### Test 4: Xem Logs
```bash
# Xem logs
docker logs historymindai-test

# Follow logs
docker logs -f historymindai-test
```

### Dọn dẹp sau Test
```bash
# Dừng và xóa container test
docker stop historymindai-test
docker rm historymindai-test
```

---

## 📤 Push lên GitHub

### Bước 1: Kiểm tra Git Status
```bash
# Xem trạng thái hiện tại
git status

# Xem các file đã thay đổi
git diff
```

### Bước 2: Add Files

#### Cách 1: Sử dụng Script

##### Windows
```powershell
.\push-to-github.ps1
```

##### Linux/Mac
```bash
chmod +x push-to-github.sh
./push-to-github.sh
```

#### Cách 2: Thủ công
```bash
# Add tất cả files
git add .

# Hoặc add từng file cụ thể
git add ai-service/
git add tests/
git add *.md
```

### Bước 3: Commit Changes
```bash
# Commit với message
git commit -m "Deploy: HistoryMindAI v2.2.0 - Production Ready"

# Hoặc commit với message chi tiết
git commit -m "Deploy: HistoryMindAI v2.2.0

- Added Context7 integration
- Added greeting responses
- Added fuzzy matching
- Added year range query
- 467/470 tests passing
- Production ready"
```

### Bước 4: Push to GitHub

#### Lần đầu tiên (chưa có remote)
```bash
# Thêm remote repository
git remote add origin https://github.com/YOUR_USERNAME/vietnam_history_dataset.git

# Push lần đầu
git push -u origin main
```

#### Lần sau (đã có remote)
```bash
# Push thẳng
git push origin main

# Hoặc push với force (cẩn thận!)
git push -f origin main
```

### Bước 5: Verify trên GitHub
1. Mở https://github.com/YOUR_USERNAME/vietnam_history_dataset
2. Kiểm tra code đã được push
3. Kiểm tra commit history
4. Kiểm tra Actions (nếu có)

---

## 🐙 Push Docker Image lên GHCR

### Bước 1: Tạo GitHub Personal Access Token

1. Vào https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Chọn scopes:
   - ✅ `write:packages`
   - ✅ `read:packages`
   - ✅ `delete:packages`
4. Click "Generate token"
5. **Lưu token lại** (chỉ hiện 1 lần!)

### Bước 2: Login vào GHCR
```bash
# Thay YOUR_TOKEN và YOUR_USERNAME
echo YOUR_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Kết quả mong đợi:
# Login Succeeded
```

### Bước 3: Tag Image cho GHCR
```bash
# Tag với latest
docker tag historymindai:latest ghcr.io/YOUR_USERNAME/historymindai:latest

# Tag với version
docker tag historymindai:latest ghcr.io/YOUR_USERNAME/historymindai:2.2.0

# Tag với cả hai
docker tag historymindai:latest ghcr.io/YOUR_USERNAME/historymindai:latest
docker tag historymindai:latest ghcr.io/YOUR_USERNAME/historymindai:2.2.0
```

### Bước 4: Push Image lên GHCR
```bash
# Push latest
docker push ghcr.io/YOUR_USERNAME/historymindai:latest

# Push version
docker push ghcr.io/YOUR_USERNAME/historymindai:2.2.0

# Push cả hai
docker push ghcr.io/YOUR_USERNAME/historymindai:latest
docker push ghcr.io/YOUR_USERNAME/historymindai:2.2.0
```

### Bước 5: Đặt Package thành Public (Tùy chọn)

1. Vào https://github.com/YOUR_USERNAME?tab=packages
2. Click vào package `historymindai`
3. Click "Package settings"
4. Scroll xuống "Danger Zone"
5. Click "Change visibility" → "Public"
6. Confirm

### Bước 6: Test Pull từ GHCR
```bash
# Pull image
docker pull ghcr.io/YOUR_USERNAME/historymindai:latest

# Run image từ GHCR
docker run -d -p 8000:8000 ghcr.io/YOUR_USERNAME/historymindai:latest

# Test
curl http://localhost:8000/health
```

---

## 🤖 Tự động hóa với GitHub Actions

### Bước 1: Kiểm tra Workflow File
File đã được tạo tại: `.github/workflows/docker-publish.yml`

### Bước 2: Push Code lên GitHub
```bash
git add .github/workflows/docker-publish.yml
git commit -m "Add: GitHub Actions workflow for Docker build and push"
git push origin main
```

### Bước 3: Xem Actions Running
1. Vào https://github.com/YOUR_USERNAME/vietnam_history_dataset/actions
2. Xem workflow "Docker Build and Push" đang chạy
3. Click vào workflow để xem chi tiết

### Bước 4: Verify Deployment
Sau khi Actions hoàn thành:
1. Kiểm tra package tại https://github.com/YOUR_USERNAME?tab=packages
2. Pull image: `docker pull ghcr.io/YOUR_USERNAME/historymindai:latest`
3. Test image

### Workflow sẽ tự động:
- ✅ Run tests
- ✅ Build Docker image
- ✅ Push to GHCR
- ✅ Test Docker image
- ✅ Notify kết quả

---

## 📊 Checklist Hoàn chỉnh

### Pre-deployment
- [ ] Tất cả tests pass (467/470)
- [ ] Docker đã cài đặt
- [ ] Git đã cài đặt
- [ ] GitHub account đã có
- [ ] GitHub token đã tạo

### Docker Build
- [ ] Image build thành công
- [ ] Image size hợp lý (~1-2GB)
- [ ] Container chạy được
- [ ] Health check pass
- [ ] API endpoints hoạt động

### GitHub Push
- [ ] Code đã commit
- [ ] Remote repository đã add
- [ ] Code đã push lên GitHub
- [ ] Commit history đúng
- [ ] README.md hiển thị đúng

### GHCR Push
- [ ] Login GHCR thành công
- [ ] Image đã tag đúng
- [ ] Image đã push lên GHCR
- [ ] Package visibility đã set
- [ ] Pull test thành công

### GitHub Actions
- [ ] Workflow file đã push
- [ ] Actions đã chạy thành công
- [ ] Image tự động build
- [ ] Tests tự động pass
- [ ] Notifications hoạt động

---

## 🎯 Các Lệnh Quan trọng

### Docker
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

# Clean up
docker system prune -a
```

### Git
```bash
# Status
git status

# Add
git add .

# Commit
git commit -m "message"

# Push
git push origin main

# Pull
git pull origin main

# Check remote
git remote -v
```

### GHCR
```bash
# Login
echo TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Tag
docker tag historymindai:latest ghcr.io/USERNAME/historymindai:latest

# Push
docker push ghcr.io/USERNAME/historymindai:latest

# Pull
docker pull ghcr.io/USERNAME/historymindai:latest
```

---

## 🐛 Troubleshooting

### Docker Build Fails
```bash
# Xem logs chi tiết
docker build --progress=plain -t historymindai:latest ./ai-service

# Build không dùng cache
docker build --no-cache -t historymindai:latest ./ai-service

# Kiểm tra Dockerfile
cat ai-service/Dockerfile
```

### Container Won't Start
```bash
# Xem logs
docker logs historymindai

# Xem logs chi tiết
docker logs --tail 100 historymindai

# Chạy interactive để debug
docker run -it --rm historymindai:latest bash
```

### Git Push Fails
```bash
# Kiểm tra remote
git remote -v

# Set lại remote
git remote set-url origin https://github.com/USERNAME/vietnam_history_dataset.git

# Force push (cẩn thận!)
git push -f origin main
```

### GHCR Login Fails
```bash
# Kiểm tra token
echo $GITHUB_TOKEN

# Login lại
docker logout ghcr.io
echo TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Kiểm tra permissions của token
# Token cần có: write:packages, read:packages
```

### GitHub Actions Fails
1. Vào Actions tab
2. Click vào failed workflow
3. Xem logs chi tiết
4. Fix lỗi và push lại

---

## 📞 Hỗ trợ

### Documentation
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Hướng dẫn chi tiết
- [DOCKER_README.md](DOCKER_README.md) - Docker quick reference
- [QUICK_DEPLOY.md](QUICK_DEPLOY.md) - Deploy nhanh

### Contact
**Creator**: Võ Đức Hiếu (h1eudayne)  
**Email**: voduchieu42@gmail.com  
**GitHub**: [h1eudayne](https://github.com/h1eudayne)

---

## 🎉 Hoàn thành!

Sau khi hoàn thành tất cả các bước:

✅ Docker image đã build  
✅ Docker image đã test  
✅ Code đã push lên GitHub  
✅ Docker image đã push lên GHCR  
✅ GitHub Actions đã setup  

**Chúc mừng! Bạn đã deploy thành công HistoryMindAI! 🚀**

---

**Version**: 2.2.0  
**Date**: 2026-02-13  
**Status**: Production Ready ✅
