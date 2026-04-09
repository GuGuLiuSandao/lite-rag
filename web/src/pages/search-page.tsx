import { Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import {
  Badge,
  Input,
  PageHeader,
  Panel,
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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Search"
        title="检索实验"
        description="按关键词检索知识库内容，并查看召回结果。"
      />

      <Panel className="animate-rise-in">
        <p className="mb-4 max-w-3xl text-sm text-dify-subtext">
          在同一界面切换 vector / fts / hybrid，快速验证知识覆盖与召回质量。
        </p>

        <form className="space-y-4" onSubmit={onSearch}>
          <Input
            label="查询"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="输入你要验证的问题或关键词"
          />

          <div className="grid gap-4 md:grid-cols-2">
            <Select label="范围（可选知识库）" value={kbRef} onChange={(event) => setKbRef(event.target.value)}>
              <option value="">All Knowledge Bases</option>
              {kbs.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name}
                </option>
              ))}
            </Select>

            <div className="space-y-1.5">
              <span className="text-sm font-medium text-dify-text">检索模式</span>
              <div className="grid gap-2 sm:grid-cols-3">
                {MODES.map((item) => (
                  <button
                    key={item.mode}
                    type="button"
                    onClick={() => setMode(item.mode)}
                    className={[
                      "rounded-xl border px-3 py-2 text-left text-xs transition",
                      mode === item.mode
                        ? "border-dify-blue bg-dify-blueSoft text-dify-blue"
                        : "border-dify-border bg-dify-surface text-dify-subtext hover:border-dify-borderStrong",
                    ].join(" ")}
                  >
                    <p className="mb-0.5 font-semibold uppercase tracking-[0.12em]">{item.mode}</p>
                    <p className="text-[11px] leading-relaxed text-dify-subtext">{item.description}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Select
              label="Rerank"
              value={rerankMode}
              onChange={(event) => setRerankMode(event.target.value as RerankMode)}
            >
              <option value="default">跟随后端默认</option>
              <option value="on">强制开启</option>
              <option value="off">强制关闭</option>
            </Select>
          </div>

          <p className="-mt-1 text-xs text-dify-subtext">
            Rerank 会对召回结果做二次排序。跟随后端默认时，不主动覆盖服务端配置。
          </p>

          <div className="grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
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
            <PrimaryButton busy={searching} className="h-[42px]">
              <Search className="h-4 w-4" />
              开始检索
            </PrimaryButton>
          </div>
        </form>
      </Panel>

      <Panel className="animate-rise-in [animation-delay:80ms]">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-dify-text">结果</h2>
            <p className="text-sm text-dify-subtext">
              共 {results.length} 条结果 · 排序依据 {rerankMode === "off" ? "retrieval" : "final"}
            </p>
            {cliffMetrics.maxDrop != null && cliffMetrics.spread != null && cliffMetrics.ratio != null ? (
              <p className="mt-1 text-xs text-dify-subtext">
                最大断崖 {formatScore(cliffMetrics.maxDrop)} / 总跨度 {formatScore(cliffMetrics.spread)} /
                占比 {(cliffMetrics.ratio * 100).toFixed(1)}% · 阈值 45%
              </p>
            ) : null}
          </div>
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
                    "animate-rise-in rounded-xl border bg-dify-surface p-4",
                    isAfterCutoff
                      ? "border-dify-danger/20 bg-dify-dangerSoft/40"
                      : "border-dify-border",
                  ].join(" ")}
                  style={{ animationDelay: `${120 + index * 30}ms` }}
                >
                  {isCutoffBoundary ? (
                    <div className="mb-3 rounded-lg border border-dify-danger/20 bg-dify-dangerSoft px-3 py-2 text-xs font-medium text-dify-danger">
                      从这里开始出现断崖下跌，后续结果大概率是垃圾候选。
                    </div>
                  ) : null}
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-dify-subtext">
                    <Badge>{item.kb_name}</Badge>
                    <Badge>{item.file_name}</Badge>
                    <Badge>chunk #{item.chunk_index}</Badge>
                    <Badge
                        className={
                          isAfterCutoff
                          ? "border-dify-danger/20 bg-dify-dangerSoft text-dify-danger"
                          : "border-dify-blue/20 bg-dify-blueSoft text-dify-blue"
                        }
                    >
                      final {formatScore(item.final_score ?? item.score)}
                    </Badge>
                    <Badge>retrieval {formatScore(item.retrieval_score)}</Badge>
                    {isAfterCutoff ? (
                      <Badge className="border-dify-danger/20 bg-dify-dangerSoft text-dify-danger">
                        garbage candidate
                      </Badge>
                    ) : null}
                  </div>
                  <p className="text-sm leading-6 text-dify-text">{truncateText(item.text, 340)}</p>
                </article>
              );
            })}
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
