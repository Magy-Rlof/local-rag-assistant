export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export type CategoryKey = "resumes" | "industries" | "jobs" | "projects";

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

export type ChatArtifactAction = {
  label: string;
  kind: "download_markdown" | "open_job_agent";
};

export type ChatArtifact = {
  artifact_id: string;
  type: "job_summary" | "job_match_report" | "resume_revision_draft" | "interview_session";
  title: string;
  description: string;
  query: string;
  scope_note: string;
  file_name: string;
  relative_path: string;
  content_preview: string;
  content_markdown: string;
  review_status: string;
  warnings: string[];
  highlights?: string[];
  metrics?: Record<string, string | number | boolean>;
  generation_mode?: string;
  generation_model?: string;
  generation_seconds?: number;
  llm_attempted?: boolean;
  llm_repair_attempted?: boolean;
  fallback_reason?: string;
  fallback_detail?: string;
  cache_hit?: boolean;
  validation_errors?: string[];
  resume_evidence_status?: string;
  resume_evidence_status_label?: string;
  question_type_summary?: Record<string, number>;
  skill_areas?: string[];
  session_payload?: JobInterviewSessionResponse;
  actions: ChatArtifactAction[];
};

export type AskResponse = {
  answer: string;
  truncated: boolean;
  sources: SourceInfo[];
  retrieval_seconds: number;
  generation_seconds: number;
  mode: "rag" | "chat" | "system";
  artifacts: ChatArtifact[];
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

export type AskStreamOptions = {
  requestId?: string;
  signal?: AbortSignal;
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

export type JobBasicInfo = {
  title: string;
  company: string;
  source: string;
  source_job_id: string;
  source_url: string;
  source_file: string;
};

export type JobTargetConfirmation = {
  title: string;
  company: string;
  source: string;
  source_job_id: string;
  source_url: string;
  source_file: string;
};

export type CurrentMaterialMatchPoint = {
  point: string;
  evidence: string;
  boundary: string;
};

export type EvidenceRequiredCandidate = {
  candidate_direction: string;
  required_evidence: string;
};

export type InterviewOnlyCandidate = {
  topic: string;
  usage: string;
};

export type CannotClaimCandidate = {
  claim: string;
  reason: string;
  source_requirement: string;
};

export type JobMatchDraft = {
  target_confirmation: JobTargetConfirmation;
  job_core_requirements: string[];
  job_core_responsibilities: string[];
  current_material_match_points: CurrentMaterialMatchPoint[];
  resume_revision_candidates: {
    can_write_to_resume: string[];
    requires_evidence_before_resume: EvidenceRequiredCandidate[];
    interview_only: InterviewOnlyCandidate[];
    cannot_claim: CannotClaimCandidate[];
    resume_state: string;
  };
  interview_questions: string[];
  evidence_gaps: string[];
  safety_notes: string[];
};

export type JobMatchDraftResponse = {
  matched: boolean;
  query: string;
  target_job: JobBasicInfo | null;
  current_resume: DocumentInfo | null;
  draft: JobMatchDraft | null;
  warnings: string[];
};

export type JobMatchDraftExportResponse = {
  exported: boolean;
  query: string;
  target_job: JobBasicInfo | null;
  current_resume: DocumentInfo | null;
  file_name: string;
  relative_path: string;
  size_bytes: number;
  content_preview: string;
  warnings: string[];
};

export type JobMatchDraftExportFile = {
  file_name: string;
  relative_path: string;
  size_bytes: number;
  modified_at: string;
};

export type JobMatchDraftExportListResponse = {
  drafts: JobMatchDraftExportFile[];
  count: number;
  directory: string;
  warnings: string[];
};

export type JobMatchDraftExportContentResponse = JobMatchDraftExportFile & {
  content: string;
};

export type JobMatchDraftExportDeleteResponse = {
  deleted: boolean;
  file_name: string;
  relative_path: string;
  warnings: string[];
};

export type ResumeRevisionDraftExportResponse = {
  exported: boolean;
  query: string;
  target_job: JobBasicInfo | null;
  current_resume: DocumentInfo | null;
  file_name: string;
  relative_path: string;
  size_bytes: number;
  content_preview: string;
  warnings: string[];
};

export type ResumeRevisionDraftExportFile = {
  file_name: string;
  relative_path: string;
  size_bytes: number;
  modified_at: string;
};

export type ResumeRevisionDraftExportListResponse = {
  drafts: ResumeRevisionDraftExportFile[];
  count: number;
  directory: string;
  warnings: string[];
};

export type ResumeRevisionDraftExportContentResponse = ResumeRevisionDraftExportFile & {
  content: string;
};

export type ResumeRevisionDraftExportDeleteResponse = {
  deleted: boolean;
  file_name: string;
  relative_path: string;
  warnings: string[];
};

export type ResumeRevisionCompareResponse = {
  file_name: string;
  relative_path: string;
  current_resume: DocumentInfo | null;
  current_resume_readable: boolean;
  current_resume_content: string;
  resume_diff_content: string;
  warnings: string[];
};

export type ResumeWriteReviewQueueResponse = {
  queued: boolean;
  source_diff_file_name: string;
  source_diff_relative_path: string;
  file_name: string;
  relative_path: string;
  size_bytes: number;
  content_preview: string;
  review_status: string;
  review_label: string;
  review_note: string;
  review_updated_at: string;
  warnings: string[];
};

export type ResumeWriteReviewQueueFile = {
  file_name: string;
  relative_path: string;
  size_bytes: number;
  modified_at: string;
  review_status: string;
  review_label: string;
  review_note: string;
  review_updated_at: string;
  source_diff_file_name: string;
  source_diff_relative_path: string;
};

export type ResumeWriteReviewQueueListResponse = {
  items: ResumeWriteReviewQueueFile[];
  count: number;
  directory: string;
  warnings: string[];
};

export type ResumeWriteReviewQueueContentResponse = ResumeWriteReviewQueueFile & {
  content: string;
};

export type ResumeWriteReviewUpdateResponse = ResumeWriteReviewQueueContentResponse & {
  warnings: string[];
};

export type ResumeWriteReviewDeleteResponse = {
  deleted: boolean;
  file_name: string;
  relative_path: string;
  warnings: string[];
};

export type JobMatchReportExportResponse = {
  exported: boolean;
  query: string;
  target_job: JobBasicInfo | null;
  current_resume: DocumentInfo | null;
  file_name: string;
  relative_path: string;
  size_bytes: number;
  content_preview: string;
  review_status: string;
  review_label: string;
  review_note: string;
  review_updated_at: string;
  warnings: string[];
};

export type JobMatchReportExportFile = {
  file_name: string;
  relative_path: string;
  size_bytes: number;
  modified_at: string;
  review_status: string;
  review_label: string;
  review_note: string;
  review_updated_at: string;
};

export type JobMatchReportExportListResponse = {
  reports: JobMatchReportExportFile[];
  count: number;
  directory: string;
  warnings: string[];
};

export type JobMatchReportExportContentResponse = JobMatchReportExportFile & {
  content: string;
};

export type JobMatchReportExportDeleteResponse = {
  deleted: boolean;
  file_name: string;
  relative_path: string;
  warnings: string[];
};

export type JobMatchReportReviewUpdateResponse = JobMatchReportExportContentResponse & {
  warnings: string[];
};

export type JobMatchBatchReportItem = {
  query: string;
  file_name: string;
  relative_path: string;
  size_bytes: number;
  target_job: JobBasicInfo | null;
};

export type JobMatchBatchReportFailure = {
  query: string;
  error: string;
};

export type JobMatchReportBatchQueueResponse = {
  queued: boolean;
  batch_id: string;
  file_name: string;
  relative_path: string;
  size_bytes: number;
  query_count: number;
  created_count: number;
  failed_count: number;
  generated_reports: JobMatchBatchReportItem[];
  failures: JobMatchBatchReportFailure[];
  content_preview: string;
  review_status: string;
  review_label: string;
  review_note: string;
  review_updated_at: string;
  warnings: string[];
};

export type JobMatchReportBatchQueueFile = {
  batch_id: string;
  file_name: string;
  relative_path: string;
  size_bytes: number;
  modified_at: string;
  query_count: number;
  created_count: number;
  failed_count: number;
  review_status: string;
  review_label: string;
  review_note: string;
  review_updated_at: string;
};

export type JobMatchReportBatchQueueListResponse = {
  batches: JobMatchReportBatchQueueFile[];
  count: number;
  directory: string;
  warnings: string[];
};

export type JobMatchReportBatchQueueContentResponse = JobMatchReportBatchQueueFile & {
  queries: string[];
  generated_reports: JobMatchBatchReportItem[];
  failures: JobMatchBatchReportFailure[];
  content: string;
};

export type JobMatchReportBatchReviewUpdateResponse = JobMatchReportBatchQueueContentResponse & {
  warnings: string[];
};

export type JobMatchReportBatchDeleteResponse = {
  deleted: boolean;
  file_name: string;
  relative_path: string;
  warnings: string[];
};

export type InterviewQuestion = {
  question_id: number;
  type?: "single_choice" | "multiple_choice" | "true_false" | "short_answer" | "open" | string;
  question_type?: string;
  difficulty?: string;
  skill_area?: string;
  tested_skill?: string;
  question: string;
  stem?: string;
  options?: Array<{ key: string; text: string }>;
  correct_answer?: string | string[];
  explanation?: string;
  source_requirement_id?: string;
  source_requirement?: string;
  source_refs?: Array<{ type: string; source_id: string; relative_path: string; quote: string; section?: string }>;
  risk_hint?: string;
  safety_note?: string;
  requirement: string;
  intent: string;
  answer_checkpoints: string[];
  risk_reminder: string;
};

export type InterviewSession = {
  target_confirmation: JobTargetConfirmation;
  generation_mode?: string;
  generation_model?: string;
  generation_seconds?: number;
  llm_attempted?: boolean;
  llm_repair_attempted?: boolean;
  fallback_reason?: string;
  fallback_detail?: string;
  cache_hit?: boolean;
  validation_errors?: string[];
  questions: InterviewQuestion[];
  answer_guidance: string[];
  safety_notes: string[];
};

export type JobInterviewSessionResponse = {
  matched: boolean;
  query: string;
  target_job: JobBasicInfo | null;
  current_resume: DocumentInfo | null;
  session: InterviewSession | null;
  warnings: string[];
  generation_mode?: string;
  generation_model?: string;
  generation_seconds?: number;
  llm_attempted?: boolean;
  llm_repair_attempted?: boolean;
  fallback_reason?: string;
  fallback_detail?: string;
  cache_hit?: boolean;
  validation_errors?: string[];
};

export type InterviewFeedback = {
  summary: string;
  clarity: string;
  evidence_strength: string;
  boundary_risk: string;
  strengths: string[];
  improvements: string[];
  risk_flags: string[];
  suggested_next_answer_shape: string[];
};

export type JobInterviewFeedbackResponse = {
  matched: boolean;
  query: string;
  target_job: JobBasicInfo | null;
  question: InterviewQuestion | null;
  feedback: InterviewFeedback | null;
  warnings: string[];
};

export type AgentStatusItem = {
  step: string;
  label: string;
  status: string;
  detail: string;
};

export type AgentAction = {
  action: string;
  label: string;
  endpoint: string;
};

export type DisabledAgentAction = {
  action: string;
  reason: string;
};

export type JobAgentSummaryResponse = {
  matched: boolean;
  query: string;
  target_job: JobBasicInfo | null;
  current_resume: DocumentInfo | null;
  summary: {
    target_confirmation: JobTargetConfirmation;
    pipeline_status: AgentStatusItem[];
    available_actions: AgentAction[];
    disabled_actions: DisabledAgentAction[];
    draft_preview: {
      requirements_count: number;
      responsibilities_count: number;
      can_write_count: number;
      requires_evidence_count: number;
      interview_only_count: number;
      cannot_claim_count: number;
      evidence_gaps: string[];
    };
    interview_preview: {
      question_count: number;
      first_question: string;
      answer_guidance: string[];
    };
    safety_notes: string[];
    recommended_next_steps: string[];
  } | null;
  warnings: string[];
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
  callbacks: AskStreamCallbacks = {},
  options: AskStreamOptions = {}
): Promise<AskResponse> {
  const response = await fetch(`${API_BASE_URL}/api/rag/ask/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(options.requestId ? { "X-Request-Id": options.requestId } : {}),
    },
    body: JSON.stringify({ question, history }),
    signal: options.signal,
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
          artifacts: event.artifacts ?? [],
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
        artifacts: event.artifacts ?? [],
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

export async function buildJobAgentSummary(query: string): Promise<JobAgentSummaryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/agent/summary?query=${encodeURIComponent(query)}`);
  return parseResponse<JobAgentSummaryResponse>(response);
}

export async function buildJobMatchDraft(query: string): Promise<JobMatchDraftResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/draft?query=${encodeURIComponent(query)}`);
  return parseResponse<JobMatchDraftResponse>(response);
}

export async function exportJobMatchDraft(query: string, note: string): Promise<JobMatchDraftExportResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/draft/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, note, confirm_save: true }),
  });
  return parseResponse<JobMatchDraftExportResponse>(response);
}

export async function listJobMatchDraftExports(): Promise<JobMatchDraftExportListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/draft/exports`);
  return parseResponse<JobMatchDraftExportListResponse>(response);
}

