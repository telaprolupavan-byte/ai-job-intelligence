"use client";

import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { apiRequest, ApiError, API_URL } from "@/lib/api";
import { getAuthToken } from "@/lib/auth";
import Container from "@/components/app/container";
import AppButton from "@/components/app/app-button";
import ErrorState from "@/components/app/error-state";
import EmptyState from "@/components/app/empty-state";
import Badge from "@/components/app/badge";
import { PanelSkeleton } from "@/components/app/skeleton";
import GeneralResumeSection from "@/components/app/general-resume-section";
import { FileText, UploadCloud } from "lucide-react";

type Resume = {
  id: string;
  filename: string;
  created_at: string;
  has_text: boolean;
  version_count: number;
  master_version_id: string | null;
  master_version_name: string | null;
  master_version_created_at: string | null;
};

type ResumeVersion = {
  id: string;
  resume_id: string;
  name: string;
  original_filename: string;
  content_text: string;
  is_master: boolean;
  has_analysis: boolean;
  created_at: string;
  // "upload", "improvement" (AJI-021) or "general_improvement" (AJI-027).
  source?: string;
};

type SavedAnalysisResponse = {
  id: string;
  resume_version_id: string;
  analysis_version: string;
  analyzer_version: string;
  model_provider: string | null;
  model_name: string | null;
  prompt_version: string;
  analysis_result: ResumeAnalysis;
  created_at: string;
};

type ResumeUploadResponse = {
  id: string;
  version_id: string;
  filename: string;
  version_name: string;
  created_at: string;
  valid: boolean;
  word_count: number;
  character_count: number;
  section_matches: string[];
  warnings: string[];
  is_new_resume: boolean;
  duplicate: boolean;
};

const ACCEPTED_RESUME_EXTENSIONS = [".pdf", ".docx"];
const MAX_RESUME_FILE_SIZE = 10 * 1024 * 1024;


type ResumeFinding = {
  category: string;
  priority: "high" | "medium" | "low";
  finding: string;
  evidence: string;
  impact: string;
  recommendation: string;
  confidence: "high" | "medium" | "low";
};

type ResumeReview = {
  strengths: string[];
  weaknesses: string[];
  findings: ResumeFinding[];
  suggestions: string[];
};

type SkillEvidence = {
  skill: string;
  evidence: string;
  demonstrated: boolean;
};

type WorkHistoryEntry = {
  company?: string | null;
  title?: string | null;
  duration?: string | null;
  summary?: string | null;
};

type EducationEntry = {
  institution?: string | null;
  credential?: string | null;
  field_of_study?: string | null;
  graduation?: string | null;
};

type ProjectEntry = {
  name: string;
  description: string;
  technologies: string[];
};

type ResumeDecoding = {
  professional_profile?: string | null;
  technical_profile?: string | null;
  work_history: WorkHistoryEntry[];
  education: EducationEntry[];
  certifications: string[];
  projects: ProjectEntry[];
  skills: SkillEvidence[];
  domains: string[];
};

type RoleMatch = {
  role: string;
  rationale: string;
};

type PositionIdentification = {
  primary_roles: RoleMatch[];
  secondary_roles: RoleMatch[];
  adjacent_roles: RoleMatch[];
  supporting_evidence: string[];
};

type ResumeAnalysis = {
  analysis_version: string;
  resume_version_id: string;
  review: ResumeReview;
  decoding: ResumeDecoding;
  position_identification: PositionIdentification;
};

async function authenticatedRequest<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs?: number,
): Promise<T> {
  const token = getAuthToken();

  return apiRequest<T>(
    path,
    {
      ...options,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers ?? {}),
      },
    },
    timeoutMs,
  );
}

// The backend bounds its own OpenAI call to a 60s timeout with one retry
// (see apps/api/services/resume_ai/providers/openai_provider.py), so a
// legitimate in-progress analysis can take up to ~120s before the backend
// itself responds. This client-side ceiling sits comfortably above that
// worst case - it exists to guarantee the "Analyzing Resume..." state
// always clears, not to race the backend's own timeout.
const ANALYZE_RESUME_TIMEOUT_MS = 150_000;

function isPdf(filename: string) {
  return filename.toLowerCase().endsWith(".pdf");
}

// AJI-027: a General Resume Intelligence version is generated from text
// and has no stored document, so it is viewed as text and has nothing to
// download.
function isGeneralRefinement(version: ResumeVersion) {
  return version.source === "general_improvement";
}

function opensAsPdf(version: ResumeVersion) {
  return isPdf(version.original_filename) && !isGeneralRefinement(version);
}

