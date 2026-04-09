export type SearchMode = "vector" | "fts" | "hybrid";

export interface ApiResponse<T> {
  ok: boolean;
  result: T;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface KBFile {
  id: string;
  kb_id: string;
  kb_name: string;
  title: string;
  source_name: string;
  stored_path: string;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface FileContentPayload {
  file: KBFile;
  content: string;
}

export interface FileChunk {
  id: string;
  file_id: string;
  kb_id: string;
  chunk_index: number;
  text: string;
  created_at: string;
  updated_at: string;
}

export interface SearchResultItem {
  chunk_id: string;
  kb_id: string;
  kb_name: string;
  file_id: string;
  file_name: string;
  chunk_index: number;
  score: number | null;
  final_score: number | null;
  retrieval_score: number | null;
  rerank_score: number | null;
  text: string;
}

export interface DashboardStats {
  kb_count: number;
  file_count: number;
  chunk_count: number;
  query_count: number;
  total_chunk_hits: number;
  queried_kb_count: number;
}

export interface DashboardQueryRecord {
  id: string;
  query: string;
  kb_id: string | null;
  kb_name: string | null;
  mode: SearchMode;
  result_count: number;
  created_at: string;
}

export interface DashboardChunkHit {
  chunk_id: string;
  kb_id: string;
  kb_name: string;
  file_id: string;
  file_name: string;
  chunk_index: number;
  hits: number;
  last_hit_at: string;
}

export interface DashboardTrendPoint {
  date: string;
  query_count: number;
}

export interface DashboardPayload {
  stats: DashboardStats;
  query_trend: DashboardTrendPoint[];
  recent_queries: DashboardQueryRecord[];
  chunk_hits: DashboardChunkHit[];
}
