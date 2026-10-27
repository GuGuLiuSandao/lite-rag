import type {
  ApiResponse,
  DashboardPayload,
  FileContentPayload,
  FileChunk,
  KBFile,
  KnowledgeBase,
  SearchMode,
  SearchResultItem,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
  /\/$/,
  "",
) || "http://127.0.0.1:8000";

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    const message = payload?.error || payload?.detail || `Request failed (${response.status})`;
    throw new ApiError(message, response.status);
  }

  if (!payload?.ok) {
    throw new ApiError(payload?.error || "Unknown API error", response.status);
  }

  return (payload as ApiResponse<T>).result;
}

export const api = {
  baseUrl: API_BASE,

  listKnowledgeBases(): Promise<KnowledgeBase[]> {
    return request<KnowledgeBase[]>("/kb");
  },

  getDashboard(): Promise<DashboardPayload> {
    return request<DashboardPayload>("/dashboard");
  },

  getFilteredDashboard(payload?: { kb_id?: string; file_id?: string }): Promise<DashboardPayload> {
    const searchParams = new URLSearchParams();
    if (payload?.kb_id) {
      searchParams.set("kb_id", payload.kb_id);
    }
    if (payload?.file_id) {
      searchParams.set("file_id", payload.file_id);
    }
    const query = searchParams.toString();
    return request<DashboardPayload>(`/dashboard${query ? `?${query}` : ""}`);
  },

  getChunk(chunkId: string): Promise<FileChunk> {
    return request<FileChunk>(`/chunk/${encodeURIComponent(chunkId)}`);
  },

  getKnowledgeBase(kbRef: string): Promise<KnowledgeBase> {
    return request<KnowledgeBase>(`/kb/${encodeURIComponent(kbRef)}`);
  },

  getFileContent(fileId: string): Promise<FileContentPayload> {
    return request<FileContentPayload>(`/file/${encodeURIComponent(fileId)}/content`);
  },

  getFileChunks(fileId: string): Promise<FileChunk[]> {
    return request<FileChunk[]>(`/file/${encodeURIComponent(fileId)}/chunks`);
  },

  createKnowledgeBase(payload: { name: string; description?: string }): Promise<KnowledgeBase> {
    return request<KnowledgeBase>("/kb", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateKnowledgeBase(
    kbRef: string,
    payload: { name?: string; description?: string },
  ): Promise<KnowledgeBase> {
    return request<KnowledgeBase>(`/kb/${encodeURIComponent(kbRef)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  deleteKnowledgeBase(kbRef: string): Promise<KnowledgeBase> {
    return request<KnowledgeBase>(`/kb/${encodeURIComponent(kbRef)}`, {
      method: "DELETE",
    });
  },

  listFiles(kbRef?: string): Promise<KBFile[]> {
    const query = kbRef ? `?kb=${encodeURIComponent(kbRef)}` : "";
    return request<KBFile[]>(`/file${query}`);
  },

  updateFile(fileId: string, payload: { title?: string }): Promise<KBFile> {
    return request<KBFile>(`/file/${encodeURIComponent(fileId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  deleteFile(fileId: string): Promise<KBFile> {
    return request<KBFile>(`/file/${encodeURIComponent(fileId)}`, {
      method: "DELETE",
    });
  },

  async uploadFile(payload: { kb: string; file: File; title?: string }): Promise<KBFile> {
    const body = new FormData();
    body.append("kb", payload.kb);
    body.append("file", payload.file);
    if (payload.title) {
      body.append("title", payload.title);
    }

    const response = await fetch(`${API_BASE}/file/upload`, {
      method: "POST",
      body,
    });
    const data = await response.json();
    if (!response.ok || !data?.ok) {
      throw new ApiError(data?.error || `Upload failed (${response.status})`, response.status);
    }
    return data.result as KBFile;
  },

  search(payload: {
    query: string;
    kb?: string;
    file_ids?: string[];
    mode: SearchMode;
    enable_reranker?: boolean;
    recall_top_k?: number;
    final_top_k?: number;
  }): Promise<SearchResultItem[]> {
    return request<SearchResultItem[]>("/search", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};

export { ApiError };
