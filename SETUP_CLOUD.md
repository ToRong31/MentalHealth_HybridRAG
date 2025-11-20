# Hướng dẫn sử dụng Milvus Cloud (Zilliz)

Dự án này được cấu hình để sử dụng **Zilliz Cloud** (Milvus managed service) thay vì chạy Milvus local.

## 🌐 Lợi ích của Milvus Cloud

- ✅ Không cần chạy Milvus container local (tiết kiệm RAM)
- ✅ Auto-scaling và high availability
- ✅ Managed backups
- ✅ Free tier cho development

## 📝 Cách setup Zilliz Cloud

### 1. Đăng ký tài khoản

Truy cập: https://cloud.zilliz.com/signup

- Đăng ký với email hoặc GitHub
- Free tier: 1 cluster với 1 CU (Compute Unit)

### 2. Tạo Cluster

1. Sau khi đăng nhập, click **Create Cluster**
2. Chọn:
   - **Free Tier** (hoặc paid nếu cần)
   - **Region**: chọn gần bạn nhất (e.g., AWS US-West-2)
   - **Cluster Name**: đặt tên bất kỳ (e.g., `chatbot-dev`)
3. Click **Create**
4. Chờ 2-3 phút để cluster được provision

### 3. Lấy thông tin kết nối

Sau khi cluster ready:

1. Click vào cluster name
2. Tìm **Connection Details**:
   - **Endpoint**: `https://xxx.aws-region.vectordb.zillizcloud.com:19530`
   - **Token**: Click "Create Token" để tạo token mới

### 4. Cập nhật file .env

Mở file `backend/src/.env` và cập nhật:

```env
# Milvus Cloud (Zilliz)
MILVUS_URI=https://your-cluster-xxx.aws-us-west-2.vectordb.zillizcloud.com:19530
MILVUS_TOKEN=db_admin:xxxxxxxxxxxxxxxxxxxxxxxxxx
MILVUS_DB=default
MILVUS_COLLECTION=kg_entities
```

**Thay thế**:
- `MILVUS_URI`: Endpoint từ Zilliz console
- `MILVUS_TOKEN`: Token bạn vừa tạo

### 5. Test kết nối

```bash
# Test với Python
cd backend
python -c "from pymilvus import connections; connections.connect(uri='your-uri', token='your-token'); print('Connected!')"
```

## 🔄 Chuyển về Local Milvus (nếu cần)

Nếu bạn muốn dùng Milvus local thay vì cloud:

### 1. Uncomment Milvus service

Mở `docker-compose.yaml` và uncomment:

```yaml
# Milvus Vector Database (Standalone)
milvus:
  image: milvusdb/milvus:v2.3.3
  container_name: milvus
  restart: unless-stopped
  ports:
    - "19530:19530"
    - "9091:9091"
  environment:
    ETCD_USE_EMBED: "true"
    COMMON_STORAGETYPE: local
  volumes:
    - milvus_data:/var/lib/milvus
  networks:
    - app-network
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 40s
```

### 2. Uncomment dependencies

Trong backend service:

```yaml
depends_on:
  neo4j:
    condition: service_healthy
  milvus:
    condition: service_healthy  # Uncomment này
```

### 3. Uncomment volume

```yaml
volumes:
  neo4j_data:
  neo4j_logs:
  neo4j_plugins:
  neo4j_import:
  milvus_data:  # Uncomment này
```

### 4. Cập nhật .env

```env
# Local Milvus
MILVUS_URI=http://localhost:19530
MILVUS_TOKEN=
```

### 5. Restart docker-compose

```bash
docker-compose down
docker-compose up -d --build
```

## 📊 So sánh Cloud vs Local

| Feature | Zilliz Cloud | Local Milvus |
|---------|--------------|--------------|
| Setup | Dễ, 5 phút | Cần Docker, config |
| RAM Usage | 0 (cloud) | ~2-4GB |
| Performance | Tốt, scaling auto | Phụ thuộc máy local |
| Cost | Free tier 1 CU | Free |
| Backup | Auto | Manual |
| Monitoring | Built-in dashboard | Cần setup riêng |
| Production | Ready | Cần hardening |

## 🔍 Monitoring

### Zilliz Cloud Dashboard

Truy cập: https://cloud.zilliz.com/

- View cluster status
- Query performance metrics
- Storage usage
- API usage statistics

### Local Milvus

```bash
# Check status
docker-compose ps milvus

# View logs
docker-compose logs -f milvus

# Milvus Web UI (nếu có cài Attu)
# http://localhost:8000
```

## 🆘 Troubleshooting

### Lỗi kết nối Cloud

```
Error: failed to connect to milvus
```

**Giải pháp**:
1. Kiểm tra `MILVUS_URI` có đúng format: `https://xxx.vectordb.zillizcloud.com:19530`
2. Kiểm tra `MILVUS_TOKEN` còn valid (có thể bị expire)
3. Kiểm tra cluster status trên Zilliz console
4. Kiểm tra firewall/network

### Collection không tồn tại

```
Error: collection 'kg_entities' not found
```

**Giải pháp**:
1. Collection sẽ được tạo tự động khi chạy ingestion
2. Hoặc tạo manual qua Zilliz console
3. Chạy ingestion script để tạo và populate data

### Token expired

**Giải pháp**:
1. Vào Zilliz console
2. Tạo token mới
3. Cập nhật `MILVUS_TOKEN` trong `.env`
4. Restart backend: `docker-compose restart backend`

## 📚 Tài liệu thêm

- [Zilliz Cloud Documentation](https://docs.zilliz.com/docs)
- [Milvus Python SDK](https://milvus.io/docs/install-pymilvus.md)
- [Zilliz Free Tier Limits](https://docs.zilliz.com/docs/free-tier)

---

💡 **Khuyến nghị**: Dùng **Zilliz Cloud** cho development và testing, chuyển sang dedicated cluster hoặc self-hosted Milvus cho production nếu cần control cao hơn.

