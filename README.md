# lite-RAG

本地版、serverless、轻量级 RAG。

支持：
- 知识库 CRUD
- 知识库中文件 CRUD
- 检索模式：`vector` / `fts` / `hybrid`
- 本地 LanceDB（chunk/vector/fts）+ SQLite（KB/文件元数据）
- 默认开启 reranker，可通过环境变量或检索请求开关关闭；依赖 `FlagEmbedding` + `transformers<5`
- skill 封装

暂不支持：
- OCR
- PDF / 图片解析

## 目录

- `src/lite_rag/`：核心实现
- `skill/local-lite-rag/`：可直接复用的 skill 包装

## 安装

```bash
pip install -e .
```

## 启动 API 服务

新增了 FastAPI 常驻服务入口：

```bash
lite-rag-api
```

默认监听：

```txt
http://127.0.0.1:8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

### CORS / 前端联调

为了便于本地前端联调，API 已启用 CORS。可通过环境变量限制来源：

```env
LITE_RAG_API_ALLOW_ORIGINS=http://127.0.0.1:5173
```

默认值为 `*`（仅建议本地开发使用）。

常用接口示例：

```bash
curl -X POST http://127.0.0.1:8000/kb \
  -H "Content-Type: application/json" \
  -d '{"name":"产品文档","description":"内部资料"}'

curl -X POST http://127.0.0.1:8000/file \
  -H "Content-Type: application/json" \
  -d '{"kb":"产品文档","path":"./demo.md"}'

curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"kb":"产品文档","query":"怎么做混合检索","mode":"hybrid","enable_reranker":true}'
```

上传文件（multipart）：

```bash
curl -X POST http://127.0.0.1:8000/file/upload \
  -F "kb=产品文档" \
  -F "file=@./demo.md" \
  -F "title=演示文档"
```

API 返回格式与 CLI 保持一致：

- 成功：`{"ok": true, "result": ...}`
- 失败：`{"ok": false, "error": "..."}`

## 配置

复制：

```bash
cp skill/local-lite-rag/.env.example skill/local-lite-rag/.env
```

可选配置（不配会默认使用仓库根目录下 `/.lite-rag`）：

```env
LITE_RAG_STORAGE_ROOT=/absolute/path/to/local-lite-rag-data
LITE_RAG_ENABLE_RERANKER=true
```

## 直接 CLI 用法

```bash
lite-rag kb create --name "产品文档"
lite-rag kb list
lite-rag file add --kb "产品文档" --path ./demo.md
lite-rag file list --kb "产品文档"
lite-rag search --kb "产品文档" --query "怎么做混合检索" --mode hybrid
```

## 前端 Workbench

仓库内置了一个本地管理前端（Vite + React + TypeScript + Tailwind）：

- 路径：`web/`
- 页面：
  - 知识库列表（创建/删除）
  - 知识库详情（元数据编辑、文件上传/删除）
  - 检索实验页（`vector` / `fts` / `hybrid` + rerank 跟随后端/强制开关）

启动方式：

```bash
cd web
cp .env.example .env
npm install
npm run dev
```

默认访问：`http://127.0.0.1:5173`

如需修改 API 地址：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

实现说明见：`docs/frontend-architecture.md`

### 一键启动前后端

仓库根目录提供了一个本地开发启动脚本：

```bash
sh start-dev.sh
```

脚本会：

- 启动后端 API：`http://127.0.0.1:8000`
- 自动补齐 `web/.env`（如果不存在）
- 首次启动时自动安装 `web/` 依赖（存在 `node_modules` 时跳过）
- 自动释放 `8000` / `5173` 端口上已有的旧进程
- 启动前端开发服务：`http://127.0.0.1:5173`

按 `Ctrl+C` 可同时停止前后端。

如需自定义监听地址或端口，可在启动前设置：

```bash
LITE_RAG_API_HOST=0.0.0.0 LITE_RAG_API_PORT=8000 VITE_HOST=0.0.0.0 VITE_PORT=5173 sh start-dev.sh
```

## skill 用法

见 `skill/local-lite-rag/SKILL.md`。
