import { Link } from "react-router-dom";
import { ArrowRight, FolderPlus, RefreshCcw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import {
  Badge,
  DangerButton,
  Input,
  PageHeader,
  Panel,
  PanelHeader,
  PrimaryButton,
  SecondaryButton,
  StatusMessage,
  Textarea,
} from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../lib/api";
import { formatTime } from "../lib/format";

export function KBListPage() {
  const [keyword, setKeyword] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const { data, loading, error, refresh } = useAsync(() => api.listKnowledgeBases(), []);
  const kbs = useMemo(() => data ?? [], [data]);
  const filteredKbs = useMemo(() => {
    const value = keyword.trim().toLowerCase();
    if (!value) {
      return kbs;
    }

    return kbs.filter((kb) => {
      return kb.name.toLowerCase().includes(value) || kb.description.toLowerCase().includes(value);
    });
  }, [kbs, keyword]);

  async function onCreateKB(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      return;
    }

    setSubmitting(true);
    try {
      await api.createKnowledgeBase({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setName("");
      setDescription("");
      setShowCreate(false);
      await refresh();
    } finally {
      setSubmitting(false);
    }
  }

  async function onDeleteKB(kbRef: string, kbName: string) {
    const confirmed = window.confirm(`删除知识库 “${kbName}” 及其所有文件？此操作不可恢复。`);
    if (!confirmed) {
      return;
    }

    setDeletingId(kbRef);
    try {
      await api.deleteKnowledgeBase(kbRef);
      await refresh();
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-6 lg:space-y-7">
      <PageHeader
        eyebrow="Knowledge"
        title="知识库"
        description="管理知识库并进入详情查看文档与检索数据。"
        action={
          <div className="flex items-center gap-2">
            <SecondaryButton onClick={() => refresh()} busy={loading}>
              <RefreshCcw className="h-4 w-4" />
              刷新
            </SecondaryButton>
            <PrimaryButton onClick={() => setShowCreate(true)}>
              <FolderPlus className="h-4 w-4" />
              新建知识库
            </PrimaryButton>
          </div>
        }
      />

      <Panel className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Input
            className="max-w-md"
            placeholder="搜索知识库名称或描述"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
          <Badge>{filteredKbs.length} results</Badge>
        </div>
      </Panel>

      <Panel className="p-4 lg:p-5">
        <PanelHeader title="知识库列表" description="浏览、搜索并进入知识库详情。" action={<Badge>{filteredKbs.length} results</Badge>} />
        {error ? (
          <StatusMessage
            title="加载失败"
            description={error}
            action={<SecondaryButton onClick={() => refresh()}>重试</SecondaryButton>}
          />
        ) : null}

        {!error && loading ? <StatusMessage title="正在加载知识库..." description="请稍候" /> : null}

        {!error && !loading && filteredKbs.length === 0 ? (
          <StatusMessage title="暂无知识库" description="先创建一个知识库开始使用" />
        ) : null}

        {!error && !loading && filteredKbs.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredKbs.map((kb) => (
              <article
                key={kb.id}
                className="rounded-xl border border-dify-border bg-dify-surface/90 p-4 transition-colors duration-150 hover:border-dify-borderStrong hover:bg-dify-muted/45"
              >
                <div className="flex h-full flex-col justify-between gap-4">
                  <div className="space-y-2">
                    <Link
                      to={`/kbs/${encodeURIComponent(kb.id)}`}
                      className="inline-block rounded-sm text-[15px] font-semibold text-dify-text underline-offset-4 transition hover:text-dify-blue hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-dify-blue/30"
                    >
                      {kb.name}
                    </Link>
                    <p className="line-clamp-2 min-h-[40px] text-sm leading-5 text-dify-subtext">
                      {kb.description || "暂无描述"}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 text-[12px] text-dify-softText">
                      <span className="font-medium">Knowledge Base</span>
                      <span>·</span>
                      <span className="font-mono">updated {formatTime(kb.updated_at)}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-3">
                    <div className="inline-flex items-center gap-2">
                    <Link to={`/kbs/${encodeURIComponent(kb.id)}`}>
                      <PrimaryButton size="sm" className="shadow-none">
                        进入详情
                        <ArrowRight className="h-4 w-4" />
                      </PrimaryButton>
                    </Link>
                    <DangerButton size="icon" busy={deletingId === kb.id} onClick={() => onDeleteKB(kb.id, kb.name)}>
                      <Trash2 className="h-4 w-4" />
                    </DangerButton>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </Panel>

      {showCreate ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-dify-overlay/40 p-4">
          <div className="w-full max-w-xl rounded-2xl border border-dify-border bg-dify-surface p-5 shadow-card">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-dify-text">新建知识库</h2>
                <p className="mt-1 text-sm text-dify-subtext">保持轻量，只填写必要信息。</p>
              </div>
              <SecondaryButton onClick={() => setShowCreate(false)}>取消</SecondaryButton>
            </div>

            <form className="space-y-4" onSubmit={onCreateKB}>
              <Input
                label="名称"
                placeholder="例如：产品文档"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <Textarea
                label="描述"
                placeholder="简要描述该知识库用途（可选）"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
              <div className="flex justify-end gap-2">
                <SecondaryButton type="button" onClick={() => setShowCreate(false)}>
                  取消
                </SecondaryButton>
                <PrimaryButton busy={submitting}>
                  <FolderPlus className="h-4 w-4" />
                  创建
                </PrimaryButton>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
