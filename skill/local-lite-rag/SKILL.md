---
name: local-lite-rag
description: "本地版 serverless 轻量级 RAG：支持知识库 CRUD、文件 CRUD、向量检索、倒排检索、混合检索。"
---

# Local Lite RAG

这是一个本地 skill，基于 Python + LanceDB，适合单机、本地目录、serverless 场景。

## 特性

- 知识库 CRUD
- 文件 CRUD
- 检索模式：`vector` / `fts` / `hybrid`
- 本地 LanceDB 向量库 + 全文倒排索引（chunk/vector/fts）
- SQLite 存储知识库与文件元数据
- 可选 reranker
- 数据落盘到 `.env` 指定目录，避免 skill 本体膨胀

## 限制

- 暂不支持 OCR
- 暂不支持 PDF、图片、扫描件解析
- 目前只支持纯文本类文件

## 前置配置

先复制配置文件：

```bash
cp skill/local-lite-rag/.env.example skill/local-lite-rag/.env
```

`LITE_RAG_STORAGE_ROOT` 可选，不配置时默认使用仓库根目录下 `/.lite-rag`。如需自定义，再填写：

```env
LITE_RAG_STORAGE_ROOT=/absolute/path/to/local-lite-rag-data
```

## 安装

```bash
pip install -e .
```

## 用法

### 1. 知识库 CRUD

```bash
python -X utf8 skill/local-lite-rag/tool.py kb create --name "产品文档" --description "本地产品知识库"
python -X utf8 skill/local-lite-rag/tool.py kb list
python -X utf8 skill/local-lite-rag/tool.py kb get --kb "产品文档"
python -X utf8 skill/local-lite-rag/tool.py kb update --kb "产品文档" --description "更新后的描述"
python -X utf8 skill/local-lite-rag/tool.py kb delete --kb "产品文档"
```

### 2. 文件 CRUD

```bash
python -X utf8 skill/local-lite-rag/tool.py file add --kb "产品文档" --path "./demo.md"
python -X utf8 skill/local-lite-rag/tool.py file list --kb "产品文档"
python -X utf8 skill/local-lite-rag/tool.py file get --file-id "<file_id>"
python -X utf8 skill/local-lite-rag/tool.py file update --file-id "<file_id>" --path "./demo-v2.md"
python -X utf8 skill/local-lite-rag/tool.py file delete --file-id "<file_id>"
```

### 3. 检索

```bash
python -X utf8 skill/local-lite-rag/tool.py search --kb "产品文档" --query "怎么做混合检索" --mode hybrid
python -X utf8 skill/local-lite-rag/tool.py search --kb "产品文档" --query "embedding 模型是什么" --mode vector
python -X utf8 skill/local-lite-rag/tool.py search --kb "产品文档" --query "倒排索引" --mode fts
```

## 命令说明

- `kb create --name <name> [--description <text>]`
- `kb list`
- `kb get --kb <kb_id_or_name>`
- `kb update --kb <kb_id_or_name> [--name <new_name>] [--description <text>]`
- `kb delete --kb <kb_id_or_name>`
- `file add --kb <kb_id_or_name> --path <file_path> [--title <title>]`
- `file list [--kb <kb_id_or_name>]`
- `file get --file-id <file_id>`
- `file update --file-id <file_id> [--path <file_path>] [--title <title>]`
- `file delete --file-id <file_id>`
- `search [--kb <kb_id_or_name>] --query <query> [--mode vector|fts|hybrid]`

## 输出

所有命令统一输出 JSON：

```json
{
  "ok": true,
  "result": {}
}
```