function formatSectionList(sections: string[]): string {
  const labels = sections.map(
    (section) => section.charAt(0).toUpperCase() + section.slice(1),
  );

  if (labels.length === 1) {
    return labels[0];
  }

  return `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
}

async function fetchResumeVersionFile(
  versionId: string,
): Promise<Blob> {
  const token = getAuthToken();

  const response = await fetch(
    `${API_URL}/resumes/versions/${versionId}/file`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  );

  if (!response.ok) {
    throw new ApiError(
      "Unable to retrieve the resume file.",
      response.status,
    );
  }

  return response.blob();
}

export default function Page() {
  const router = useRouter();

  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<string>("");
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string>("");

  const [analysis, setAnalysis] = useState<ResumeAnalysis | null>(null);

  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadTargetResumeId, setUploadTargetResumeId] = useState("");
  const [uploadVersionName, setUploadVersionName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] =
    useState<ResumeUploadResponse | null>(null);

  const [fileActionError, setFileActionError] = useState<string | null>(null);
  const [fileActionBusy, setFileActionBusy] = useState<
    "view" | "download" | null
  >(null);
  const [showExtractedText, setShowExtractedText] = useState(false);

  // Every load of the versions list is explicitly triggered by a
  // specific user action (initial load, selecting a resume, or a
  // successful upload) rather than by a useEffect cascading off
  // selectedResumeId. That effect-based approach previously allowed two
  // requests to race (e.g. an upload's explicit reload competing with
  // the effect firing off the resume-list reload), and whichever
  // resolved last would silently win, sometimes discarding the version
  // that should have ended up selected. requestIdRef guards against any
  // remaining overlap by only applying the most recently *started*
  // request's result.
  const versionsRequestIdRef = useRef(0);

  const loadVersions = useCallback(
    (resumeId: string, preferredVersionId?: string) => {
      if (!resumeId) {
        return;
      }

      const requestId = ++versionsRequestIdRef.current;

      startTransition(async () => {
        try {
          const versionData = await authenticatedRequest<ResumeVersion[]>(
            `/resumes/${resumeId}/versions`,
          );

          if (requestId !== versionsRequestIdRef.current) {
            return;
          }

          setVersions(versionData);

          const preferredVersion =
            versionData.find(
              (version) => version.id === preferredVersionId,
            ) ??
            versionData.find((version) => version.is_master) ??
            versionData[0];

          setSelectedVersionId(preferredVersion ? preferredVersion.id : "");
          setAnalysis(null);
          setShowExtractedText(false);
        } catch (err) {
          if (requestId !== versionsRequestIdRef.current) {
            return;
          }

          setError(
            err instanceof Error
              ? err.message
              : "Unable to load resume versions.",
          );
        }
      });
    },
    [startTransition],
  );

  const loadResumes = useCallback(
    (preferredResumeId?: string, preferredVersionId?: string) => {
      if (!getAuthToken()) {
        router.replace("/login");
        return;
      }

      startTransition(async () => {
        try {
          const resumeData =
            await authenticatedRequest<Resume[]>("/resumes");
          setResumes(resumeData);
          setError(null);

          if (resumeData.length === 0) {
            setSelectedResumeId("");
            setVersions([]);
            setSelectedVersionId("");
            return;
          }

          const nextResume =
            resumeData.find((resume) => resume.id === preferredResumeId) ??
            resumeData[0];

          setSelectedResumeId(nextResume.id);
          loadVersions(nextResume.id, preferredVersionId);
        } catch (err) {
          if (err instanceof ApiError && [401, 403].includes(err.status)) {
            router.replace("/login");
            return;
          }

          setError(
            err instanceof Error
              ? err.message
              : "Unable to load your resumes.",
          );
        }
      });
    },
    [router, startTransition, loadVersions],
  );

  useEffect(() => {
    loadResumes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectResume(resumeId: string) {
    setSelectedResumeId(resumeId);
    loadVersions(resumeId);
  }

  function validateSelectedFile(file: File): string | null {
    const extension = file.name
      .slice(file.name.lastIndexOf("."))
      .toLowerCase();

    if (!ACCEPTED_RESUME_EXTENSIONS.includes(extension)) {
      return "Only PDF and DOCX resumes are supported.";
    }

    if (file.size > MAX_RESUME_FILE_SIZE) {
      return "Resume file must be 10 MB or smaller.";
    }

    return null;
  }

  function handleFileSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;

    setUploadSuccess(null);
    setUploadError(null);

    if (!file) {
      setSelectedFile(null);
      return;
    }

    const validationError = validateSelectedFile(file);

    if (validationError) {
      setSelectedFile(null);
      setUploadError(validationError);
      event.target.value = "";
      return;
    }

    setSelectedFile(file);
  }

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();

    if (!selectedFile) {
      return;
    }

    try {
      setUploading(true);
      setUploadError(null);
      setUploadSuccess(null);

      const formData = new FormData();
      formData.append("file", selectedFile);

      if (uploadTargetResumeId) {
        formData.append("resume_id", uploadTargetResumeId);
      }

      if (uploadVersionName.trim()) {
        formData.append("version_name", uploadVersionName.trim());
      }

      const result = await authenticatedRequest<ResumeUploadResponse>(
        "/resumes/upload",
        {
          method: "POST",
          body: formData,
        },
      );

      setUploadSuccess(result);
      setSelectedFile(null);
      setUploadVersionName("");

      // loadResumes refreshes the resume list and then explicitly loads
      // this resume's versions, preferring the version just uploaded
      // (whether it's a brand-new resume's first version or a new
      // version on an existing resume).
      loadResumes(result.id, result.version_id);
    } catch (err) {
      setUploadError(
        err instanceof Error
          ? err.message
          : "Resume upload failed. Please try again.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function analyzeResume() {
    if (!selectedVersionId) {
      return;
    }

    try {
      setAnalyzing(true);
      setError(null);
      setAnalysis(null);

      const result = await authenticatedRequest<ResumeAnalysis>(
        `/resumes/versions/${selectedVersionId}/ai-analysis`,
        {
          method: "POST",
        },
        ANALYZE_RESUME_TIMEOUT_MS,
      );

      setAnalysis(result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Resume analysis failed.",
      );
    } finally {
      setAnalyzing(false);
    }
  }

  const selectedVersion = versions.find(
    (version) => version.id === selectedVersionId,
  );

  useEffect(() => {
    if (!selectedVersionId) {
      return;
    }

    let cancelled = false;

    async function loadSavedAnalysis() {
      try {
        setError(null);

        const savedAnalysis =
          await authenticatedRequest<SavedAnalysisResponse>(
            `/resumes/versions/${selectedVersionId}/ai-analysis`,
          );

        if (!cancelled) {
          setAnalysis(savedAnalysis.analysis_result);
        }
      } catch (err) {
        if (cancelled) {
          return;
        }

        // A 404 means this version has not been analyzed yet.
        if (err instanceof ApiError && err.status === 404) {
          setAnalysis(null);
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load saved resume analysis.",
        );
      }
    }

    loadSavedAnalysis();

    return () => {
      cancelled = true;
    };
  }, [selectedVersionId]);

  async function handleView() {
    if (!selectedVersion) {
      return;
    }

    setFileActionError(null);

    if (!opensAsPdf(selectedVersion)) {
      setShowExtractedText((value) => !value);
      return;
    }

    try {
      setFileActionBusy("view");
      const blob = await fetchResumeVersionFile(selectedVersion.id);
      const objectUrl = URL.createObjectURL(blob);

      // Deliberately omit "noopener": a blob: URL is only resolvable
      // within the browsing context that created it, and "noopener"
      // forces the new tab into an isolated context that can't resolve
      // it (the tab opens blank).
      const newTab = window.open(objectUrl, "_blank");

      if (!newTab) {
        URL.revokeObjectURL(objectUrl);
        setFileActionError(
          "Your browser blocked this popup. Please allow popups for " +
            "this site and try again.",
        );
      } else {
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
      }
    } catch (err) {
      setFileActionError(
        err instanceof Error
          ? err.message
          : "Unable to open the resume file.",
      );
    } finally {
      setFileActionBusy(null);
    }
  }

  async function handleDownload() {
    if (!selectedVersion) {
      return;
    }

    setFileActionError(null);

    try {
      setFileActionBusy("download");
      const blob = await fetchResumeVersionFile(selectedVersion.id);
      const objectUrl = URL.createObjectURL(blob);

      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = selectedVersion.original_filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);

      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setFileActionError(
        err instanceof Error
          ? err.message
          : "Unable to download the resume file.",
      );
    } finally {
      setFileActionBusy(null);
    }
  }

  const selectedResume = resumes.find(
    (resume) => resume.id === selectedResumeId,
  );

  // Resolved independently from the analysis payload's own
  // resume_version_id (rather than assumed to be "whatever is currently
  // selected") so the AI Analysis section always labels itself with the
  // resume/version it actually belongs to, even for a moment during a
  // version switch.
  const analysisVersion = analysis
    ? versions.find((version) => version.id === analysis.resume_version_id)
    : undefined;
  const analysisResume = analysisVersion
    ? resumes.find((resume) => resume.id === analysisVersion.resume_id)
    : undefined;

  return (
    <div className="bg-app-bg text-app-text">
      <Container>
        <header className="border-b border-app-border pb-6">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-app-red">
            Intelligence Module / AJI-005
          </div>

          <h1 className="mt-3 font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight sm:text-3xl">
            Resume Intelligence
          </h1>

          <p className="mt-3 max-w-2xl text-sm leading-7 text-app-muted">
            Manage multiple resumes and versions, and run evidence-backed
            analysis of positioning, skills, experience, technical depth,
            structure, and improvement priorities.
          </p>
        </header>

        <section className="mt-8 rounded-xl border border-app-border bg-app-panel p-6">
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-app-blue">
            <UploadCloud className="h-3.5 w-3.5" aria-hidden="true" />
            Resume Workspace
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_320px]">
            <form
              onSubmit={handleUpload}
              className="rounded-2xl border border-app-border bg-app-bg p-6 sm:p-8"
            >
              <h2 className="text-xl font-bold text-app-text sm:text-2xl">
                {resumes.length === 0
                  ? "Drop your resume here"
                  : "Add a new resume or version"}
              </h2>

              <p className="mt-2 text-sm text-app-muted">
                PDF or DOCX • Your file stays under your control
              </p>

              <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center">
                <label className="flex-1">
                  <span className="sr-only">Choose resume file</span>
                  <input
                    type="file"
                    accept=".pdf,.docx"
                    onChange={handleFileSelected}
                    disabled={uploading}
                    className="w-full rounded-lg border border-app-border-strong bg-app-panel px-4 py-3 text-sm text-app-text outline-none file:mr-4 file:cursor-pointer file:rounded-[10px] file:border-0 file:bg-crimson-fill file:px-4 file:py-2 file:text-xs file:font-bold file:text-white hover:file:bg-crimson-fill-hover focus:border-app-blue disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </label>

                <AppButton
                  type="submit"
                  disabled={!selectedFile || uploading}
                  loading={uploading}
                >
                  {uploading ? "Uploading..." : "Upload"}
                </AppButton>
              </div>

              {resumes.length > 0 && (
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div>
                    <label
                      htmlFor="upload-target"
                      className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-muted"
                    >
                      Add as
                    </label>
                    <select
                      id="upload-target"
                      value={uploadTargetResumeId}
                      onChange={(event) =>
                        setUploadTargetResumeId(event.target.value)
                      }
                      disabled={uploading}
                      className="mt-2 w-full rounded-lg border border-app-border-strong bg-app-panel px-4 py-3 text-sm text-app-text outline-none focus:border-app-blue"
                    >
                      <option value="">New Resume</option>
                      {resumes.map((resume) => (
                        <option key={resume.id} value={resume.id}>
                          New version of &quot;{resume.filename}&quot;
                        </option>
                      ))}
                    </select>
                  </div>

                  {uploadTargetResumeId && (
                    <div>
                      <label
                        htmlFor="upload-version-name"
                        className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-muted"
                      >
                        Version Label (optional)
                      </label>
                      <input
                        id="upload-version-name"
                        type="text"
                        value={uploadVersionName}
                        onChange={(event) =>
                          setUploadVersionName(event.target.value)
                        }
                        disabled={uploading}
                        placeholder="e.g. Updated, Tailored"
                        maxLength={255}
                        className="mt-2 w-full rounded-lg border border-app-border-strong bg-app-panel px-4 py-3 text-sm text-app-text outline-none focus:border-app-blue"
                      />
                    </div>
                  )}
                </div>
              )}

              {selectedFile && !uploading && (
                <div className="mt-3 font-mono text-[9px] uppercase tracking-wider text-app-faint">
                  SELECTED FILE: {selectedFile.name}
                </div>
              )}

              {uploadError && (
                <div className="mt-5">
                  <ErrorState title="Upload Error" message={uploadError} />
                </div>
              )}

              <p className="mt-6 text-xs leading-5 text-app-muted">
                NERO analyzes the document to help you understand and
                improve it. No changes are applied without approval.
              </p>
            </form>

            <div className="flex flex-col gap-4">
              <div className="relative overflow-hidden rounded-xl border border-app-border bg-app-bg p-5 pl-6">
                <span
                  className="absolute left-0 top-0 h-full w-1 bg-app-amber"
                  aria-hidden="true"
                />
                <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-faint">
                  Current status
                </div>
                <p className="mt-2 text-sm leading-6 text-app-body">
                  {resumes.length === 0
                    ? "No resume analyzed yet. Upload a file to start."
                    : `${resumes.length} resume${resumes.length === 1 ? "" : "s"} on file.`}
                </p>
              </div>

              <div className="relative overflow-hidden rounded-xl border border-app-border bg-app-bg p-5 pl-6">
                <span
                  className="absolute left-0 top-0 h-full w-1 bg-app-blue"
                  aria-hidden="true"
                />
                <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-faint">
                  What happens next
                </div>
                <p className="mt-2 text-sm font-bold text-app-text">
                  1 Validate
                </p>
                <p className="mt-1 text-sm leading-6 text-app-body">
                  Structure and parsing checks → ATS alignment → review
                  improvements.
                </p>
              </div>
            </div>
          </div>

          {uploadSuccess && (
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="relative overflow-hidden rounded-xl border border-app-border bg-app-bg p-5 pl-6">
                <span
                  className="absolute left-0 top-0 h-full w-1 bg-app-success"
                  aria-hidden="true"
                />
                <div className="text-base font-bold text-app-text">
                  {uploadSuccess.duplicate
                    ? "Resume already on file"
                    : "Document parsed successfully"}
                </div>
                <p className="mt-2 text-sm leading-6 text-app-body">
                  {uploadSuccess.duplicate
                    ? `This exact resume content already exists as "${uploadSuccess.version_name}" (${uploadSuccess.word_count} words). No duplicate was created.`
                    : `${uploadSuccess.filename} was stored as "${uploadSuccess.version_name}" — ${uploadSuccess.word_count} words, ${uploadSuccess.character_count} characters.`}
                </p>
              </div>

              <div className="relative overflow-hidden rounded-xl border border-app-border bg-app-bg p-5 pl-6">
                <span
                  className={`absolute left-0 top-0 h-full w-1 ${
                    uploadSuccess.section_matches.length > 0
                      ? "bg-app-success"
                      : "bg-app-amber"
                  }`}
                  aria-hidden="true"
                />
                <div className="text-base font-bold text-app-text">
                  Sections detected
                </div>
                <p className="mt-2 text-sm leading-6 text-app-body">
                  {uploadSuccess.section_matches.length > 0
                    ? `${formatSectionList(uploadSuccess.section_matches)} detected.`
                    : "No standard resume sections were detected. Review formatting before relying on analysis."}
                </p>
              </div>
            </div>
          )}

          {uploadSuccess && !uploadSuccess.duplicate && (
            <div className="mt-6 flex flex-col items-start justify-between gap-4 border-t border-app-border pt-6 sm:flex-row sm:items-center">
              <div className="text-sm font-bold text-app-text">
                Continue to ATS alignment
              </div>
              <AppButton href="/jobs" className="normal-case tracking-normal">
                Continue analysis
              </AppButton>
            </div>
          )}

          <div className="mt-8 border-t border-app-border pt-5">
            <div className="flex flex-wrap items-center gap-x-10 gap-y-2 font-mono text-[11px] uppercase tracking-wider">
              <span
                className={
                  resumes.length > 0 ? "text-app-text" : "text-app-faint"
                }
              >
                1 Upload
              </span>
              <span
                className={
                  uploadSuccess ? "text-app-text" : "text-app-faint"
                }
              >
                2 Validate
              </span>
              <span className="text-app-faint">3 Analyze</span>
              <span className="text-app-faint">4 Approve</span>
            </div>
          </div>
        </section>

        <section className="mt-8 rounded-xl border border-app-border bg-app-panel p-6">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-soft">
            My Resumes
          </div>

          {isPending && resumes.length === 0 ? (
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <PanelSkeleton key={index} lines={2} />
              ))}
            </div>
          ) : resumes.length === 0 ? (
            <div className="mt-6">
              <EmptyState
                icon={FileText}
                title="No resume uploaded"
                description="Upload a resume before running Resume Intelligence analysis."
              />
            </div>
          ) : (
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {resumes.map((resume) => {
                const isSelected = resume.id === selectedResumeId;

                return (
                  <button
                    key={resume.id}
                    type="button"
                    onClick={() => selectResume(resume.id)}
                    className={`rounded-lg border p-5 text-left transition ${
                      isSelected
                        ? "border-app-blue bg-app-blue/10"
                        : "border-app-border bg-app-bg hover:border-app-border-strong"
                    }`}
                  >
                    <div className="truncate text-base font-semibold">
                      {resume.filename}
                    </div>

                    <div className="mt-2 font-mono text-[9px] uppercase tracking-wider text-app-faint">
                      Uploaded{" "}
                      {new Date(resume.created_at).toLocaleDateString()}
                    </div>

                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Badge>
                        {resume.version_count}{" "}
                        {resume.version_count === 1 ? "version" : "versions"}
                      </Badge>

                      {resume.master_version_name && (
                        <Badge tone="blue">
                          Master: {resume.master_version_name}
                        </Badge>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {error && (
            <div className="mt-5">
              <ErrorState message={error} />
            </div>
          )}
        </section>

        {selectedResume && (
          <>
            <section className="mt-8 rounded-xl border border-app-border bg-app-panel p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-soft">
                Selected Resume
              </div>

              <h2 className="mt-3 text-2xl font-bold">
                {selectedVersion?.original_filename ?? selectedResume.filename}
              </h2>

              {selectedVersion && (
                <div className="mt-2 flex flex-wrap items-center gap-3 font-mono text-[9px] uppercase tracking-wider text-app-faint">
                  <span>{selectedVersion.name}</span>
                  {selectedVersion.is_master && (
                    <span className="text-app-blue">Master</span>
                  )}
                  <span>
                    Created{" "}
                    {new Date(
                      selectedVersion.created_at,
                    ).toLocaleDateString()}
                  </span>
                  <span
                    className={
                      selectedVersion.has_analysis
                        ? "text-app-blue"
                        : "text-app-faint"
                    }
                  >
                    AI Analysis:{" "}
                    {selectedVersion.has_analysis
                      ? "Available"
                      : "Not yet analyzed"}
                  </span>
                </div>
              )}

              <div className="mt-5">
                <label
                  htmlFor="resume-version"
                  className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-muted"
                >
                  Resume Version
                </label>

                <select
                  id="resume-version"
                  value={selectedVersionId}
                  onChange={(event) => {
                    setSelectedVersionId(event.target.value);
                    setAnalysis(null);
                    setShowExtractedText(false);
                  }}
                  className="mt-2 w-full rounded-lg border border-app-border-strong bg-app-bg px-4 py-3 text-sm text-app-text outline-none focus:border-app-blue"
                >
                  {versions.map((version) => (
                    <option key={version.id} value={version.id}>
                      {version.name}
                      {version.is_master ? " — Master" : ""}
                      {version.source === "general_improvement"
                        ? " — General refinement"
                        : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <AppButton
                  variant="secondary"
                  onClick={handleView}
                  disabled={!selectedVersion || fileActionBusy !== null}
                  loading={fileActionBusy === "view"}
                >
                  {fileActionBusy === "view"
                    ? "Opening..."
                    : selectedVersion && opensAsPdf(selectedVersion)
                      ? "View Resume"
                      : showExtractedText
                        ? "Hide Extracted Text"
                        : "View Extracted Text"}
                </AppButton>

                <AppButton
                  variant="secondary"
                  onClick={handleDownload}
                  disabled={
                    !selectedVersion ||
                    isGeneralRefinement(selectedVersion) ||
                    fileActionBusy !== null
                  }
                  loading={fileActionBusy === "download"}
                >
                  {fileActionBusy === "download"
                    ? "Downloading..."
                    : "Download"}
                </AppButton>

                <AppButton
                  onClick={analyzeResume}
                  disabled={!selectedVersionId || analyzing}
                  loading={analyzing}
                >
                  {analyzing ? "Analyzing Resume..." : "Analyze Resume"}
                </AppButton>
              </div>

              {fileActionError && (
                <div className="mt-5">
                  <ErrorState message={fileActionError} />
                </div>
              )}

              {showExtractedText &&
                selectedVersion &&
                !opensAsPdf(selectedVersion) && (
                  <div className="mt-5 rounded-lg border border-app-border bg-app-bg p-4">
                    <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                      {isGeneralRefinement(selectedVersion)
                        ? "Refined Version Text (built from your approved edits)"
                        : "Extracted DOCX Content (not the original file layout)"}
                    </div>
                    <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-xs leading-6 text-app-body">
                      {selectedVersion.content_text}
                    </pre>
                  </div>
                )}
            </section>

            {selectedVersion && (
              <GeneralResumeSection
                key={selectedVersion.id}
                versionId={selectedVersion.id}
                onOpenVersion={(versionId) =>
                  loadVersions(selectedResumeId, versionId)
                }
              />
            )}

            <section className="mt-8 rounded-xl border border-app-border bg-app-panel p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-soft">
                Version History
              </div>

              {versions.length === 0 ? (
                <p className="mt-5 text-sm text-app-faint">
                  No versions found for this resume.
                </p>
              ) : (
                <div className="mt-5 space-y-3">
                  {versions.map((version) => (
                    <div
                      key={version.id}
                      className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4 ${
                        version.id === selectedVersionId
                          ? "border-app-blue bg-app-blue/5"
                          : "border-app-border"
                      }`}
                    >
                      <div>
                        <div className="text-sm font-semibold">
                          {version.name}
                          {version.is_master && (
                            <span className="ml-2 font-mono text-[9px] uppercase tracking-wider text-app-blue">
                              Master
                            </span>
                          )}
                        </div>
                        <div className="mt-1 font-mono text-[9px] uppercase tracking-wider text-app-faint">
                          {version.original_filename} · Created{" "}
                          {new Date(version.created_at).toLocaleDateString()}
                          {version.source === "general_improvement" &&
                            " · General refinement"}
                          {" · "}
                          <span
                            className={
                              version.has_analysis
                                ? "text-app-blue"
                                : "text-app-faint"
                            }
                          >
                            {version.has_analysis
                              ? "AI Analysis Available"
                              : "Not Yet Analyzed"}
                          </span>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => {
                          setSelectedVersionId(version.id);
                          setAnalysis(null);
                          setShowExtractedText(false);
                        }}
                        disabled={version.id === selectedVersionId}
                        className="rounded-lg border border-app-border-strong px-4 py-2 text-[10px] font-bold uppercase tracking-[0.15em] text-app-text transition hover:border-app-blue disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {version.id === selectedVersionId
                          ? "Selected"
                          : "Select"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}

        {analysis && (
          <div className="mt-8 space-y-8">
            <section className="rounded-xl border border-app-border bg-app-panel p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-blue">
                Resume Intelligence
              </div>

              <div className="mt-4 grid gap-4 rounded-lg border border-app-border bg-app-bg p-4 sm:grid-cols-2">
                <div>
                  <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                    Resume
                  </div>
                  <div className="mt-1 text-sm font-semibold">
                    {analysisResume?.filename ??
                      selectedResume?.filename ??
                      "Unknown resume"}
                  </div>
                </div>

                <div>
                  <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                    Version
                  </div>
                  <div className="mt-1 text-sm font-semibold">
                    {analysisVersion
                      ? `${analysisVersion.name}${
                          analysisVersion.is_master ? " — Master" : ""
                        }`
                      : "Unknown version"}
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-xl border border-app-border bg-app-panel p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-blue">
                Resume Review
              </div>

              <div className="mt-6 grid gap-6 md:grid-cols-2">
                <ListBlock
                  title="Strengths"
                  items={analysis.review.strengths}
                />

                <ListBlock
                  title="Weaknesses"
                  items={analysis.review.weaknesses}
                />
              </div>

              <div className="mt-6 font-mono text-[9px] uppercase tracking-wider text-app-faint">
                Findings
              </div>

              {analysis.review.findings.length === 0 ? (
                <p className="mt-5 text-sm text-app-muted">
                  No findings were returned for this analysis.
                </p>
              ) : (
                <div className="mt-6 space-y-5">
                  {analysis.review.findings.map((finding, index) => (
                    <article
                      key={`${finding.category}-${index}`}
                      className="rounded-lg border border-app-border bg-app-bg p-5"
                    >
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-red">
                          {finding.priority}
                        </span>

                        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                          {finding.category}
                        </span>

                        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                          CONFIDENCE: {finding.confidence}
                        </span>
                      </div>

                      <h3 className="mt-4 text-lg font-semibold">
                        {finding.finding}
                      </h3>

                      <FindingField
                        label="Evidence"
                        value={finding.evidence}
                      />

                      <FindingField
                        label="Impact"
                        value={finding.impact}
                      />

                      <FindingField
                        label="Recommendation"
                        value={finding.recommendation}
                      />
                    </article>
                  ))}
                </div>
              )}

              <div className="mt-8">
                <ListBlock
                  title="Suggestions"
                  items={analysis.review.suggestions}
                />
              </div>
            </section>

            <section className="rounded-xl border border-app-border bg-app-panel p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-blue">
                Resume Decoding
              </div>

              <div className="mt-6 grid gap-5 md:grid-cols-2">
                <InfoBlock
                  label="Professional Profile"
                  value={
                    analysis.decoding.professional_profile ??
                    "Not identified"
                  }
                />

                <InfoBlock
                  label="Technical Profile"
                  value={
                    analysis.decoding.technical_profile ?? "Not identified"
                  }
                />
              </div>

              <div className="mt-8 grid gap-8 md:grid-cols-2">
                <EntryListBlock
                  title="Work History"
                  entries={analysis.decoding.work_history}
                  render={(entry) => (
                    <>
                      <div className="text-sm font-semibold text-app-text">
                        {[entry.title, entry.company]
                          .filter(Boolean)
                          .join(" · ") || "Unlabeled role"}
                      </div>
                      {entry.duration && (
                        <div className="mt-1 font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                          {entry.duration}
                        </div>
                      )}
                      {entry.summary && (
                        <p className="mt-2 text-sm leading-6 text-app-body">
                          {entry.summary}
                        </p>
                      )}
                    </>
                  )}
                />

                <EntryListBlock
                  title="Education"
                  entries={analysis.decoding.education}
                  render={(entry) => (
                    <>
                      <div className="text-sm font-semibold text-app-text">
                        {[entry.credential, entry.field_of_study]
                          .filter(Boolean)
                          .join(" · ") || "Unlabeled credential"}
                      </div>
                      {entry.institution && (
                        <div className="mt-1 text-sm text-app-body">
                          {entry.institution}
                        </div>
                      )}
                      {entry.graduation && (
                        <div className="mt-1 font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                          {entry.graduation}
                        </div>
                      )}
                    </>
                  )}
                />

                <EntryListBlock
                  title="Projects"
                  entries={analysis.decoding.projects}
                  render={(entry) => (
                    <>
                      <div className="text-sm font-semibold text-app-text">
                        {entry.name}
                      </div>
                      <p className="mt-2 text-sm leading-6 text-app-body">
                        {entry.description}
                      </p>
                      {entry.technologies.length > 0 && (
                        <div className="mt-2 font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                          {entry.technologies.join(" • ")}
                        </div>
                      )}
                    </>
                  )}
                />

                <div className="space-y-8">
                  <ListBlock
                    title="Certifications"
                    items={analysis.decoding.certifications}
                  />

                  <ListBlock
                    title="Domains"
                    items={analysis.decoding.domains}
                  />
                </div>
              </div>

              <div className="mt-8 rounded-lg border border-app-border bg-app-bg p-5">
                <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-soft">
                  Skills
                </div>

                {analysis.decoding.skills.length === 0 ? (
                  <p className="mt-4 text-sm text-app-faint">
                    No skills identified.
                  </p>
                ) : (
                  <ul className="mt-4 space-y-4">
                    {analysis.decoding.skills.map((skill, index) => (
                      <li
                        key={`${skill.skill}-${index}`}
                        className="border-l border-app-border-strong pl-4"
                      >
                        <div className="flex flex-wrap items-center gap-3">
                          <span className="text-sm font-semibold text-app-text">
                            {skill.skill}
                          </span>
                          <span
                            className={`font-mono text-[9px] uppercase tracking-[0.15em] ${
                              skill.demonstrated
                                ? "text-app-blue"
                                : "text-app-faint"
                            }`}
                          >
                            {skill.demonstrated
                              ? "Demonstrated"
                              : "Skills Only"}
                          </span>
                        </div>
                        <p className="mt-1 text-sm leading-6 text-app-body">
                          {skill.evidence}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>

            <section className="rounded-xl border border-app-border bg-app-panel p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-blue">
                Position Identification
              </div>

              <div className="mt-6 grid gap-6 md:grid-cols-3">
                <RoleListBlock
                  title="Primary Roles"
                  roles={analysis.position_identification.primary_roles}
                />

                <RoleListBlock
                  title="Secondary Roles"
                  roles={analysis.position_identification.secondary_roles}
                />

                <RoleListBlock
                  title="Adjacent Roles"
                  roles={analysis.position_identification.adjacent_roles}
                />
              </div>

              <div className="mt-8">
                <ListBlock
                  title="Supporting Evidence"
                  items={
                    analysis.position_identification.supporting_evidence
                  }
                />
              </div>
            </section>
          </div>
        )}
      </Container>
    </div>
  );
}

function InfoBlock({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-app-border bg-app-bg p-5">
      <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
        {label}
      </div>

      <div className="mt-3 text-base font-semibold">{value}</div>
    </div>
  );
}

function ListBlock({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  return (
    <div className="rounded-lg border border-app-border bg-app-bg p-5">
      <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-soft">
        {title}
      </div>

      {items.length === 0 ? (
        <p className="mt-4 text-sm text-app-faint">
          No items identified.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((item, index) => (
            <li
              key={`${item}-${index}`}
              className="border-l border-app-border-strong pl-4 text-sm leading-6 text-app-body"
            >
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EntryListBlock<T>({
  title,
  entries,
  render,
}: {
  title: string;
  entries: T[];
  render: (entry: T) => React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-app-border bg-app-bg p-5">
      <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-soft">
        {title}
      </div>

      {entries.length === 0 ? (
        <p className="mt-4 text-sm text-app-faint">
          No items identified.
        </p>
      ) : (
        <ul className="mt-4 space-y-4">
          {entries.map((entry, index) => (
            <li
              key={index}
              className="border-l border-app-border-strong pl-4"
            >
              {render(entry)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RoleListBlock({
  title,
  roles,
}: {
  title: string;
  roles: { role: string; rationale: string }[];
}) {
  return (
    <div className="rounded-lg border border-app-border bg-app-bg p-5">
      <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-soft">
        {title}
      </div>

      {roles.length === 0 ? (
        <p className="mt-4 text-sm text-app-faint">
          No roles identified.
        </p>
      ) : (
        <ul className="mt-4 space-y-4">
          {roles.map((role, index) => (
            <li
              key={`${role.role}-${index}`}
              className="border-l border-app-border-strong pl-4"
            >
              <div className="text-sm font-semibold text-app-text">
                {role.role}
              </div>
              <p className="mt-1 text-sm leading-6 text-app-body">
                {role.rationale}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function FindingField({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="mt-5">
      <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
        {label}
      </div>

      <p className="mt-2 text-sm leading-6 text-app-body">{value}</p>
    </div>
  );
}

