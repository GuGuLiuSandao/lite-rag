import { Activity, BookCopy, Database, Eye, FileText, Search as SearchIcon, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";

import { ChartContainer, ChartTooltipContent, type ChartConfig } from "../components/chart";
import { Badge, Modal, PageHeader, Panel, SecondaryButton, Select, StatusMessage } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../lib/api";
import { formatTime, truncateText } from "../lib/format";
import type { DashboardChunkHit, DashboardTrendPoint, FileChunk, KBFile, KnowledgeBase } from "../lib/types";

function StatCard({
  title,
  value,
  detail,
  icon: Icon,
}: {
  title: string;
  value: number;
  detail: string;
  icon: typeof Database;
}) {
  return (
    <Panel className="animate-rise-in p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-dify-subtext">{title}</p>
          <p className="mt-2 text-3xl font-semibold tracking-[-0.02em] text-dify-text">{value}</p>
          <p className="mt-2 text-xs leading-5 text-dify-softText">{detail}</p>
        </div>
        <div
          className="flex h-11 w-11 items-center justify-center rounded-2xl border border-dify-accent/25 text-dify-accent shadow-[inset_0_1px_0_rgba(255,255,255,0.24)]"
          style={{ backgroundImage: "var(--gradient-brand)" }}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </Panel>
  );
}

function TrendLineChart({ points }: { points: DashboardTrendPoint[] }) {
  if (points.length === 0) {
    return null;
  }
  const chartConfig = {
    queries: {
      label: "查询次数",
      color: "rgb(var(--color-chart-1))",
    },
  } satisfies ChartConfig;

  const total = points.reduce((sum, point) => sum + point.query_count, 0);
  const delta = points.length >= 2 ? points[points.length - 1]!.query_count - points[0]!.query_count : 0;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
        <div className="rounded-2xl border border-dify-border bg-dify-surface p-4">
          <ChartContainer config={chartConfig} className="h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={points} margin={{ left: 8, right: 8, top: 12, bottom: 8 }} accessibilityLayer>
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={10}
                  minTickGap={24}
                  tickFormatter={(value: string) => value.slice(5)}
                />
                <Tooltip
                  cursor={false}
                  content={({ active, payload, label }) => (
                    <ChartTooltipContent
                      active={active}
                      payload={payload?.map((item) => ({
                        value: Array.isArray(item.value) ? item.value.join(", ") : item.value == null ? undefined : String(item.value),
                        name: "查询次数",
                        color: "rgb(var(--color-chart-1))",
                      }))}
                      label={label == null ? undefined : String(label)}
                    />
                  )}
                />
                <Line
                  type="natural"
                  dataKey="query_count"
                  name="查询次数"
                  stroke="var(--color-queries)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "rgb(var(--color-chart-1))", stroke: "rgb(var(--color-surface))", strokeWidth: 2 }}
                  activeDot={{ r: 4, fill: "rgb(var(--color-chart-1))", stroke: "rgb(var(--color-surface))", strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartContainer>
        </div>

        <div className="flex flex-col justify-between rounded-2xl border border-dify-border bg-dify-muted/40 p-4">
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-dify-softText">7 天总查询量</p>
            <p className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-dify-text">{total}</p>
          </div>
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-dify-border bg-dify-surface px-3 py-1.5 text-xs text-dify-subtext">
              <TrendingUp className="h-3.5 w-3.5 text-dify-blue" />
              {delta >= 0 ? `较首日 +${delta}` : `较首日 ${delta}`}
            </div>
            <div className="space-y-2 text-sm">
              {points.map((point) => (
                <div key={point.date} className="flex items-center justify-between text-dify-subtext">
                  <span>{point.date.slice(5)}</span>
                  <span className="font-medium text-dify-text">{point.query_count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [selectedKbId, setSelectedKbId] = useState("");
  const [selectedFileId, setSelectedFileId] = useState("");
  const [chunkModalOpen, setChunkModalOpen] = useState(false);
  const [chunkLoading, setChunkLoading] = useState(false);
  const [chunkError, setChunkError] = useState<string | null>(null);
  const [activeChunk, setActiveChunk] = useState<FileChunk | null>(null);

  const kbState = useAsync(() => api.listKnowledgeBases(), []);
  const fileState = useAsync(() => api.listFiles(selectedKbId || undefined), [selectedKbId]);
  const { data, loading, error, refresh } = useAsync(
    () => api.getFilteredDashboard({ kb_id: selectedKbId || undefined, file_id: selectedFileId || undefined }),
    [selectedKbId, selectedFileId],
  );

  const kbs = useMemo<KnowledgeBase[]>(() => kbState.data ?? [], [kbState.data]);
  const files = useMemo<KBFile[]>(() => fileState.data ?? [], [fileState.data]);

  async function onOpenChunk(chunkId: string) {
    setChunkModalOpen(true);
    setChunkLoading(true);
    setChunkError(null);
    setActiveChunk(null);
    try {
      const chunk = await api.getChunk(chunkId);
      setActiveChunk(chunk);
    } catch (err) {
      setChunkError(err instanceof Error ? err.message : "加载 chunk 内容失败");
    } finally {
      setChunkLoading(false);
    }
  }

  function onReplayQuery(query: string, kbId: string | null, mode: string) {
    const params = new URLSearchParams();
    params.set("query", query);
    params.set("mode", mode);
    if (kbId) {
      params.set("kb", kbId);
    }
    navigate(`/search?${params.toString()}`);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Dashboard"
        title="知识库仪表盘"
        description="查看知识库规模、查询趋势与 chunk 命中热点。"
        action={
          <Badge className="border-dify-blue/20 bg-dify-blueSoft text-dify-blue">
            实时数据视图
          </Badge>
        }
      />

      <Panel className="animate-rise-in p-4">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[220px_280px_1fr] xl:items-end">
          <Select label="按知识库筛选" value={selectedKbId} onChange={(event) => {
            setSelectedKbId(event.target.value);
            setSelectedFileId("");
          }}>
            <option value="">全部知识库</option>
            {kbs.map((kb) => (
              <option key={kb.id} value={kb.id}>{kb.name}</option>
            ))}
          </Select>
          <Select label="按文档筛选" value={selectedFileId} onChange={(event) => setSelectedFileId(event.target.value)}>
            <option value="">全部文档</option>
            {files.map((file) => (
              <option key={file.id} value={file.id}>{file.title}</option>
            ))}
          </Select>
          <div className="flex items-center gap-2 xl:justify-end">
            <SecondaryButton onClick={() => {
              setSelectedKbId("");
              setSelectedFileId("");
            }}>清空筛选</SecondaryButton>
            <Badge>{selectedKbId || selectedFileId ? "已启用筛选" : "全局统计"}</Badge>
          </div>
        </div>
      </Panel>

      {error ? (
        <StatusMessage title="仪表盘加载失败" description={error} action={<SecondaryButton onClick={() => refresh()}>重试</SecondaryButton>} />
      ) : null}

      {!error && loading ? <StatusMessage title="正在加载仪表盘..." description="请稍候" /> : null}

      {!error && !loading && data ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              title="知识库总数"
              value={data.stats.kb_count}
              detail={`其中 ${data.stats.queried_kb_count} 个知识库发生过查询`}
              icon={Database}
            />
            <StatCard
              title="文档总数"
              value={data.stats.file_count}
              detail={data.stats.file_count === 0 ? "暂无已导入文档" : "已纳入当前本地检索范围"}
              icon={FileText}
            />
            <StatCard
              title="Chunk 总数"
              value={data.stats.chunk_count}
              detail="用于向量 / FTS / 混合检索的切片总量"
              icon={BookCopy}
            />
            <StatCard
              title="累计查询次数"
              value={data.stats.query_count}
              detail={`累计 chunk 命中 ${data.stats.total_chunk_hits} 次`}
              icon={SearchIcon}
            />
          </div>

          <Panel className="animate-rise-in [animation-delay:60ms]">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-dify-text">最近 7 天查询趋势</h2>
                <p className="text-sm text-dify-subtext">用最近七天的查询量观察检索活跃度变化。</p>
              </div>
              <TrendingUp className="h-4 w-4 text-dify-subtext" />
            </div>
            {data.query_trend.length === 0 ? (
              <StatusMessage title="暂无趋势数据" description="有查询记录后，这里会展示 7 天趋势。" />
            ) : (
              <TrendLineChart points={data.query_trend} />
            )}
          </Panel>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
            <Panel className="animate-rise-in p-0 [animation-delay:80ms]">
              <div className="flex items-center justify-between border-b border-dify-border px-5 py-4">
                <div>
                  <h2 className="text-lg font-semibold text-dify-text">最近查询记录</h2>
                  <p className="text-sm text-dify-subtext">最近 10 次查询的关键词、范围与命中结果数。</p>
                </div>
                <Badge>{data.recent_queries.length} rows</Badge>
              </div>

              {data.recent_queries.length === 0 ? (
                <div className="p-5">
                  <StatusMessage title="暂无查询记录" description="先去 Search 页面执行一次查询。" />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-dify-border text-sm">
                    <thead className="bg-dify-muted/70 text-left text-xs uppercase tracking-[0.08em] text-dify-softText">
                      <tr>
                        <th className="px-5 py-3 font-medium">时间</th>
                        <th className="px-5 py-3 font-medium">Query</th>
                        <th className="px-5 py-3 font-medium">范围</th>
                        <th className="px-5 py-3 font-medium">模式</th>
                        <th className="px-5 py-3 font-medium">结果数</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dify-border">
                      {data.recent_queries.map((item) => (
                        <tr key={item.id} className="hover:bg-dify-muted/50">
                          <td className="whitespace-nowrap px-5 py-3 text-dify-subtext">{formatTime(item.created_at)}</td>
                          <td className="max-w-[320px] px-5 py-3 font-medium text-dify-text">
                            <button className="text-left text-dify-text hover:text-dify-blue" onClick={() => onReplayQuery(item.query, item.kb_id, item.mode)}>
                              {truncateText(item.query, 48)}
                            </button>
                          </td>
                          <td className="px-5 py-3 text-dify-subtext">{item.kb_name || "全部知识库"}</td>
                          <td className="px-5 py-3">
                            <Badge className="border-dify-blue/20 bg-dify-blueSoft text-dify-blue">{item.mode}</Badge>
                          </td>
                          <td className="px-5 py-3 text-dify-subtext">{item.result_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>

            <div className="space-y-4">
              <Panel className="animate-rise-in [animation-delay:120ms]">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-dify-text">Chunk 命中热点</h2>
                    <p className="text-sm text-dify-subtext">按累计命中次数排序，帮助识别高频内容与热点文档。</p>
                  </div>
                  <Activity className="h-4 w-4 text-dify-subtext" />
                </div>

                {data.chunk_hits.length === 0 ? (
                  <StatusMessage title="暂无 chunk 命中数据" description="查询结果产生后，这里会出现热点 chunk。" />
                ) : (
                  <div className="space-y-3">
                    {data.chunk_hits.map((item: DashboardChunkHit, index) => {
                      const maxHits = data.chunk_hits[0]?.hits ?? 1;
                      const width = Math.max((item.hits / maxHits) * 100, 8);

                      return (
                        <article key={item.chunk_id} className="space-y-2 rounded-xl border border-dify-border p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <button className="truncate text-left text-sm font-medium text-dify-text hover:text-dify-blue" onClick={() => onOpenChunk(item.chunk_id)}>
                                {item.file_name}
                              </button>
                              <p className="mt-1 text-xs text-dify-subtext">
                                {item.kb_name} · chunk #{item.chunk_index}
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge className={index === 0 ? "border-dify-blue/20 bg-dify-blueSoft text-dify-blue" : undefined}>
                                {item.hits} hits
                              </Badge>
                              <SecondaryButton onClick={() => onOpenChunk(item.chunk_id)}>
                                <Eye className="h-4 w-4" />
                                查看
                              </SecondaryButton>
                            </div>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-dify-muted">
                            <div className="h-full rounded-full bg-dify-blue" style={{ width: `${width}%` }} />
                          </div>
                          <p className="text-[11px] text-dify-softText">最后命中于 {formatTime(item.last_hit_at)}</p>
                          <div className="flex items-center gap-2 text-xs text-dify-subtext">
                            <Badge>{item.kb_name}</Badge>
                            <Badge>{item.file_name}</Badge>
                            <Link to={`/kbs/${encodeURIComponent(item.kb_id)}`} className="text-dify-blue hover:underline">
                              去知识库
                            </Link>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                )}
              </Panel>

              <Panel className="animate-rise-in [animation-delay:160ms]">
                <div className="mb-3 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-dify-subtext" />
                  <h2 className="text-lg font-semibold text-dify-text">运行概况</h2>
                </div>
                <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
                  <div className="rounded-xl border border-dify-border bg-dify-muted/60 p-3">
                    <p className="text-xs uppercase tracking-[0.08em] text-dify-softText">平均每库文档数</p>
                    <p className="mt-2 text-xl font-semibold text-dify-text">
                      {data.stats.kb_count > 0 ? (data.stats.file_count / data.stats.kb_count).toFixed(1) : "0.0"}
                    </p>
                  </div>
                  <div className="rounded-xl border border-dify-border bg-dify-muted/60 p-3">
                    <p className="text-xs uppercase tracking-[0.08em] text-dify-softText">平均每文档 chunk 数</p>
                    <p className="mt-2 text-xl font-semibold text-dify-text">
                      {data.stats.file_count > 0 ? (data.stats.chunk_count / data.stats.file_count).toFixed(1) : "0.0"}
                    </p>
                  </div>
                  <div className="rounded-xl border border-dify-border bg-dify-muted/60 p-3">
                    <p className="text-xs uppercase tracking-[0.08em] text-dify-softText">平均每次查询命中数</p>
                    <p className="mt-2 text-xl font-semibold text-dify-text">
                      {data.stats.query_count > 0 ? (data.stats.total_chunk_hits / data.stats.query_count).toFixed(1) : "0.0"}
                    </p>
                  </div>
                </div>
              </Panel>
            </div>
          </div>
        </>
      ) : null}

      <Modal open={chunkModalOpen} title={activeChunk ? `Chunk #${activeChunk.chunk_index}` : "Chunk 内容"} onClose={() => setChunkModalOpen(false)}>
        {chunkError ? <StatusMessage title="加载 chunk 失败" description={chunkError} /> : null}
        {!chunkError && chunkLoading ? <StatusMessage title="正在加载 chunk 内容..." /> : null}
        {!chunkError && !chunkLoading && activeChunk ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-xs text-dify-subtext">
              <Badge>{activeChunk.kb_id}</Badge>
              <Badge>{activeChunk.file_id}</Badge>
              <Badge>chunk #{activeChunk.chunk_index}</Badge>
              <Badge>{formatTime(activeChunk.updated_at)}</Badge>
            </div>
            <div className="rounded-xl border border-dify-border bg-dify-muted/40 p-4">
              <pre className="whitespace-pre-wrap break-words text-sm leading-6 text-dify-text">{activeChunk.text}</pre>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
