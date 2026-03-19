# 前后端可执行开发清单

## 当前已完成

### 后端服务化
- 已新增 FastAPI 服务骨架
- 已新增 SQLite 正式数据层
- 已新增 `/api/ingest` 批量入库接口，可直接接收现有 `HTTPUploader` 的 gzip 批量数据
- 查询接口已从“直接读 CSV”切到“优先读 SQLite 数据库”
- 数据库为空时，会自动从 `experiments` 下最新的 `metrics/events` CSV 引导初始化

### 前端页面
- 已落地三页：
  - `/` 全局大盘
  - `/devices/:deviceId` 设备详情
  - `/events` 事件中心
- 已接通数据库查询 API
- 已补 A/J/P/D 风险分解图
- 已补告警确认与静默操作入口

### 告警闭环
- 已支持规则：
  - 设备不可用
  - 高风险
  - 高温
- 已支持状态：
  - `open`
  - `acknowledged`
  - `silenced`
  - `resolved`

### Outbox 接入
- 大盘已能读取最新 `*outbox.db` 的 `pending/dead` 数量
- 后端已可作为 outbox 上传目标

## 现阶段推荐运行方式

### 1. 启动后端
```powershell
.\.venv\Scripts\python -m uvicorn backend.app.main:app --reload --port 8001
```

### 2. 启动前端
```powershell
cd frontend
npm run dev
```

### 3. 让采样链路接入正式后端
```powershell
.\.venv\Scripts\python demo\havfs_experiment.py --mode havfs --device cpu --remote-endpoint http://127.0.0.1:8001/api/ingest
```

## 接口清单

### 查询接口
- `GET /health`
- `GET /api/devices`
- `GET /api/metrics/realtime`
- `GET /api/metrics/history?device_id=cpu0&limit=120`
- `GET /api/events`
- `GET /api/alerts`
- `GET /api/alerts/trends`
- `GET /api/alerts/rules`
- `GET /api/scheduler/config`
- `GET /api/dashboard/overview`
- `GET /api/dashboard/risk-heatmap`

### 写接口
- `POST /api/ingest`
- `POST /api/alerts/{id}/ack`
- `POST /api/alerts/{id}/silence`
- `PUT /api/alerts/rules/{rule_key}`

## 下一轮建议

### P1：进一步产品化
- 增加设备元数据表
- 增加站点维度与多设备分组
- 增加登录与权限控制

### P1：进一步可视化
- 将当前风险分布图升级为真正热力图
- 增加告警趋势图
- 增加设备状态时间轴

### P2：进一步平台化
- 数据库从 SQLite 升级到 TimescaleDB / PostgreSQL
- 后端增加规则管理接口
- 前端增加规则配置页和告警处理记录页
