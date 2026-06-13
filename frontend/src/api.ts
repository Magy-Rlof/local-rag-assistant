export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export type CategoryKey = "resumes" | "industries" | "jobs" | "projects" | "notes";

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

export type AskStreamMeta = {
  sources: SourceInfo[];
  retrieval_seconds: number;
  mode: AskResponse["mode"];
};

export type AskStreamCallbacks = {
  onMeta?: (meta: AskStreamMeta) => void;
  onDelta?: (text: string) => void;
  onDone?: (response: AskResponse) => void;
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

export async function askQuestionStream(
  question: string,
  history: ChatMessage[] = [],
  callbacks: AskStreamCallbacks = {}
): Promise<AskResponse> {
  const response = await fetch(`${API_BASE_URL}/api/rag/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history })
  });

  if (!response.ok || !response.body) {
    return parseResponse<AskResponse>(response);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResponse: AskResponse | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.event === "meta") {
        callbacks.onMeta?.({
          sources: event.sources ?? [],
          retrieval_seconds: event.retrieval_seconds ?? 0,
          mode: event.mode ?? "chat",
        });
      } else if (event.event === "delta") {
        callbacks.onDelta?.(event.text ?? "");
      } else if (event.event === "done") {
        finalResponse = {
          answer: event.answer ?? "",
          truncated: Boolean(event.truncated),
          sources: event.sources ?? [],
          retrieval_seconds: event.retrieval_seconds ?? 0,
          generation_seconds: event.generation_seconds ?? 0,
          mode: event.mode ?? "chat",
        };
        callbacks.onDone?.(finalResponse);
      } else if (event.event === "error") {
        throw new Error(event.message || "流式生成失败。");
      }
    }
  }

  if (buffer.trim()) {
    const event = JSON.parse(buffer);
    if (event.event === "done") {
      finalResponse = {
        answer: event.answer ?? "",
        truncated: Boolean(event.truncated),
        sources: event.sources ?? [],
        retrieval_seconds: event.retrieval_seconds ?? 0,
        generation_seconds: event.generation_seconds ?? 0,
        mode: event.mode ?? "chat",
      };
      callbacks.onDone?.(finalResponse);
    } else if (event.event === "error") {
      throw new Error(event.message || "流式生成失败。");
    }
  }

  if (!finalResponse) {
    throw new Error("流式生成没有返回完整结果。");
  }
  return finalResponse;
}

export async function listDocuments(category: CategoryKey): Promise<DocumentInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${category}`);
  return parseResponse<DocumentInfo[]>(response);
}

export async function getCurrentResume(): Promise<DocumentInfo | null> {
  const response = await fetch(`${API_BASE_URL}/api/resumes/current`);
  return parseResponse<DocumentInfo | null>(response);
}

export async function setCurrentResume(document: DocumentInfo): Promise<DocumentInfo> {
  const response = await fetch(`${API_BASE_URL}/api/resumes/current`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: document.name, source: document.source })
  });
  return parseResponse<DocumentInfo>(response);
}

export async function uploadDocument(
  category: CategoryKey,
  file: File,
  source: "private" | "public" = "private"
): Promise<DocumentInfo> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/documents/${category}/upload?source=${source}`, {
    method: "POST",
    body: formData
  });
  return parseResponse<DocumentInfo>(response);
}

export async function deleteDocument(
  category: CategoryKey,
  name: string,
  source: "private" | "public" = "private"
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${category}/${encodeURIComponent(name)}?source=${source}`, {
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

export async function updateDocument(
  category: CategoryKey,
  name: string,
  content: string,
  source: "private" | "public" = "private"
): Promise<DocumentInfo> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${category}/${encodeURIComponent(name)}?source=${source}`, {
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
