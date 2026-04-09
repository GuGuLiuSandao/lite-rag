import { ArrowLeft, Eye, FileText, Pencil, RefreshCcw, Save, Trash2, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  Badge,
  DangerButton,
  Input,
  Modal,
  PageHeader,
  Panel,
  PrimaryButton,
  SecondaryButton,
  StatusMessage,
  Textarea,
} from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../lib/api";
import { formatTime } from "../lib/format";
import type { FileChunk } from "../lib/types";

function renderPreviewContent(content: string) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: Array<{ type: string; content: string; level?: number }> = [];

  let paragraph: string[] = [];
  let codeLines: string[] = [];
  let inCodeBlock = false;

  function flushParagraph() {
    if (paragraph.length > 0) {
      blocks.push({ type: "paragraph", content: paragraph.join(" ") });
      paragraph = [];
    }
  }

  function flushCodeBlock() {
    if (codeLines.length > 0) {
      blocks.push({ type: "code", content: codeLines.join("\n") });
      codeLines = [];
    }
  }

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      flushParagraph();
      if (inCodeBlock) {
        flushCodeBlock();
      }
      inCodeBlock = !inCodeBlock;
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      blocks.push({
        type: "heading",
        level: headingMatch[1].length,
        content: headingMatch[2],
      });
      continue;
    }

    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      flushParagraph();
      blocks.push({ type: "bullet", content: trimmed.slice(2) });
      continue;
    }

    if (trimmed.startsWith("> ")) {
      flushParagraph();
      blocks.push({ type: "quote", content: trimmed.slice(2) });
      continue;
    }

    paragraph.push(trimmed);
  }

  flushParagraph();
  flushCodeBlock();

  return blocks.map((block, index) => {
    if (block.type === "heading") {
      const styles = {
        1: "mt-6 text-[22px] font-semibold tracking-[-0.02em] text-dify-text",
        2: "mt-5 text-[18px] font-semibold text-dify-text",
        3: "mt-4 text-[15px] font-semibold text-dify-text",
      } as const;
      const className = styles[(block.level ?? 3) as 1 | 2 | 3] ?? styles[3];
      return (
        <h3 key={`${block.type}-${index}`} className={className}>
          {block.content}
        </h3>
      );
    }

    if (block.type === "bullet") {
      return (
        <div key={`${block.type}-${index}`} className="flex items-start gap-3 py-1 text-sm leading-7 text-dify-text">
          <span className="mt-[11px] h-1.5 w-1.5 rounded-full bg-dify-blue" />
          <span>{block.content}</span>
        </div>
      );
    }

    if (block.type === "quote") {
      return (
        <blockquote
          key={`${block.type}-${index}`}
          className="my-3 border-l-2 border-dify-blue bg-dify-surface/70 px-4 py-3 text-sm leading-7 text-dify-subtext"
        >
          {block.content}
        </blockquote>
      );
    }

    if (block.type === "code") {
      return (
        <pre
          key={`${block.type}-${index}`}
          className="my-4 overflow-x-auto rounded-xl border border-dify-border bg-dify-surface px-4 py-3 font-mono text-xs leading-6 text-dify-text"
        >
          {block.content}
        </pre>
      );
    }

    return (
      <p key={`${block.type}-${index}`} className="py-1 text-sm leading-7 text-dify-text">
        {block.content}
      </p>
    );
  });
}