export async function readJobMatchDraftExport(fileName: string): Promise<JobMatchDraftExportContentResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/draft/exports/${encodeURIComponent(fileName)}`);
  return parseResponse<JobMatchDraftExportContentResponse>(response);
}

export async function deleteJobMatchDraftExport(fileName: string): Promise<JobMatchDraftExportDeleteResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/draft/exports/${encodeURIComponent(fileName)}`, {
    method: "DELETE",
  });
  return parseResponse<JobMatchDraftExportDeleteResponse>(response);
}

export async function exportResumeRevisionDraft(query: string, note: string): Promise<ResumeRevisionDraftExportResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/resume-diff/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, note, confirm_save: true }),
  });
  return parseResponse<ResumeRevisionDraftExportResponse>(response);
}

export async function listResumeRevisionDraftExports(): Promise<ResumeRevisionDraftExportListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/resume-diff/exports`);
  return parseResponse<ResumeRevisionDraftExportListResponse>(response);
}

export async function readResumeRevisionDraftExport(fileName: string): Promise<ResumeRevisionDraftExportContentResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/resume-diff/exports/${encodeURIComponent(fileName)}`);
  return parseResponse<ResumeRevisionDraftExportContentResponse>(response);
}

export async function compareResumeRevisionWithCurrent(fileName: string): Promise<ResumeRevisionCompareResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/jobs/match/resume-diff/exports/${encodeURIComponent(fileName)}/compare-current`
  );
  return parseResponse<ResumeRevisionCompareResponse>(response);
}

export async function deleteResumeRevisionDraftExport(fileName: string): Promise<ResumeRevisionDraftExportDeleteResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/resume-diff/exports/${encodeURIComponent(fileName)}`, {
    method: "DELETE",
  });
  return parseResponse<ResumeRevisionDraftExportDeleteResponse>(response);
}

