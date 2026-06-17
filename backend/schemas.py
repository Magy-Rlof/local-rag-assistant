from pydantic import BaseModel, Field
from typing import Literal


class DocumentInfo(BaseModel):
    name: str
    category: str
    source: str
    size_bytes: int
    modified_at: str
    editable: bool
    deletable: bool


class DocumentContent(BaseModel):
    name: str
    category: str
    source: str
    content: str


class UpdateDocumentRequest(BaseModel):
    content: str


class SetCurrentResumeRequest(BaseModel):
    name: str
    source: Literal["private", "public"] = "private"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    question: str
    history: list[ChatMessage] = Field(default_factory=list)


class SourceInfo(BaseModel):
    source_file: str
    title: str
    score: float | None = None


class ChatArtifactAction(BaseModel):
    label: str
    kind: Literal["download_markdown", "open_job_agent"]


class ChatArtifact(BaseModel):
    artifact_id: str
    type: Literal["job_summary", "job_match_report", "resume_revision_draft", "interview_session"]
    title: str
    description: str
    query: str = ""
    scope_note: str
    file_name: str = ""
    relative_path: str = ""
    content_preview: str = ""
    content_markdown: str = ""
    review_status: str = ""
    warnings: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    metrics: dict[str, int | str | bool] = Field(default_factory=dict)
    generation_mode: str = ""
    generation_model: str = ""
    generation_seconds: float = 0.0
    llm_attempted: bool = False
    llm_repair_attempted: bool = False
    fallback_reason: str = ""
    fallback_detail: str = ""
    validation_errors: list[str] = Field(default_factory=list)
    resume_evidence_status: str = ""
    resume_evidence_status_label: str = ""
    question_type_summary: dict[str, int] = Field(default_factory=dict)
    skill_areas: list[str] = Field(default_factory=list)
    session_payload: dict = Field(default_factory=dict)
    actions: list[ChatArtifactAction] = Field(default_factory=list)


class JobCandidateInfo(BaseModel):
    source_file: str
    file_name: str
    source: str
    title: str
    source_job_id: str = ""
    marker: str = ""


class JobBasicInfo(BaseModel):
    source_file: str
    file_name: str
    source: str
    title: str
    basic_info: dict[str, str]
    source_name: str = ""
    source_channel: str = ""
    source_job_id: str = ""
    source_url: str = ""
    marker: str = ""
    city: str = ""
    company: str = ""
    salary: str = ""
    experience: str = ""
    education: str = ""
    job_category: str = ""
    headcount: str = ""
    industry: str = ""
    company_size: str = ""
    company_nature: str = ""


class JobResolveResponse(BaseModel):
    matched: bool
    query: str
    job: JobBasicInfo | None
    candidates: list[JobCandidateInfo]


class JobMatchEvidence(BaseModel):
    source_file: str
    title: str
    responsibilities_text: str = ""
    requirements_text: str = ""
    raw_description_excerpt: str = ""


class JobMatchOutputContract(BaseModel):
    sections: list[str]
    resume_safety_rules: list[str]
    evidence_rules: list[str]


class JobMatchContextResponse(BaseModel):
    matched: bool
    query: str
    target_job: JobBasicInfo | None
    current_resume: DocumentInfo | None
    job_evidence: JobMatchEvidence | None
    output_contract: JobMatchOutputContract
    analysis_prompt: str
    warnings: list[str]


class JobTargetConfirmation(BaseModel):
    title: str
    company: str
    city: str
    source_job_id: str
    marker: str
    source_file: str
    source_url: str


class CurrentMaterialMatchPoint(BaseModel):
    point: str
    evidence: str
    boundary: str


class EvidenceRequiredCandidate(BaseModel):
    candidate_direction: str
    required_evidence: str


class InterviewOnlyCandidate(BaseModel):
    topic: str
    usage: str


class CannotClaimCandidate(BaseModel):
    claim: str
    reason: str
    source_requirement: str


