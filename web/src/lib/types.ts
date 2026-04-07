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
  text: string;
}