export async function createResumeWriteReviewItem(
  diffFileName: string,
  note: string
): Promise<ResumeWriteReviewQueueResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/resume-write-review/queue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ diff_file_name: diffFileName, note, confirm_queue: true }),
  });
  return parseResponse<ResumeWriteReviewQueueResponse>(response);
}

export async function listResumeWriteReviewItems(): Promise<ResumeWriteReviewQueueListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/resume-write-review/queue`);
  return parseResponse<ResumeWriteReviewQueueListResponse>(response);
}

export async function readResumeWriteReviewItem(fileName: string): Promise<ResumeWriteReviewQueueContentResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/resume-write-review/queue/${encodeURIComponent(fileName)}`);
  return parseResponse<ResumeWriteReviewQueueContentResponse>(response);
}

export async function updateResumeWriteReviewItem(
  fileName: string,
  reviewStatus: string,
  reviewNote: string
): Promise<ResumeWriteReviewUpdateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/resume-write-review/queue/${encodeURIComponent(fileName)}/review`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_status: reviewStatus, review_note: reviewNote }),
  });
  return parseResponse<ResumeWriteReviewUpdateResponse>(response);
}

export async function deleteResumeWriteReviewItem(fileName: string): Promise<ResumeWriteReviewDeleteResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/resume-write-review/queue/${encodeURIComponent(fileName)}`, {
    method: "DELETE",
  });
  return parseResponse<ResumeWriteReviewDeleteResponse>(response);
}