class ResumeRevisionCandidates(BaseModel):
    can_write_to_resume: list[str]
    requires_evidence_before_resume: list[EvidenceRequiredCandidate]
    interview_only: list[InterviewOnlyCandidate]
    cannot_claim: list[CannotClaimCandidate]
    resume_state: str


class JobMatchDraft(BaseModel):
    target_confirmation: JobTargetConfirmation
    job_core_requirements: list[str]
    job_core_responsibilities: list[str]
    current_material_match_points: list[CurrentMaterialMatchPoint]
    resume_revision_candidates: ResumeRevisionCandidates
    interview_questions: list[str]
    evidence_gaps: list[str]
    safety_notes: list[str]


class JobMatchDraftResponse(BaseModel):
    matched: bool
    query: str
    target_job: JobBasicInfo | None
    current_resume: DocumentInfo | None
    draft: JobMatchDraft | None
    warnings: list[str]


class JobMatchDraftExportRequest(BaseModel):
    query: str
    confirm_save: bool = False
    note: str = ""


class JobMatchDraftExportResponse(BaseModel):
    exported: bool
    query: str
    target_job: JobBasicInfo | None
    current_resume: DocumentInfo | None
    file_name: str
    relative_path: str
    size_bytes: int
    content_preview: str
    warnings: list[str]


class JobMatchDraftExportFile(BaseModel):
    file_name: str
    relative_path: str
    size_bytes: int
    modified_at: str


class JobMatchDraftExportListResponse(BaseModel):
    drafts: list[JobMatchDraftExportFile]
    count: int
    directory: str
    warnings: list[str]


class JobMatchDraftExportContentResponse(BaseModel):
    file_name: str
    relative_path: str
    size_bytes: int
    modified_at: str
    content: str


class JobMatchDraftExportDeleteResponse(BaseModel):
    deleted: bool
    file_name: str
    relative_path: str
    warnings: list[str]


class ResumeRevisionDraftExportRequest(BaseModel):
    query: str
    confirm_save: bool = False
    note: str = ""


class ResumeRevisionDraftExportResponse(BaseModel):
    exported: bool
    query: str
    target_job: JobBasicInfo | None
    current_resume: DocumentInfo | None
    file_name: str
    relative_path: str
    size_bytes: int
    content_preview: str
    warnings: list[str]


class ResumeRevisionDraftExportFile(BaseModel):
    file_name: str
    relative_path: str
    size_bytes: int
    modified_at: str


class ResumeRevisionDraftExportListResponse(BaseModel):
    drafts: list[ResumeRevisionDraftExportFile]
    count: int
    directory: str
    warnings: list[str]


class ResumeRevisionDraftExportContentResponse(BaseModel):
    file_name: str
    relative_path: str
    size_bytes: int
    modified_at: str
    content: str


class ResumeRevisionDraftExportDeleteResponse(BaseModel):
    deleted: bool
    file_name: str
    relative_path: str
    warnings: list[str]


class ResumeRevisionCompareResponse(BaseModel):
    file_name: str
    relative_path: str
    current_resume: DocumentInfo | None
    current_resume_readable: bool
    current_resume_content: str
    resume_diff_content: str
    warnings: list[str]


class ResumeWriteReviewQueueRequest(BaseModel):
    diff_file_name: str
    confirm_queue: bool = False
    note: str = ""


class ResumeWriteReviewQueueResponse(BaseModel):
    queued: bool
    source_diff_file_name: str
    source_diff_relative_path: str
    file_name: str
    relative_path: str
    size_bytes: int
    content_preview: str
    review_status: str
    review_label: str
    review_note: str
    review_updated_at: str
    warnings: list[str]


class ResumeWriteReviewQueueFile(BaseModel):
    file_name: str
    relative_path: str
    size_bytes: int
    modified_at: str
    review_status: str
    review_label: str
    review_note: str
    review_updated_at: str
    source_diff_file_name: str
    source_diff_relative_path: str


