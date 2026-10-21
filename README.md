# lite-RAG

本地版、serverless、轻量级 RAG。

支持：
- 知识库 CRUD
- 知识库中文件 CRUD
- 检索模式：`vector` / `fts` / `hybrid`
- 本地 LanceDB（chunk/vector/fts）+ SQLite（KB/文件元数据）
- 向量化与重排分别支持本地模型或 HTTP API，默认仍为本地 BGE 模型
- 默认开启 reranker，可通过环境变量或检索请求开关关闭；本地推理依赖通过 `[local]` 安装
- skill 封装

暂不支持：
- OCR
- PDF / 图片解析

## 目录

- `src/lite_rag/`：核心实现
- `skill/local-lite-rag/`：可直接复用的 skill 包装

## 安装

使用本地模型（保留原有运行方式）：

```bash
pip install -e '.[local]'
```

仅使用 HTTP 模型服务时，无需安装 Sentence Transformers、FlagEmbedding 和本地推理依赖：

```bash
pip install -e .
```

已有环境中的本地依赖不会自动卸载。

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

CLI 和 API 都会自动读取仓库根目录的 `.env`，系统环境变量优先。首次配置可复制：

```bash
cp .env.example .env
```

Skill 包装还会先读取自身目录下的 `.env`，其值优先于仓库 `.env`：

```bash
cp skill/local-lite-rag/.env.example skill/local-lite-rag/.env
```

可选配置（不配会默认使用仓库根目录下 `/.lite-rag`）：

```env
LITE_RAG_STORAGE_ROOT=/absolute/path/to/local-lite-rag-data
LITE_RAG_ENABLE_RERANKER=true
```

### 通过通用 HTTP API 调用模型

向量化与重排可以独立选择 `local` 或 `http`，也可以接入不同服务。URL 填完整接口地址，程序不会自动拼接 `/v1` 或路径：

```env
LITE_RAG_EMBED_PROVIDER=http
LITE_RAG_EMBED_MODEL=your-embedding-model
LITE_RAG_EMBED_API_URL=http://127.0.0.1:9000/v1/embeddings
LITE_RAG_EMBED_API_KEY=
LITE_RAG_EMBED_BATCH_SIZE=32

LITE_RAG_ENABLE_RERANKER=true
LITE_RAG_RERANK_PROVIDER=http
LITE_RAG_RERANK_MODEL=your-reranker-model
LITE_RAG_RERANK_API_URL=http://127.0.0.1:9000/v1/rerank
LITE_RAG_RERANK_API_KEY=

LITE_RAG_MODEL_API_TIMEOUT=30
```

有密钥时使用 `Authorization: Bearer <key>`；无密钥时不发送认证头。改配置后需重启 API，CLI 每次运行读取配置。

向量化接口协议：

```json
请求：{"model":"your-embedding-model","input":["文本一","文本二"],"encoding_format":"float"}
响应：{"data":[{"index":0,"embedding":[0.1,0.2]},{"index":1,"embedding":[0.3,0.4]}]}
```

重排接口协议：

```json
请求：{"model":"your-reranker-model","query":"问题","documents":["片段一","片段二"],"top_n":2}
响应：{"results":[{"index":1,"relevance_score":0.9},{"index":0,"relevance_score":0.2}]}
```

响应必须包含每条输入的结果和从 0 开始的 `index`，返回顺序不限。向量化会分批请求并校验数量、维度和数值；重排失败会记录警告，回退到原始检索结果，HTTP 模式下会在下次查询重试。其他协议的服务需要适配，不能仅凭支持 HTTP 就直接接入。

如果只需要远程向量化，可设置 `LITE_RAG_ENABLE_RERANKER=false`，无需配置重排 API。

### 更换向量模型与已有数据

新建索引会记录向量模型的 provider、模型名与接口地址的签名，阻止其他配置读写该索引的向量，即使维度相同也会拦截。全文检索仍可使用已有索引。

更换向量模型时，设置新的 `LITE_RAG_STORAGE_ROOT` 并重新导入文件。仅更换重排模型或 API 密钥不需要重建索引。当前不提供原地自动重建命令。

历史索引没有模型签名，为兼容原有数据，仅允许默认的本地 `BAAI/bge-m3` 使用它。如果历史数据实际使用了其他模型，应使用新目录重新导入，避免语义空间混用。

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