export async function exportJobMatchReport(query: string, note: string): Promise<JobMatchReportExportResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/report/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, note, confirm_save: true }),
  });
  return parseResponse<JobMatchReportExportResponse>(response);
}

export async function listJobMatchReportExports(): Promise<JobMatchReportExportListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/report/exports`);
  return parseResponse<JobMatchReportExportListResponse>(response);
}

export async function readJobMatchReportExport(fileName: string): Promise<JobMatchReportExportContentResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/report/exports/${encodeURIComponent(fileName)}`);
  return parseResponse<JobMatchReportExportContentResponse>(response);
}

export async function deleteJobMatchReportExport(fileName: string): Promise<JobMatchReportExportDeleteResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/report/exports/${encodeURIComponent(fileName)}`, {
    method: "DELETE",
  });
  return parseResponse<JobMatchReportExportDeleteResponse>(response);
}

export async function updateJobMatchReportReview(
  fileName: string,
  reviewStatus: string,
  reviewNote: string
): Promise<JobMatchReportReviewUpdateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/report/exports/${encodeURIComponent(fileName)}/review`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_status: reviewStatus, review_note: reviewNote }),
  });
  return parseResponse<JobMatchReportReviewUpdateResponse>(response);
}

export async function createJobMatchReportBatchQueue(
  queries: string[],
  note: string
): Promise<JobMatchReportBatchQueueResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/report/batch-queue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ queries, note, confirm_queue: true }),
  });
  return parseResponse<JobMatchReportBatchQueueResponse>(response);
}

