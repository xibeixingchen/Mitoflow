# MitoFlow Web 部署技术设计文档

## 版本信息
- 版本: v1.0
- 日期: 2024-01
- 状态: 设计评审

---

## 目录
1. [概述](#1-概述)
2. [系统架构](#2-系统架构)
3. [技术选型](#3-技术选型)
4. [详细设计](#4-详细设计)
5. [部署方案](#5-部署方案)
6. [安全设计](#6-安全设计)
7. [性能优化](#7-性能优化)
8. [监控与运维](#8-监控与运维)
9. [风险评估](#9-风险评估)

---

## 1. 概述

### 1.1 项目背景
MitoFlow 是一个植物线粒体基因组注释平台，需要将现有的 Python CLI 工具部署为 Web 服务，供外部用户访问。

### 1.2 设计目标
| 目标 | 优先级 | 说明 |
|------|--------|------|
| 可用性 | P0 | 99.9% 服务可用性 |
| 并发支持 | P0 | 支持 5-10 个并发分析任务 |
| 安全性 | P0 | HTTPS, 输入验证, 沙箱执行 |
| 可扩展性 | P1 | 支持水平扩展 |
| 成本控制 | P1 | 优化资源使用 |

### 1.3 约束条件
- 单个分析任务可能占用 4-8GB 内存
- 分析时间: 5分钟 - 2小时
- 输入文件大小限制: 100MB
- 需要持久化存储结果文件

---

## 2. 系统架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户层 (User Layer)                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                         │
│  │   Browser   │  │   Mobile    │  │   API Client│                         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                         │
└─────────┼────────────────┼────────────────┼─────────────────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            接入层 (Access Layer)                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        Nginx Reverse Proxy                            │  │
│  │  • SSL termination  • Rate limiting  • Load balancing  • Static files │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           应用层 (Application Layer)                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   Streamlit     │  │   FastAPI       │  │   Celery Workers            │  │
│  │   Frontend      │  │   Backend API   │  │   (Background Tasks)        │  │
│  │                 │  │                 │  │                             │  │
│  │  • File Upload  │  │  • Task Mgmt    │  │  • HMM Search               │  │
│  │  • Progress UI  │  │  • Validation   │  │  • BLAST Search             │  │
│  │  • Results      │  │  • Auth (v2)    │  │  • Gene Prediction          │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           数据层 (Data Layer)                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │     Redis       │  │   Object Store  │  │   PostgreSQL (v2)           │  │
│  │                 │  │   (MinIO/S3)    │  │                             │  │
│  │  • Task Queue   │  │                 │  │  • User Data                │  │
│  │  • Caching      │  │  • Input Files  │  │  • Task History             │  │
│  │  • Rate Limit   │  │  • Results      │  │  • Metadata                 │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 组件职责

| 组件 | 职责 | 技术 |
|------|------|------|
| Nginx | 反向代理、SSL、静态文件、限流 | Nginx 1.24+ |
| Frontend | 用户界面、文件上传、结果展示 | Streamlit 1.28+ |
| Backend API | REST API、任务管理、状态查询 | FastAPI 0.104+ |
| Worker | 后台任务执行、生物信息学分析 | Celery 5.3+ |
| Redis | 消息队列、缓存、速率限制 | Redis 7.0+ |
| Object Store | 文件存储（输入/输出） | MinIO / AWS S3 |

---

## 3. 技术选型

### 3.1 方案对比

#### 前端方案
| 方案 | 优点 | 缺点 | 评估 |
|------|------|------|------|
| **Streamlit** | 快速开发、Python原生、适合MVP | 定制性有限、SEO差 | ✅ 推荐 (Phase 1) |
| React + FastAPI | 灵活、现代、可扩展 | 开发周期长、需要前端技能 | Phase 2 |
| Gradio | 适合ML demo、简单 | 功能有限 | 备选 |

#### 后端方案
| 方案 | 优点 | 缺点 | 评估 |
|------|------|------|------|
| **FastAPI + Celery** | 高性能、异步、成熟 | 复杂度较高 | ✅ 推荐 |
| Flask + RQ | 简单、易上手 | 性能较低 | 备选 |
| Django | 功能全、admin强 | 重量级、学习曲线 | 不适合 |

#### 部署方案
| 方案 | 优点 | 缺点 | 评估 |
|------|------|------|------|
| **Docker Compose** | 简单、适合单机 | 扩展性有限 | ✅ Phase 1 |
| Kubernetes | 高可用、自动扩展 | 复杂、运维成本高 | Phase 2 |
| Serverless (Fargate) | 按需付费、无运维 | 冷启动、限制多 | 备选 |

### 3.2 最终选型

```yaml
Phase 1 (MVP):
  Frontend: Streamlit
  Backend: FastAPI
  Task Queue: Celery + Redis
  Deployment: Docker Compose
  Server: Single VPS (8 vCPU, 32GB RAM)

Phase 2 (Production):
  Frontend: React + TypeScript
  Backend: FastAPI
  Task Queue: Celery + Redis Cluster
  Deployment: Kubernetes (EKS/GKE)
  Server: Auto-scaling group
```

---

## 4. 详细设计

### 4.1 API 设计

#### 核心端点

```yaml
POST /api/annotate:
  summary: 提交注释任务
  consumes: multipart/form-data
  parameters:
    - file: FASTA file (max 100MB)
    - name: Sample name
    - threads: CPU threads (1-8)
    - skip_trna: boolean
    - skip_rrna: boolean
    - skip_qc: boolean
  responses:
    202: 
      description: Task accepted
      body: { task_id, status, estimated_time }
    400: Validation error
    429: Rate limit exceeded

GET /api/tasks/{task_id}:
  summary: 查询任务状态
  responses:
    200:
      body: { task_id, status, progress, message, result_url }
    404: Task not found

GET /api/results/{task_id}/download:
  summary: 下载结果
  produces: application/zip
  responses:
    200: ZIP file
    400: Task not completed

DELETE /api/tasks/{task_id}:
  summary: 删除任务
  responses:
    200: Deleted
    404: Not found
```

#### 状态机

```
[pending] → (upload complete) → [running] → (success) → [completed]
                                    ↓
                              (failure) → [failed]
```

### 4.2 数据模型

```python
class Task(BaseModel):
    task_id: UUID
    status: TaskStatus  # pending, running, completed, failed
    created_at: datetime
    updated_at: datetime
    
    # Input
    input_file: Path
    sample_name: str
    parameters: dict
    
    # Output
    output_dir: Optional[Path]
    result_archive: Optional[Path]
    
    # Runtime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    
    # Resource tracking
    peak_memory_mb: Optional[int]
    cpu_time_seconds: Optional[float]
```

### 4.3 任务执行流程

```
1. 用户上传文件
   ↓
2. API 接收并验证
   - 文件类型检查
   - 文件大小检查
   - 病毒扫描 (ClamAV)
   ↓
3. 保存到对象存储
   - 生成唯一 ID
   - 上传到 MinIO/S3
   ↓
4. 创建任务记录 (Redis)
   - 状态 = pending
   - 加入任务队列
   ↓
5. Celery Worker 领取任务
   - 状态 = running
   - 下载输入文件
   ↓
6. 执行分析流程
   - 在沙箱容器中运行
   - 实时更新进度
   ↓
7. 结果处理
   - 打包结果
   - 上传对象存储
   - 状态 = completed
   ↓
8. 清理临时文件
   - 保留 7 天
   - 定时任务清理
```

### 4.4 文件存储设计

```
Object Store 结构:

s3://mitoflow/
├── uploads/
│   └── {task_id}/
│       └── input.fasta
├── results/
│   └── {task_id}/
│       ├── gff/
│       ├── genbank/
│       ├── fasta/
│       ├── report/
│       └── mitoflow_results.zip
└── temp/
    └── {task_id}/  # 临时文件，定期清理
```

### 4.5 容器设计

#### API 容器
```dockerfile
- Base: python:3.11-slim
- Expose: 8000
- Resources: 1 CPU, 2GB RAM
- Health check: /api/health
```

#### Worker 容器
```dockerfile
- Base: python:3.11-slim + bioinformatics tools
- Resources: 4 CPU, 8GB RAM (limit)
- Concurrency: 2 workers per container
- Auto-scaling based on queue depth
```

#### Frontend 容器
```dockerfile
- Base: python:3.11-slim
- Expose: 8501
- Resources: 0.5 CPU, 1GB RAM
```

---

## 5. 部署方案

### 5.1 服务器规格

#### 最小配置 (MVP)
```yaml
Server:
  CPU: 8 vCPU
  RAM: 32 GB
  Disk: 200 GB SSD
  Network: 100 Mbps
  OS: Ubuntu 22.04 LTS
  
Cost Estimate:
  AWS EC2 (t3.2xlarge): ~$250/month
  Alibaba Cloud (ecs.c7.2xlarge): ~$200/month
  Hetzner (CPX51): ~$100/month
```

#### 推荐配置 (Production)
```yaml
Server:
  CPU: 16 vCPU
  RAM: 64 GB
  Disk: 500 GB SSD
  Network: 1 Gbps
```

### 5.2 部署步骤

#### 准备阶段
1. 域名注册和 DNS 配置
2. SSL 证书申请 (Let's Encrypt)
3. 服务器安全加固

#### 部署阶段
```bash
# 1. 安装 Docker 和 Docker Compose
curl -fsSL https://get.docker.com | sh

# 2. 克隆代码
git clone https://github.com/mitoflow/mitoflow.git
cd mitoflow/deploy/docker

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 4. 启动服务
docker-compose up -d

# 5. 验证
curl https://your-domain.com/api/health
```

### 5.3 配置管理

#### 环境变量
```bash
# .env 文件
DOMAIN=mitoflow.example.com
EMAIL=admin@example.com

# Database
REDIS_URL=redis://redis:6379/0

# Storage
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=xxx
MINIO_SECRET_KEY=xxx

# Security
SECRET_KEY=random-secret-key
MAX_FILE_SIZE=104857600  # 100MB

# Limits
MAX_CONCURRENT_TASKS=5
TASK_TIMEOUT=7200  # 2 hours
```

---

## 6. 安全设计

### 6.1 网络安全

#### 防火墙规则
```bash
# UFW 配置
ufw default deny incoming
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw enable
```

#### Nginx 安全头
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'" always;
```

### 6.2 应用安全

#### 输入验证
```python
# 文件类型白名单
ALLOWED_EXTENSIONS = {'.fasta', '.fa', '.fas', '.fna'}
ALLOWED_CONTENT_TYPES = {'text/plain', 'application/octet-stream'}

# 文件大小限制
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# 文件名清理
import re
safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
```

#### 沙箱执行
```python
# 使用 Docker-in-Docker 或 gVisor 隔离任务
docker run \
  --rm \
  --network none \
  --read-only \
  --memory=8g \
  --cpus=4 \
  -v /tmp/task:/data:ro \
  mitoflow-sandbox \
  mitoflow annotate -i /data/input.fasta
```

### 6.3 数据安全

- 传输加密: TLS 1.2+
- 存储加密: 使用 MinIO 服务器端加密
- 备份策略: 每日增量备份，每周全量备份
- 数据保留: 结果保留 30 天，日志保留 90 天

---

## 7. 性能优化

### 7.1 优化策略

#### 文件上传
- 分片上传 (multipart)
- 断点续传
- 前端压缩 (gzip)

#### 任务执行
- 异步处理 (Celery)
- 资源限制 (cgroups)
- 超时控制

#### 结果下载
- 流式传输
- 支持 Range 请求
- CDN 加速 (Phase 2)

### 7.2 缓存策略

```python
# Redis 缓存配置
CACHE_CONFIG = {
    'default': {
        'BACKEND': 'redis',
        'LOCATION': 'redis://redis:6379/1',
        'TIMEOUT': 3600,  # 1 hour
    }
}

# 缓存键命名
CACHE_KEYS = {
    'task_status': 'task:{task_id}:status',
    'task_result': 'task:{task_id}:result',
    'rate_limit': 'ratelimit:{ip}',
}
```

### 7.3 性能指标

| 指标 | 目标 | 监控方式 |
|------|------|----------|
| API 响应时间 | < 200ms | Prometheus |
| 任务完成时间 | 符合基准 | 日志分析 |
| 内存使用 | < 80% | Docker stats |
| 磁盘 I/O | < 100 MB/s | iostat |
| 并发任务 | 5-10 | Celery monitoring |

---

## 8. 监控与运维

### 8.1 日志管理

#### 日志格式
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "mitoflow-api",
  "request_id": "uuid",
  "user_ip": "xxx.xxx.xxx.xxx",
  "message": "Task started",
  "task_id": "uuid",
  "duration_ms": 150
}
```

#### 日志收集
```yaml
# docker-compose.yml logging
driver: "fluentd"
options:
  fluentd-address: localhost:24224
  tag: docker.mitoflow
```

### 8.2 监控方案

#### 关键指标
- 系统指标: CPU, 内存, 磁盘, 网络
- 应用指标: QPS, 延迟, 错误率
- 业务指标: 任务成功率, 平均处理时间

#### 工具栈
- Prometheus: 指标收集
- Grafana: 可视化
- Alertmanager: 告警
- ELK Stack: 日志分析

### 8.3 告警规则

```yaml
# alert.rules
groups:
- name: mitoflow
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
      
  - alert: TaskQueueBacklog
    expr: celery_tasks_pending > 20
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Task queue backlog detected"
```

---

## 9. 风险评估

### 9.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| HMM 搜索内存溢出 | 中 | 高 | 资源限制, 任务队列隔离 |
| 文件上传攻击 | 低 | 高 | 文件类型检查, 沙箱执行 |
| 并发过高导致崩溃 | 中 | 中 | 速率限制, 队列深度控制 |
| 数据丢失 | 低 | 高 | 定期备份, 对象存储多副本 |

### 9.2 运维风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 服务器宕机 | 低 | 高 | 监控告警, 快速恢复 |
| SSL 证书过期 | 中 | 中 | 自动续期 (certbot) |
| 磁盘空间不足 | 中 | 中 | 监控, 自动清理 |

### 9.3 回滚方案

```bash
# 快速回滚
docker-compose down
docker-compose -f docker-compose.prev.yml up -d

# 数据库回滚 (Redis)
redis-cli BGSAVE
cp /data/redis/dump.rdb /backup/
```

---

## 10. 附录

### 10.1 参考文档
- FastAPI: https://fastapi.tiangolo.com/
- Celery: https://docs.celeryq.dev/
- Streamlit: https://docs.streamlit.io/
- Docker Compose: https://docs.docker.com/compose/

### 10.2 术语表
- **HMM**: Hidden Markov Model，隐马尔可夫模型
- **BLAST**: Basic Local Alignment Search Tool
- **tRNA**: transfer RNA，转运RNA
- **rRNA**: ribosomal RNA，核糖体RNA
- **CMS**: Cytoplasmic Male Sterility，细胞质雄性不育

---

## 审批记录

| 版本 | 日期 | 作者 | 审批人 | 状态 |
|------|------|------|--------|------|
| 0.1 | 2024-01 | TBD | TBD | 草稿 |
| 1.0 | 2024-01 | TBD | TBD | 待评审 |