export function KBDetailPage() {
  const params = useParams<{ kbRef: string }>();
  const kbRef = params.kbRef ?? "";

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [savingKb, setSavingKb] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [deletingFileId, setDeletingFileId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"documents" | "settings">("documents");
  const [showUpload, setShowUpload] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTitle, setPreviewTitle] = useState("");
  const [previewContent, setPreviewContent] = useState("");
  const [previewMeta, setPreviewMeta] = useState<{ chunks: number; updatedAt: string; sourceName: string } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [chunkPreviewOpen, setChunkPreviewOpen] = useState(false);
  const [chunkPreviewTitle, setChunkPreviewTitle] = useState("");
  const [chunkItems, setChunkItems] = useState<FileChunk[]>([]);
  const [chunkLoading, setChunkLoading] = useState(false);
  const [chunkError, setChunkError] = useState<string | null>(null);

  const kbState = useAsync(() => api.getKnowledgeBase(kbRef), [kbRef]);
  const filesState = useAsync(() => api.listFiles(kbRef), [kbRef]);

  useEffect(() => {
    if (!kbState.data) {
      return;
    }
    setName(kbState.data.name);
    setDescription(kbState.data.description || "");
  }, [kbState.data?.id]);

  const files = useMemo(() => filesState.data ?? [], [filesState.data]);
  const filteredFiles = useMemo(() => {
    const value = keyword.trim().toLowerCase();
    if (!value) {
      return files;
    }

    return files.filter((file) => {
      return file.title.toLowerCase().includes(value) || file.source_name.toLowerCase().includes(value);
    });
  }, [files, keyword]);

  async function onSaveKB(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingKb(true);
    try {
      await api.updateKnowledgeBase(kbRef, {
        name: name.trim() || undefined,
        description: description.trim(),
      });
      await Promise.all([kbState.refresh(), filesState.refresh()]);
    } finally {
      setSavingKb(false);
    }
  }

  async function onUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!uploadFile) {
      return;
    }

    setUploading(true);
    try {
      await api.uploadFile({ kb: kbRef, file: uploadFile, title: uploadTitle.trim() || undefined });
      setUploadFile(null);
      setUploadTitle("");
      setShowUpload(false);
      await filesState.refresh();
    } finally {
      setUploading(false);
    }
  }

  async function onDeleteFile(fileId: string, title: string) {
    const confirmed = window.confirm(`删除文件 “${title}”？其索引数据也会被移除。`);
    if (!confirmed) {
      return;
    }
    setDeletingFileId(fileId);
    try {
      await api.deleteFile(fileId);
      await filesState.refresh();
    } finally {
      setDeletingFileId(null);
    }
  }

  async function onPreviewFile(fileId: string, title: string) {
    setPreviewOpen(true);
    setPreviewTitle(title);
    setPreviewContent("");
    setPreviewMeta(null);
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      const result = await api.getFileContent(fileId);
      setPreviewTitle(result.file.title);
      setPreviewContent(result.content);
      setPreviewMeta({
        chunks: result.file.chunk_count,
        updatedAt: result.file.updated_at,
        sourceName: result.file.source_name,
      });
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : "加载文档内容失败");
    } finally {
      setPreviewLoading(false);
    }
  }

  function onDropFile(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0] ?? null;
    if (file) {
      setUploadFile(file);
    }
  }

  async function onPreviewChunks(fileId: string, title: string) {
    setChunkPreviewOpen(true);
    setChunkPreviewTitle(title);
    setChunkItems([]);
    setChunkError(null);
    setChunkLoading(true);
    try {
      const result = await api.getFileChunks(fileId);
      setChunkItems(result);
    } catch (error) {
      setChunkError(error instanceof Error ? error.message : "加载 chunk 失败");
    } finally {
      setChunkLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link to="/" className="inline-flex items-center gap-2 text-sm text-dify-subtext hover:text-dify-text">
        <ArrowLeft className="h-4 w-4" />
        返回知识库首页
      </Link>

      <PageHeader
        eyebrow="Knowledge Detail"
        title={kbState.data?.name || "知识库详情"}
        description={kbState.data?.description || "暂无描述"}
        action={
          <div className="flex items-center gap-2">
            <PrimaryButton onClick={() => setShowUpload((value) => !value)}>
              <Upload className="h-4 w-4" />
              上传文件
            </PrimaryButton>
            <SecondaryButton
              onClick={() => Promise.all([kbState.refresh(), filesState.refresh()])}
              busy={kbState.loading || filesState.loading}
            >
              <RefreshCcw className="h-4 w-4" />
              刷新
            </SecondaryButton>
          </div>
        }
      />

      <Panel>
        <div className="flex flex-wrap items-center gap-4 font-mono text-[11px] text-dify-softText">
          <span>ref: {kbRef}</span>
          {kbState.data ? <span>updated {formatTime(kbState.data.updated_at)}</span> : null}
          <Badge>{filteredFiles.length} files</Badge>
        </div>

        <div className="mt-5 flex items-center gap-2 border-b border-dify-border">
          {[
            { key: "documents", label: "Documents" },
            { key: "settings", label: "Settings" },
          ].map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key as "documents" | "settings")}
              className={[
                "border-b-2 px-3 py-3 text-sm font-medium transition",
                activeTab === tab.key
                  ? "border-dify-blue text-dify-blue"
                  : "border-transparent text-dify-subtext hover:text-dify-text",
              ].join(" ")}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "documents" ? (
          <div className="pt-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <Input
                className="max-w-md"
                placeholder="搜索文件标题或来源名"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
              />
              <Badge>{filteredFiles.length} documents</Badge>
            </div>

            {filesState.error ? (
              <StatusMessage
                title="文件列表加载失败"
                description={filesState.error}
                action={<SecondaryButton onClick={() => filesState.refresh()}>重试</SecondaryButton>}
              />
            ) : null}

            {!filesState.error && filesState.loading ? <StatusMessage title="正在加载文件..." /> : null}

            {!filesState.error && !filesState.loading && filteredFiles.length === 0 ? (
              <StatusMessage title="暂无文件" description="上传文本文件后即可参与检索。" />
            ) : null}

            {!filesState.error && !filesState.loading && filteredFiles.length > 0 ? (
              <div className="overflow-hidden rounded-xl border border-dify-border">
                <div className="overflow-x-auto">
                  <div className="min-w-[720px]">
                    <div className="grid grid-cols-[minmax(0,1.8fr)_100px_160px_180px] gap-3 border-b border-dify-border bg-dify-muted px-4 py-3 text-xs font-medium uppercase tracking-[0.08em] text-dify-subtext">
                      <span className="sticky left-0 bg-dify-muted">Document</span>
                      <span className="hidden md:block">Chunks</span>
                      <span>Updated</span>
                      <span className="text-right">Actions</span>
                    </div>

                    {filteredFiles.map((file) => (
                      <article
                        key={file.id}
                        className="grid grid-cols-[minmax(0,1.8fr)_100px_160px_180px] items-center gap-3 border-b border-dify-border bg-dify-surface px-4 py-3 last:border-b-0"
                      >
                        <div className="sticky left-0 min-w-0 bg-dify-surface">
                          <p className="truncate text-sm font-medium text-dify-text" title={file.title}>
                            {file.title}
                          </p>
                          <p className="truncate text-xs text-dify-subtext" title={file.source_name}>
                            {file.source_name}
                          </p>
                        </div>
                        <div className="hidden text-sm text-dify-subtext md:block">{file.chunk_count}</div>
                        <div className="font-mono text-[11px] text-dify-softText">{formatTime(file.updated_at)}</div>
                        <div className="flex justify-end gap-2">
                          <SecondaryButton type="button" onClick={() => onPreviewChunks(file.id, file.title)}>
                            Chunks
                          </SecondaryButton>
                          <SecondaryButton type="button" onClick={() => onPreviewFile(file.id, file.title)}>
                            <Eye className="h-4 w-4" />
                            查看
                          </SecondaryButton>
                          <DangerButton busy={deletingFileId === file.id} onClick={() => onDeleteFile(file.id, file.title)}>
                            <Trash2 className="h-4 w-4" />
                          </DangerButton>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>

                <div className="border-t border-dify-border bg-dify-muted/60 px-4 py-2 text-xs text-dify-softText md:hidden">
                  左右滑动可查看更多列
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="pt-5">
            <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
              <div className="rounded-xl bg-dify-muted p-4 text-sm text-dify-subtext">
                <div className="mb-3 flex items-center gap-2">
                  <Pencil className="h-4 w-4 text-dify-blue" />
                  <span className="font-medium text-dify-text">基础设置</span>
                </div>
                <div className="space-y-2">
                  <div>
                    <div className="mb-1 text-xs uppercase tracking-[0.12em] text-dify-softText">Reference</div>
                    <div className="break-all font-mono text-xs text-dify-text">{kbRef}</div>
                  </div>
                  {kbState.data ? (
                    <>
                      <div>创建时间：{formatTime(kbState.data.created_at)}</div>
                      <div>更新时间：{formatTime(kbState.data.updated_at)}</div>
                    </>
                  ) : null}
                </div>
              </div>

              <div>
                {kbState.error ? <StatusMessage title="加载知识库失败" description={kbState.error} /> : null}

                {!kbState.error ? (
                  <form className="space-y-4" onSubmit={onSaveKB}>
                    <Input
                      label="名称"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      placeholder="知识库名称"
                    />
                    <Textarea
                      label="描述"
                      value={description}
                      onChange={(event) => setDescription(event.target.value)}
                      placeholder="可选描述"
                    />
                    <div className="flex justify-end">
                      <PrimaryButton type="submit" busy={savingKb}>
                        <Save className="h-4 w-4" />
                        保存修改
                      </PrimaryButton>
                    </div>
                  </form>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </Panel>

      <Modal
        open={showUpload}
        title="上传文件"
        onClose={() => {
          if (!uploading) {
            setShowUpload(false);
            setDragActive(false);
          }
        }}
      >
        <form className="space-y-5" onSubmit={onUpload}>
          <div className="space-y-1.5">
            <p className="text-sm text-dify-text">将本地文本文件导入当前知识库。</p>
            <p className="text-sm text-dify-subtext">仅支持本地文本文件，暂不支持 OCR、PDF 解析、图片解析。</p>
          </div>

          <div
            className={[
              "rounded-xl border border-dashed p-5 transition",
              dragActive
                ? "border-dify-blue bg-dify-blue/5"
                : "border-dify-border bg-dify-muted",
            ].join(" ")}
            onDragEnter={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              if (event.currentTarget === event.target) {
                setDragActive(false);
              }
            }}
            onDrop={onDropFile}
          >
            <div className="space-y-3 text-center">
              <div
                className={[
                  "mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-dify-surface text-dify-blue shadow-card transition",
                  dragActive ? "-translate-y-0.5" : "",
                ].join(" ")}
              >
                <Upload className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-medium text-dify-text">拖拽文件到此处，或选择文件</p>
                <p className="mt-1 text-xs text-dify-subtext">上传后会进入当前知识库并参与检索。</p>
              </div>
              <div className="flex justify-center">
                <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dify-border bg-dify-surface px-3.5 py-2 text-sm font-medium text-dify-text transition hover:border-dify-borderStrong hover:bg-dify-muted">
                  <Upload className="h-4 w-4" />
                  选择文件
                  <input
                    type="file"
                    className="hidden"
                    onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                  />
                </label>
              </div>
            </div>
          </div>

          <Input
            label="标题覆盖"
            placeholder="可选：自定义显示名"
            value={uploadTitle}
            onChange={(event) => setUploadTitle(event.target.value)}
          />

          <div className="rounded-xl border border-dify-border bg-dify-muted p-4">
            {uploadFile ? (
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-dify-text">{uploadFile.name}</p>
                  <p className="mt-1 text-xs text-dify-subtext">
                    {(uploadFile.size / 1024).toFixed(1)} KB · {uploading ? "上传中" : "待上传"}
                  </p>
                </div>
                <SecondaryButton
                  type="button"
                  onClick={() => setUploadFile(null)}
                  disabled={uploading}
                >
                  移除
                </SecondaryButton>
              </div>
            ) : (
              <p className="text-sm text-dify-subtext">请先选择要上传的文件。</p>
            )}
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-dify-border pt-4">
            <p className="text-xs text-dify-subtext">当前知识库：{kbState.data?.name || kbRef}</p>
            <div className="flex gap-2">
              <SecondaryButton type="button" onClick={() => setShowUpload(false)} disabled={uploading}>
                取消
              </SecondaryButton>
              <PrimaryButton busy={uploading} disabled={!uploadFile}>
                开始上传
              </PrimaryButton>
            </div>
          </div>
        </form>
      </Modal>

      <Modal open={previewOpen} title={previewTitle || "文档预览"} onClose={() => setPreviewOpen(false)}>
        <div className="space-y-4">
          <div className="rounded-xl border border-dify-border bg-dify-muted px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-dify-surface text-dify-blue shadow-card">
                  <FileText className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-dify-text">{previewTitle || "文档预览"}</p>
                  <p className="truncate text-xs text-dify-subtext">
                    {previewMeta
                      ? `${previewMeta.sourceName} · ${previewMeta.chunks} chunks · updated ${formatTime(previewMeta.updatedAt)}`
                      : "仅预览当前已入库的文本内容"}
                  </p>
                </div>
              </div>
              <Badge>Text Preview</Badge>
            </div>
          </div>

          {previewError ? <StatusMessage title="加载失败" description={previewError} /> : null}
          {!previewError && previewLoading ? <StatusMessage title="正在加载文档内容..." /> : null}
          {!previewError && !previewLoading ? (
            <div className="max-h-[60vh] overflow-auto rounded-xl border border-dify-border bg-dify-muted p-4">
              <div className="mx-auto max-w-4xl">
                {previewContent ? (
                  <div className="space-y-1">{renderPreviewContent(previewContent)}</div>
                ) : (
                  <p className="text-sm text-dify-subtext">文档内容为空</p>
                )}
              </div>
            </div>
          ) : null}

          <div className="flex justify-end border-t border-dify-border pt-4">
            <SecondaryButton onClick={() => setPreviewOpen(false)}>关闭</SecondaryButton>
          </div>
        </div>
      </Modal>

      <Modal open={chunkPreviewOpen} title={`${chunkPreviewTitle || "文档"} · Chunks`} onClose={() => setChunkPreviewOpen(false)}>
        <div className="space-y-4">
          <div className="rounded-xl border border-dify-border bg-dify-muted px-4 py-3 text-sm text-dify-subtext">
            展示当前文件的分块结果。现在 chunk 已同时保存到 LanceDB 和 SQLite metadata，便于检索与前端查看。
          </div>

          {chunkError ? <StatusMessage title="加载失败" description={chunkError} /> : null}
          {!chunkError && chunkLoading ? <StatusMessage title="正在加载 chunks..." /> : null}
          {!chunkError && !chunkLoading ? (
            <div className="max-h-[60vh] space-y-3 overflow-auto pr-1">
              {chunkItems.length > 0 ? (
                chunkItems.map((chunk) => (
                  <article key={chunk.id} className="rounded-xl border border-dify-border bg-dify-muted p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-dify-subtext">
                      <Badge>chunk #{chunk.chunk_index}</Badge>
                      <Badge>{chunk.text.length} chars</Badge>
                    </div>
                    <p className="whitespace-pre-wrap break-words text-sm leading-6 text-dify-text">{chunk.text}</p>
                  </article>
                ))
              ) : (
                <StatusMessage title="暂无 chunk" description="当前文件还没有可展示的分块内容。" />
              )}
            </div>
          ) : null}

          <div className="flex justify-end border-t border-dify-border pt-4">
            <SecondaryButton onClick={() => setChunkPreviewOpen(false)}>关闭</SecondaryButton>
          </div>
        </div>
      </Modal>
    </div>
  );
}