export async function listJobMatchReportBatchQueues(): Promise<JobMatchReportBatchQueueListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/report/batch-queue`);
  return parseResponse<JobMatchReportBatchQueueListResponse>(response);
}

export async function readJobMatchReportBatchQueue(fileName: string): Promise<JobMatchReportBatchQueueContentResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/report/batch-queue/${encodeURIComponent(fileName)}`);
  return parseResponse<JobMatchReportBatchQueueContentResponse>(response);
}

export async function updateJobMatchReportBatchReview(
  fileName: string,
  reviewStatus: string,
  reviewNote: string
): Promise<JobMatchReportBatchReviewUpdateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/report/batch-queue/${encodeURIComponent(fileName)}/review`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_status: reviewStatus, review_note: reviewNote }),
  });
  return parseResponse<JobMatchReportBatchReviewUpdateResponse>(response);
}

export async function deleteJobMatchReportBatchQueue(fileName: string): Promise<JobMatchReportBatchDeleteResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/match/report/batch-queue/${encodeURIComponent(fileName)}`, {
    method: "DELETE",
  });
  return parseResponse<JobMatchReportBatchDeleteResponse>(response);
}

export async function buildJobInterviewSession(query: string): Promise<JobInterviewSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/interview/session?query=${encodeURIComponent(query)}`);
  return parseResponse<JobInterviewSessionResponse>(response);
}

export async function buildJobInterviewFeedback(
  query: string,
  questionId: number,
  answer: string
): Promise<JobInterviewFeedbackResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/interview/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, question_id: questionId, answer }),
  });
  return parseResponse<JobInterviewFeedbackResponse>(response);
}
