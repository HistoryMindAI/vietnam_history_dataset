# 🚀 START HERE - Deploy và Push lên GitHub

## 📝 Bạn cần làm gì?

### ✅ Bước 1: Build Docker Image (2 phút)
```bash
docker build -t historymindai:latest ./ai-service
```

### ✅ Bước 2: Test Docker Image (1 phút)
```bash
docker run -d -p 8000:8000 --name historymindai historymindai:latest
curl http://localhost:8000/health
```

### ✅ Bước 3: Push lên GitHub (2 phút)

#### Windows
```powershell
.\push-to-github.ps1
```

#### Linux/Mac
```bash
chmod +x push-to-github.sh
./push-to-github.sh
```

### ✅ Bước 4: Push Docker Image lên GHCR (3 phút)

#### 4.1. Tạo GitHub Token
1. Vào https://github.com/settings/tokens
2. Generate new token (classic)
3. Chọn: `write:packages`, `read:packages`
4. Copy token

#### 4.2. Login và Push
```bash
# Login (thay YOUR_TOKEN và YOUR_USERNAME)
echo YOUR_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Tag
docker tag historymindai:latest ghcr.io/YOUR_USERNAME/historymindai:latest

# Push
docker push ghcr.io/YOUR_USERNAME/historymindai:latest
```

---

## 🎯 Hoặc Dùng Script Tự động (Khuyến nghị)

### Windows
```powershell
.\deploy.ps1
```

### Linux/Mac
```bash
chmod +x deploy.sh
./deploy.sh
```

Script sẽ tự động:
- ✅ Run tests
- ✅ Build Docker image
- ✅ Test Docker image
- ✅ Commit và push to GitHub
- ✅ Push Docker image to GHCR

---

## 📚 Cần Hướng dẫn Chi tiết?

- **Hướng dẫn đầy đủ**: [DEPLOY_AND_PUSH_GUIDE.md](DEPLOY_AND_PUSH_GUIDE.md)
- **Docker guide**: [DOCKER_README.md](DOCKER_README.md)
- **Deploy nhanh**: [QUICK_DEPLOY.md](QUICK_DEPLOY.md)
- **Deployment guide**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

## 🐛 Gặp vấn đề?

### Docker build fails
```bash
docker build --no-cache -t historymindai:latest ./ai-service
```

### Port đã được sử dụng
```bash
docker run -d -p 9000:8000 historymindai:latest
```

### Git push fails
```bash
git remote set-url origin https://github.com/YOUR_USERNAME/vietnam_history_dataset.git
git push -f origin main
```

---

## ✅ Checklist Nhanh

- [ ] Docker đã cài
- [ ] Git đã cài
- [ ] GitHub account đã có
- [ ] GitHub token đã tạo
- [ ] Image build thành công
- [ ] Container chạy được
- [ ] Code đã push lên GitHub
- [ ] Image đã push lên GHCR

---

## 🎉 Xong!

Sau khi hoàn thành:
- ✅ Code trên GitHub: https://github.com/YOUR_USERNAME/vietnam_history_dataset
- ✅ Docker image trên GHCR: https://github.com/YOUR_USERNAME?tab=packages
- ✅ API running: http://localhost:8000

**Chúc mừng! Bạn đã deploy thành công! 🚀**

---

**Cần hỗ trợ?**  
Email: voduchieu42@gmail.com  
GitHub: [h1eudayne](https://github.com/h1eudayne)