class ResumeWriteReviewQueueListResponse(BaseModel):
    items: list[ResumeWriteReviewQueueFile]
    count: int
    directory: str
    warnings: list[str]


class ResumeWriteReviewQueueContentResponse(ResumeWriteReviewQueueFile):
    content: str


class ResumeWriteReviewUpdateRequest(BaseModel):
    review_status: str
    review_note: str = ""


class ResumeWriteReviewUpdateResponse(ResumeWriteReviewQueueContentResponse):
    warnings: list[str]


class ResumeWriteReviewDeleteResponse(BaseModel):
    deleted: bool
    file_name: str
    relative_path: str
    warnings: list[str]


class JobMatchReportExportRequest(BaseModel):
    query: str
    confirm_save: bool = False
    note: str = ""


class JobMatchReportExportResponse(BaseModel):
    exported: bool
    query: str
    target_job: JobBasicInfo | None
    current_resume: DocumentInfo | None
    file_name: str
    relative_path: str
    size_bytes: int
    content_preview: str
    review_status: str
    review_label: str
    review_note: str
    review_updated_at: str
    warnings: list[str]


class JobMatchReportExportFile(BaseModel):
    file_name: str
    relative_path: str
    size_bytes: int
    modified_at: str
    review_status: str
    review_label: str
    review_note: str
    review_updated_at: str


class JobMatchReportExportListResponse(BaseModel):
    reports: list[JobMatchReportExportFile]
    count: int
    directory: str
    warnings: list[str]


class JobMatchReportExportContentResponse(BaseModel):
    file_name: str
    relative_path: str
    size_bytes: int
    modified_at: str
    review_status: str
    review_label: str
    review_note: str
    review_updated_at: str
    content: str


class JobMatchReportExportDeleteResponse(BaseModel):
    deleted: bool
    file_name: str
    relative_path: str
    warnings: list[str]


class JobMatchReportReviewUpdateRequest(BaseModel):
    review_status: str
    review_note: str = ""


class JobMatchReportReviewUpdateResponse(BaseModel):
    file_name: str
    relative_path: str
    size_bytes: int
    modified_at: str
    review_status: str
    review_label: str
    review_note: str
    review_updated_at: str
    content: str
    warnings: list[str]


class JobMatchBatchReportItem(BaseModel):
    query: str
    file_name: str
    relative_path: str
    size_bytes: int
    target_job: JobBasicInfo | None


class JobMatchBatchReportFailure(BaseModel):
    query: str
    error: str


class JobMatchReportBatchQueueRequest(BaseModel):
    queries: list[str]
    confirm_queue: bool = False
    note: str = ""


class JobMatchReportBatchQueueResponse(BaseModel):
    queued: bool
    batch_id: str
    file_name: str
    relative_path: str
    size_bytes: int
    query_count: int
    created_count: int
    failed_count: int
    generated_reports: list[JobMatchBatchReportItem]
    failures: list[JobMatchBatchReportFailure]
    content_preview: str
    review_status: str
    review_label: str
    review_note: str
    review_updated_at: str
    warnings: list[str]


class JobMatchReportBatchQueueFile(BaseModel):
    batch_id: str
    file_name: str
    relative_path: str
    size_bytes: int
    modified_at: str
    query_count: int
    created_count: int
    failed_count: int
    review_status: str
    review_label: str
    review_note: str
    review_updated_at: str


class JobMatchReportBatchQueueListResponse(BaseModel):
    batches: list[JobMatchReportBatchQueueFile]
    count: int
    directory: str
    warnings: list[str]


class JobMatchReportBatchQueueContentResponse(JobMatchReportBatchQueueFile):
    queries: list[str]
    generated_reports: list[JobMatchBatchReportItem]
    failures: list[JobMatchBatchReportFailure]
    content: str


class JobMatchReportBatchReviewUpdateRequest(BaseModel):
    review_status: str
    review_note: str = ""


class JobMatchReportBatchReviewUpdateResponse(JobMatchReportBatchQueueContentResponse):
    warnings: list[str]


