export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export type CategoryKey = "resumes" | "jobs" | "projects" | "notes";

export type DocumentInfo = {
  name: string;
  category: CategoryKey;
  source: "private" | "public";
  size_bytes: number;
  modified_at: string;
  editable: boolean;
  deletable: boolean;
};

export type SourceInfo = {
  source_file: string;
  title: string;
  score: number | null;
};

export type AskResponse = {
  answer: string;
  truncated: boolean;
  sources: SourceInfo[];
  retrieval_seconds: number;
  generation_seconds: number;
  mode: "rag" | "chat" | "system";
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type IndexResponse = {
  changed_sources: string[];
  skipped_sources: string[];
  removed_sources: string[];
  written_points: number;
  collection_name: string;
  storage_path: string;
  logs: string[];
};

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function askQuestion(question: string, history: ChatMessage[] = []): Promise<AskResponse> {
  const response = await fetch(`${API_BASE_URL}/api/rag/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history })
  });
  return parseResponse<AskResponse>(response);
}

export async function listDocuments(category: CategoryKey): Promise<DocumentInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${category}`);
  return parseResponse<DocumentInfo[]>(response);
}

export async function uploadDocument(category: CategoryKey, file: File): Promise<DocumentInfo> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/documents/${category}/upload`, {
    method: "POST",
    body: formData
  });
  return parseResponse<DocumentInfo>(response);
}

export async function deleteDocument(category: CategoryKey, name: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${category}/${encodeURIComponent(name)}`, {
    method: "DELETE"
  });
  await parseResponse(response);
}

export async function readDocument(category: CategoryKey, document: DocumentInfo): Promise<string> {
  const response = await fetch(
    `${API_BASE_URL}/api/documents/${category}/${encodeURIComponent(document.name)}?source=${document.source}`
  );
  const payload = await parseResponse<{ content: string }>(response);
  return payload.content;
}

export async function updateDocument(category: CategoryKey, name: string, content: string): Promise<DocumentInfo> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${category}/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content })
  });
  return parseResponse<DocumentInfo>(response);
}

export async function buildIndex(): Promise<IndexResponse> {
  const response = await fetch(`${API_BASE_URL}/api/index/build`, {
    method: "POST"
  });
  return parseResponse<IndexResponse>(response);
}
