import { Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import {
  Badge,
  Input,
  PageHeader,
  Panel,
  PanelHeader,
  PrimaryButton,
  Select,
  StatusMessage,
} from "../components/ui";
import { api } from "../lib/api";
import { truncateText } from "../lib/format";
import type { KnowledgeBase, SearchMode, SearchResultItem } from "../lib/types";
import { useAsync } from "../hooks/useAsync";

const MODES: Array<{ mode: SearchMode; description: string }> = [
  { mode: "hybrid", description: "向量 + 全文混合，推荐用于常规查询" },
  { mode: "vector", description: "语义检索，适合表达不精准但语义相关" },
  { mode: "fts", description: "关键词检索，适合精确词命中" },
];

type RerankMode = "default" | "on" | "off";

function formatScore(value: number | null): string {
  return value == null ? "-" : value.toFixed(4);
}

function getDisplayScore(item: SearchResultItem): number | null {
  return item.rerank_score ?? item.final_score ?? item.score;
}

function getCliffMetrics(results: SearchResultItem[]): {
  cutoffIndex: number | null;
  maxDrop: number | null;
  spread: number | null;
  ratio: number | null;
} {
  if (results.length < 2) {
    return { cutoffIndex: null, maxDrop: null, spread: null, ratio: null };
  }

  let cutoffIndex: number | null = null;
  let maxDrop = 0;

  for (let index = 0; index < results.length - 1; index += 1) {
    const current = getDisplayScore(results[index]);
    const next = getDisplayScore(results[index + 1]);
    if (current == null || next == null) {
      continue;
    }

    const drop = current - next;
    if (drop > maxDrop) {
      maxDrop = drop;
      cutoffIndex = index;
    }
  }

  if (cutoffIndex == null || maxDrop <= 0) {
    return { cutoffIndex: null, maxDrop: null, spread: null, ratio: null };
  }

  const headScore = getDisplayScore(results[0]);
  const tailItem = results[results.length - 1];
  const tailScore = tailItem ? getDisplayScore(tailItem) : null;
  if (headScore == null || tailScore == null) {
    return { cutoffIndex: null, maxDrop: null, spread: null, ratio: null };
  }

  const spread = headScore - tailScore;
  if (spread <= 0) {
    return { cutoffIndex: null, maxDrop: null, spread: null, ratio: null };
  }

  const ratio = maxDrop / spread;
  return {
    cutoffIndex: maxDrop >= spread * 0.45 ? cutoffIndex : null,
    maxDrop,
    spread,
    ratio,
  };
}

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [kbRef, setKbRef] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [rerankMode, setRerankMode] = useState<RerankMode>("default");
  const [recallTopK, setRecallTopK] = useState(20);
  const [finalTopK, setFinalTopK] = useState(5);
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const kbState = useAsync(() => api.listKnowledgeBases(), []);
  const kbs = useMemo<KnowledgeBase[]>(() => kbState.data ?? [], [kbState.data]);
  const cliffMetrics = useMemo(() => getCliffMetrics(results), [results]);
  const cliffCutoffIndex = cliffMetrics.cutoffIndex;
  const activeMode = MODES.find((item) => item.mode === mode) ?? MODES[0];

  useEffect(() => {
    const nextQuery = searchParams.get("query") ?? "";
    const nextKb = searchParams.get("kb") ?? "";
    const nextMode = searchParams.get("mode") as SearchMode | null;

    setQuery(nextQuery);
    setKbRef(nextKb);
    if (nextMode && ["vector", "fts", "hybrid"].includes(nextMode)) {
      setMode(nextMode);
    }
  }, [searchParams]);

  async function onSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const value = await api.search({
        query: query.trim(),
        kb: kbRef || undefined,
        mode,
        enable_reranker:
          rerankMode === "default" ? undefined : rerankMode === "on",
        recall_top_k: recallTopK,
        final_top_k: finalTopK,
      });
      setResults(value);
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        next.set("query", query.trim());
        if (kbRef) {
          next.set("kb", kbRef);
        } else {
          next.delete("kb");
        }
        next.set("mode", mode);
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="space-y-6 lg:space-y-7">
      <PageHeader
        eyebrow="Search"
        title="检索实验"
        description="按关键词检索知识库内容，并查看召回结果。"
      />

      <Panel className="animate-rise-in p-4 lg:p-5">
        <PanelHeader title="检索参数" description="输入查询后，按范围与策略调整召回方式。" />

        <form className="space-y-4" onSubmit={onSearch}>
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
            <div className="space-y-1.5">
              <span className="text-sm font-medium text-dify-text">查询</span>
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="输入你要验证的问题或关键词"
              />
            </div>
            <PrimaryButton size="lg" busy={searching} className="md:min-w-[128px]">
              <Search className="h-4 w-4" />
              开始检索
            </PrimaryButton>
          </div>

          <div className="rounded-xl border border-dify-border/80 bg-dify-muted/30 p-3.5 lg:p-4">
            <div className="mb-3">
              <p className="text-xs font-semibold text-dify-softText">检索范围与策略</p>
              <p className="mt-1 text-xs leading-5 text-dify-subtext">先选知识库范围，再决定使用哪种检索模式。</p>
            </div>

            <div className="grid gap-3 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:items-start">
              <div className="flex w-full flex-col gap-1">
                <p className="text-sm font-medium text-dify-text">范围（可选知识库）</p>
                <Select className="h-10 pr-10" value={kbRef} onChange={(event) => setKbRef(event.target.value)}>
                  <option value="">All Knowledge Bases</option>
                  {kbs.map((kb) => (
                    <option key={kb.id} value={kb.id}>
                      {kb.name}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="flex w-full flex-col gap-1">
                <p className="text-sm font-medium text-dify-text">检索模式</p>
                <div className="inline-flex self-start rounded-lg border border-dify-border bg-dify-surface p-1">
                  {MODES.map((item) => (
                    <button
                      key={item.mode}
                      type="button"
                      onClick={() => setMode(item.mode)}
                      className={[
                        "rounded-md px-3.5 text-[11px] font-medium tracking-[0.02em] whitespace-nowrap",
                        "transition-colors duration-150 ease-out",
                        "h-8",
                        mode === item.mode
                          ? "bg-dify-blueSoft text-dify-blue"
                          : "text-dify-subtext hover:bg-dify-muted hover:text-dify-text",
                      ].join(" ")}
                    >
                      {item.mode}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-3 rounded-lg border border-dify-border/60 bg-dify-surface/70 px-3 py-2">
              <p className="text-xs leading-5 text-dify-subtext">当前：{activeMode.mode} · {activeMode.description}</p>
            </div>
          </div>

          <details className="rounded-2xl border border-dify-border bg-dify-surface px-4 py-3">
            <summary className="cursor-pointer list-none text-sm font-medium text-dify-text">
              高级参数
              <span className="ml-2 text-xs font-normal text-dify-subtext">调整 rerank 与召回深度</span>
            </summary>
            <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <div className="space-y-4 rounded-xl border border-dify-border bg-dify-muted/45 p-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-dify-softText">排序</p>
                  <p className="mt-1 text-sm text-dify-subtext">决定是否对召回结果做二次重排。</p>
                </div>
                <Select
                  label="Rerank"
                  value={rerankMode}
                  onChange={(event) => setRerankMode(event.target.value as RerankMode)}
                >
                  <option value="default">跟随后端默认</option>
                  <option value="on">强制开启</option>
                  <option value="off">强制关闭</option>
                </Select>
                <p className="text-xs text-dify-subtext">Rerank 会对召回结果做二次排序；默认模式不会覆盖服务端配置。</p>
              </div>

              <div className="space-y-4 rounded-xl border border-dify-border bg-dify-muted/45 p-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-dify-softText">召回深度</p>
                  <p className="mt-1 text-sm text-dify-subtext">控制初始召回数量与最终保留数量。</p>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label="Recall Top K"
                    type="number"
                    min={1}
                    max={200}
                    value={recallTopK}
                    onChange={(event) => setRecallTopK(Number(event.target.value || 20))}
                  />
                  <Input
                    label="Final Top K"
                    type="number"
                    min={1}
                    max={100}
                    value={finalTopK}
                    onChange={(event) => setFinalTopK(Number(event.target.value || 5))}
                  />
                </div>
              </div>
            </div>
          </details>
        </form>
      </Panel>

      <Panel className="animate-rise-in [animation-delay:80ms]">
        <PanelHeader
          title="结果"
          description="查看召回结果，并结合分数变化判断相关性边界。"
          action={
            <div className="flex items-center gap-2">
              <Badge className="gap-1">
                <SlidersHorizontal className="h-3 w-3" />
                {mode}
              </Badge>
              <Badge
                className={
                  rerankMode === "on"
                    ? "border-dify-blue/20 bg-dify-blueSoft text-dify-blue"
                    : undefined
                }
              >
                rerank {rerankMode}
              </Badge>
            </div>
          }
        />

        <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-dify-border bg-dify-muted/50 px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-dify-softText">结果数</p>
            <p className="mt-2 text-lg font-semibold text-dify-text">{results.length}</p>
          </div>
          <div className="rounded-xl border border-dify-border bg-dify-muted/50 px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-dify-softText">排序依据</p>
            <p className="mt-2 text-lg font-semibold text-dify-text">{rerankMode === "off" ? "retrieval" : "final"}</p>
          </div>
          <div className="rounded-xl border border-dify-border bg-dify-muted/50 px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-dify-softText">最大断崖</p>
            <p className="mt-2 font-mono text-lg font-semibold text-dify-text">{formatScore(cliffMetrics.maxDrop)}</p>
          </div>
          <div className="rounded-xl border border-dify-border bg-dify-muted/50 px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-dify-softText">断崖占比</p>
            <p className="mt-2 font-mono text-lg font-semibold text-dify-text">
              {cliffMetrics.ratio != null ? `${(cliffMetrics.ratio * 100).toFixed(1)}%` : "-"}
            </p>
          </div>
        </div>

        {error ? <StatusMessage title="检索失败" description={error} /> : null}
        {!error && searching ? <StatusMessage title="正在检索，请稍候..." /> : null}
        {!error && !searching && results.length === 0 ? (
          <StatusMessage title="暂无结果" description="执行一次查询后在此查看召回片段。" />
        ) : null}

        {!error && !searching && results.length > 0 ? (
          <div className="space-y-3">
            {results.map((item, index) => {
              const isAfterCutoff = cliffCutoffIndex != null && index > cliffCutoffIndex;
              const isCutoffBoundary = cliffCutoffIndex != null && index === cliffCutoffIndex + 1;

              return (
                <article
                  key={item.chunk_id}
                  className={[
                    "animate-rise-in rounded-xl border bg-dify-surface p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)]",
                    isAfterCutoff
                      ? "border-l-4 border-dify-danger/30 bg-dify-dangerSoft/18"
                      : "border-dify-border",
                  ].join(" ")}
                  style={{ animationDelay: `${120 + index * 30}ms` }}
                >
                  {isCutoffBoundary ? (
                    <div className="mb-3 rounded-lg border border-dify-danger/20 bg-dify-dangerSoft px-3 py-2 text-xs font-medium text-dify-danger">
                      从这里开始出现明显断崖，后续结果建议重点复核。
                    </div>
                  ) : null}
                  <div className="mb-3 space-y-2">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-dify-subtext">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-dify-softText">
                        {item.kb_name}
                      </span>
                      <span aria-hidden="true" className="text-dify-softText">
                        /
                      </span>
                      <span className="max-w-full truncate font-medium text-dify-text">{item.file_name}</span>
                      <span aria-hidden="true" className="text-dify-softText">
                        /
                      </span>
                      <span>chunk #{item.chunk_index}</span>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 text-xs text-dify-subtext">
                      <Badge className="font-mono text-dify-text">retrieval {formatScore(item.retrieval_score)}</Badge>
                      {item.rerank_score != null ? (
                        <Badge className="font-mono text-dify-text">rerank {formatScore(item.rerank_score)}</Badge>
                      ) : null}
                      <Badge
                        className={[
                          "font-mono text-[11px]",
                          isAfterCutoff
                            ? "border-dify-danger/30 bg-dify-danger/15 text-dify-danger"
                            : "border-dify-blue/20 bg-dify-blue/15 text-dify-blue",
                        ].join(" ")}
                      >
                        final {formatScore(item.final_score ?? item.score)}
                      </Badge>
                      {isAfterCutoff ? (
                        <Badge className="border-dify-danger/30 bg-dify-danger/15 text-dify-danger">
                          低相关候选
                        </Badge>
                      ) : null}
                    </div>
                  </div>

                  <p className="text-sm leading-7 text-dify-text">{truncateText(item.text, 340)}</p>
                </article>
              );
            })}
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