class JobMatchReportBatchDeleteResponse(BaseModel):
    deleted: bool
    file_name: str
    relative_path: str
    warnings: list[str]


class InterviewQuestion(BaseModel):
    question_id: int
    question: str
    requirement: str
    intent: str
    answer_checkpoints: list[str]
    risk_reminder: str
    type: str = "open"
    difficulty: str = ""
    skill_area: str = ""
    options: list[dict[str, str]] = Field(default_factory=list)
    correct_answer: str | list[str] = ""
    explanation: str = ""
    source_requirement_id: str = ""
    source_requirement: str = ""
    source_refs: list[dict[str, str]] = Field(default_factory=list)
    risk_hint: str = ""


class InterviewSession(BaseModel):
    target_confirmation: JobTargetConfirmation
    generation_mode: str = ""
    generation_model: str = ""
    generation_seconds: float = 0.0
    llm_attempted: bool = False
    llm_repair_attempted: bool = False
    fallback_reason: str = ""
    fallback_detail: str = ""
    validation_errors: list[str] = Field(default_factory=list)
    questions: list[InterviewQuestion]
    answer_guidance: list[str]
    safety_notes: list[str]


class JobInterviewSessionResponse(BaseModel):
    matched: bool
    query: str
    target_job: JobBasicInfo | None
    current_resume: DocumentInfo | None
    session: InterviewSession | None
    warnings: list[str]
    generation_mode: str = ""
    generation_model: str = ""
    generation_seconds: float = 0.0
    llm_attempted: bool = False
    llm_repair_attempted: bool = False
    fallback_reason: str = ""
    fallback_detail: str = ""
    validation_errors: list[str] = Field(default_factory=list)


class InterviewFeedbackRequest(BaseModel):
    query: str
    question_id: int
    answer: str


class InterviewFeedback(BaseModel):
    summary: str
    clarity: str
    evidence_strength: str
    boundary_risk: str
    strengths: list[str]
    improvements: list[str]
    risk_flags: list[str]
    suggested_next_answer_shape: list[str]


class JobInterviewFeedbackResponse(BaseModel):
    matched: bool
    query: str
    target_job: JobBasicInfo | None
    question: InterviewQuestion | None
    feedback: InterviewFeedback | None
    warnings: list[str]


class AgentStatusItem(BaseModel):
    step: str
    label: str
    status: str
    detail: str


class AgentAction(BaseModel):
    action: str
    label: str
    endpoint: str


class DisabledAgentAction(BaseModel):
    action: str
    reason: str


class AgentDraftPreview(BaseModel):
    requirements_count: int
    responsibilities_count: int
    can_write_count: int
    requires_evidence_count: int
    interview_only_count: int
    cannot_claim_count: int
    evidence_gaps: list[str]


class AgentInterviewPreview(BaseModel):
    question_count: int
    first_question: str
    answer_guidance: list[str]


class JobAgentSummary(BaseModel):
    target_confirmation: JobTargetConfirmation
    pipeline_status: list[AgentStatusItem]
    available_actions: list[AgentAction]
    disabled_actions: list[DisabledAgentAction]
    draft_preview: AgentDraftPreview
    interview_preview: AgentInterviewPreview
    safety_notes: list[str]
    recommended_next_steps: list[str]


class JobAgentSummaryResponse(BaseModel):
    matched: bool
    query: str
    target_job: JobBasicInfo | None
    current_resume: DocumentInfo | None
    summary: JobAgentSummary | None
    warnings: list[str]


class AskResponse(BaseModel):
    answer: str
    truncated: bool
    sources: list[SourceInfo]
    retrieval_seconds: float
    generation_seconds: float
    mode: str
    artifacts: list[ChatArtifact] = Field(default_factory=list)


class IndexResponse(BaseModel):
    changed_sources: list[str]
    skipped_sources: list[str]
    removed_sources: list[str]
    written_points: int
    collection_name: str
    storage_path: str
    logs: list[str]
