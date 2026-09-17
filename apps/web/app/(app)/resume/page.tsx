"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { apiRequest, ApiError, API_URL } from "@/lib/api";
import { getAuthToken } from "@/lib/auth";

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
  created_at: string;
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


type ResumeAnalysis = {
  analysis_version: string;
  resume_version_id: string;
  profile: Record<string, unknown>;
  positioning: {
    apparent_target_role?: string | null;
    apparent_specialization?: string | null;
    apparent_seniority?: string | null;
    positioning_strengths: string[];
    positioning_risks: string[];
  };
  sections: Record<string, unknown>;
  skills: Record<string, unknown>;
  experience: Record<string, unknown>;
  technical_depth: Record<string, unknown>;
  structure: Record<string, unknown>;
  findings: {
    category: string;
    priority: "high" | "medium" | "low";
    finding: string;
    evidence: string;
    impact: string;
    recommendation: string;
    confidence: "high" | "medium" | "low";
  }[];
  summary: {
    strengths: string[];
    top_priorities: string[];
  };
};

async function authenticatedRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getAuthToken();

  return apiRequest<T>(path, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
}

function isPdf(filename: string) {
  return filename.toLowerCase().endsWith(".pdf");
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

  const loadResumes = useCallback(
    (preferredResumeId?: string) => {
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
    [router, startTransition],
  );

  useEffect(() => {
    loadResumes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadVersions = useCallback(
    (resumeId: string, preferredVersionId?: string) => {
      if (!resumeId) {
        return;
      }

      startTransition(async () => {
        try {
          const versionData = await authenticatedRequest<ResumeVersion[]>(
            `/resumes/${resumeId}/versions`,
          );

          setVersions(versionData);

          const masterVersion =
            versionData.find(
              (version) => version.id === preferredVersionId,
            ) ??
            versionData.find((version) => version.is_master) ??
            versionData[0];

          setSelectedVersionId(masterVersion ? masterVersion.id : "");
          setAnalysis(null);
          setShowExtractedText(false);
        } catch (err) {
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

  useEffect(() => {
    if (selectedResumeId) {
      loadVersions(selectedResumeId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedResumeId]);

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

      loadResumes(result.id);
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

    if (!isPdf(selectedVersion.original_filename)) {
      setShowExtractedText((value) => !value);
      return;
    }

    try {
      setFileActionBusy("view");
      const blob = await fetchResumeVersionFile(selectedVersion.id);
      const objectUrl = URL.createObjectURL(blob);
      window.open(objectUrl, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
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

  return (
    <main className="min-h-screen bg-[#05070A] px-6 py-10 text-[#F2F5F8]">
      <div className="mx-auto w-full max-w-6xl">
        <header className="border-b border-[#1A3048] pb-8">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-[#E50920]">
            Intelligence Module / AJI-005
          </div>

          <h1 className="mt-4 text-4xl font-bold tracking-tight">
            Resume Intelligence
          </h1>

          <p className="mt-3 max-w-2xl text-sm leading-7 text-[#8D9AAA]">
            Manage multiple resumes and versions, and run evidence-backed
            analysis of positioning, skills, experience, technical depth,
            structure, and improvement priorities.
          </p>
        </header>

        <section className="mt-8 border border-[#1A3048] bg-[#0B1626] p-6">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#71849A]">
            Upload Resume
          </div>

          <p className="mt-2 text-sm text-[#8D9AAA]">
            {resumes.length === 0
              ? "No resume uploaded. Upload a PDF or DOCX to get started."
              : "Upload a new PDF or DOCX as a separate resume, or add it as a new version of an existing resume below."}
          </p>

          <form
            onSubmit={handleUpload}
            className="mt-5 flex flex-col gap-4"
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <label className="flex-1">
                <span className="sr-only">Choose resume file</span>
                <input
                  type="file"
                  accept=".pdf,.docx"
                  onChange={handleFileSelected}
                  disabled={uploading}
                  className="w-full border border-[#294B70] bg-[#05070A] px-4 py-3 text-sm text-[#F2F5F8] outline-none file:mr-4 file:border-0 file:bg-[#1A3048] file:px-3 file:py-1.5 file:text-xs file:font-bold file:uppercase file:tracking-wider file:text-[#F2F5F8] focus:border-[#1677E8] disabled:cursor-not-allowed disabled:opacity-50"
                />
              </label>

              <button
                type="submit"
                disabled={!selectedFile || uploading}
                className="bg-[#E50920] px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] text-white transition hover:bg-[#FF1E32] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {uploading ? "Uploading..." : "Upload"}
              </button>
            </div>

            {resumes.length > 0 && (
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="upload-target"
                    className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#8D9AAA]"
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
                    className="mt-2 w-full border border-[#294B70] bg-[#05070A] px-4 py-3 text-sm text-[#F2F5F8] outline-none focus:border-[#1677E8]"
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
                      className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#8D9AAA]"
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
                      className="mt-2 w-full border border-[#294B70] bg-[#05070A] px-4 py-3 text-sm text-[#F2F5F8] outline-none focus:border-[#1677E8]"
                    />
                  </div>
                )}
              </div>
            )}
          </form>

          {selectedFile && !uploading && (
            <div className="mt-3 font-mono text-[9px] uppercase tracking-wider text-[#5E7187]">
              SELECTED FILE: {selectedFile.name}
            </div>
          )}

          {uploadError && (
            <div className="mt-5 border border-[#E50920]/40 bg-[#E50920]/5 p-4">
              <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#E50920]">
                Upload Error
              </div>

              <p className="mt-2 text-sm text-[#F2F5F8]">{uploadError}</p>
            </div>
          )}

          {uploadSuccess && (
            <div className="mt-5 border border-[#1677E8]/40 bg-[#1677E8]/5 p-4">
              <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#1677E8]">
                {uploadSuccess.duplicate
                  ? "Resume Already Exists"
                  : "Resume Stored Successfully"}
              </div>

              <p className="mt-2 text-sm text-[#F2F5F8]">
                {uploadSuccess.duplicate
                  ? `This exact resume content already exists as "${uploadSuccess.version_name}" (${uploadSuccess.word_count} words). No duplicate was created.`
                  : `${uploadSuccess.filename} was stored as "${uploadSuccess.version_name}" (${uploadSuccess.word_count} words).`}
              </p>
            </div>
          )}
        </section>

        <section className="mt-8 border border-[#1A3048] bg-[#0B1626] p-6">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#71849A]">
            My Resumes
          </div>

          {isPending && resumes.length === 0 ? (
            <div className="mt-6 font-mono text-xs uppercase tracking-wider text-[#5E7187]">
              Loading resumes...
            </div>
          ) : resumes.length === 0 ? (
            <div className="mt-6">
              <div className="text-lg font-semibold">
                No resume uploaded
              </div>

              <p className="mt-2 text-sm text-[#8D9AAA]">
                Upload a resume before running Resume Intelligence analysis.
              </p>
            </div>
          ) : (
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {resumes.map((resume) => {
                const isSelected = resume.id === selectedResumeId;

                return (
                  <button
                    key={resume.id}
                    type="button"
                    onClick={() => setSelectedResumeId(resume.id)}
                    className={`border p-5 text-left transition ${
                      isSelected
                        ? "border-[#1677E8] bg-[#1677E8]/10"
                        : "border-[#1A3048] bg-[#05070A] hover:border-[#294B70]"
                    }`}
                  >
                    <div className="truncate text-base font-semibold">
                      {resume.filename}
                    </div>

                    <div className="mt-2 font-mono text-[9px] uppercase tracking-wider text-[#5E7187]">
                      Uploaded{" "}
                      {new Date(resume.created_at).toLocaleDateString()}
                    </div>

                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className="border border-[#294B70] px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-[#8D9AAA]">
                        {resume.version_count}{" "}
                        {resume.version_count === 1 ? "version" : "versions"}
                      </span>

                      {resume.master_version_name && (
                        <span className="border border-[#1677E8]/60 px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-[#1677E8]">
                          Master: {resume.master_version_name}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {error && (
            <div className="mt-5 border border-[#E50920]/40 bg-[#E50920]/5 p-4">
              <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#E50920]">
                Error
              </div>

              <p className="mt-2 text-sm text-[#F2F5F8]">{error}</p>
            </div>
          )}
        </section>

        {selectedResume && (
          <>
            <section className="mt-8 border border-[#1A3048] bg-[#0B1626] p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#71849A]">
                Selected Resume
              </div>

              <h2 className="mt-3 text-2xl font-bold">
                {selectedVersion?.original_filename ?? selectedResume.filename}
              </h2>

              {selectedVersion && (
                <div className="mt-2 flex flex-wrap items-center gap-3 font-mono text-[9px] uppercase tracking-wider text-[#5E7187]">
                  <span>{selectedVersion.name}</span>
                  {selectedVersion.is_master && (
                    <span className="text-[#1677E8]">Master</span>
                  )}
                  <span>
                    Created{" "}
                    {new Date(
                      selectedVersion.created_at,
                    ).toLocaleDateString()}
                  </span>
                </div>
              )}

              <div className="mt-5">
                <label
                  htmlFor="resume-version"
                  className="font-mono text-[10px] uppercase tracking-[0.15em] text-[#8D9AAA]"
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
                  className="mt-2 w-full border border-[#294B70] bg-[#05070A] px-4 py-3 text-sm text-[#F2F5F8] outline-none focus:border-[#1677E8]"
                >
                  {versions.map((version) => (
                    <option key={version.id} value={version.id}>
                      {version.name}
                      {version.is_master ? " — Master" : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={handleView}
                  disabled={!selectedVersion || fileActionBusy !== null}
                  className="border border-[#294B70] px-5 py-3 text-xs font-bold uppercase tracking-[0.15em] text-[#F2F5F8] transition hover:border-[#1677E8] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {fileActionBusy === "view"
                    ? "Opening..."
                    : selectedVersion && isPdf(selectedVersion.original_filename)
                      ? "View Resume"
                      : showExtractedText
                        ? "Hide Extracted Text"
                        : "View Extracted Text"}
                </button>

                <button
                  type="button"
                  onClick={handleDownload}
                  disabled={!selectedVersion || fileActionBusy !== null}
                  className="border border-[#294B70] px-5 py-3 text-xs font-bold uppercase tracking-[0.15em] text-[#F2F5F8] transition hover:border-[#1677E8] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {fileActionBusy === "download"
                    ? "Downloading..."
                    : "Download"}
                </button>

                <button
                  type="button"
                  onClick={analyzeResume}
                  disabled={!selectedVersionId || analyzing}
                  className="bg-[#E50920] px-5 py-3 text-xs font-bold uppercase tracking-[0.15em] text-white transition hover:bg-[#FF1E32] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {analyzing ? "Analyzing Resume..." : "Analyze Resume"}
                </button>
              </div>

              {fileActionError && (
                <div className="mt-5 border border-[#E50920]/40 bg-[#E50920]/5 p-4">
                  <p className="text-sm text-[#F2F5F8]">{fileActionError}</p>
                </div>
              )}

              {showExtractedText &&
                selectedVersion &&
                !isPdf(selectedVersion.original_filename) && (
                  <div className="mt-5 border border-[#1A3048] bg-[#05070A] p-4">
                    <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#5E7187]">
                      Extracted DOCX Content (not the original file layout)
                    </div>
                    <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-xs leading-6 text-[#C7D0DA]">
                      {selectedVersion.content_text}
                    </pre>
                  </div>
                )}
            </section>

            <section className="mt-8 border border-[#1A3048] bg-[#0B1626] p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#71849A]">
                Version History
              </div>

              {versions.length === 0 ? (
                <p className="mt-5 text-sm text-[#5E7187]">
                  No versions found for this resume.
                </p>
              ) : (
                <div className="mt-5 space-y-3">
                  {versions.map((version) => (
                    <div
                      key={version.id}
                      className={`flex flex-wrap items-center justify-between gap-3 border p-4 ${
                        version.id === selectedVersionId
                          ? "border-[#1677E8] bg-[#1677E8]/5"
                          : "border-[#1A3048]"
                      }`}
                    >
                      <div>
                        <div className="text-sm font-semibold">
                          {version.name}
                          {version.is_master && (
                            <span className="ml-2 font-mono text-[9px] uppercase tracking-wider text-[#1677E8]">
                              Master
                            </span>
                          )}
                        </div>
                        <div className="mt-1 font-mono text-[9px] uppercase tracking-wider text-[#5E7187]">
                          {version.original_filename} · Created{" "}
                          {new Date(version.created_at).toLocaleDateString()}
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
                        className="border border-[#294B70] px-4 py-2 text-[10px] font-bold uppercase tracking-[0.15em] text-[#F2F5F8] transition hover:border-[#1677E8] disabled:cursor-not-allowed disabled:opacity-40"
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
            <section className="border border-[#1A3048] bg-[#0B1626] p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#1677E8]">
                AI Resume Analysis
              </div>
              <div className="mt-2 font-mono text-[9px] uppercase tracking-wider text-[#5E7187]">
                Positioning
              </div>

              <div className="mt-6 grid gap-5 md:grid-cols-3">
                <InfoBlock
                  label="Target Role"
                  value={
                    analysis.positioning.apparent_target_role ??
                    "Not identified"
                  }
                />

                <InfoBlock
                  label="Specialization"
                  value={
                    analysis.positioning.apparent_specialization ??
                    "Not identified"
                  }
                />

                <InfoBlock
                  label="Seniority"
                  value={
                    analysis.positioning.apparent_seniority ??
                    "Not identified"
                  }
                />
              </div>

              <div className="mt-8 grid gap-6 md:grid-cols-2">
                <ListBlock
                  title="Positioning Strengths"
                  items={analysis.positioning.positioning_strengths}
                />

                <ListBlock
                  title="Positioning Risks"
                  items={analysis.positioning.positioning_risks}
                />
              </div>
            </section>

            <section className="grid gap-8 md:grid-cols-2">
              <DataBlock
                title="Skills"
                data={analysis.skills}
              />

              <DataBlock
                title="Experience"
                data={analysis.experience}
              />

              <DataBlock
                title="Technical Depth"
                data={analysis.technical_depth}
              />

              <DataBlock
                title="Structure"
                data={analysis.structure}
              />
            </section>

            <section className="border border-[#1A3048] bg-[#0B1626] p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#1677E8]">
                Findings
              </div>

              {analysis.findings.length === 0 ? (
                <p className="mt-5 text-sm text-[#8D9AAA]">
                  No findings were returned for this analysis.
                </p>
              ) : (
                <div className="mt-6 space-y-5">
                  {analysis.findings.map((finding, index) => (
                    <article
                      key={`${finding.category}-${index}`}
                      className="border border-[#1A3048] bg-[#05070A] p-5"
                    >
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#E50920]">
                          {finding.priority}
                        </span>

                        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#5E7187]">
                          {finding.category}
                        </span>

                        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#5E7187]">
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
            </section>

            <section className="grid gap-8 md:grid-cols-2">
              <ListBlock
                title="Strengths"
                items={analysis.summary.strengths}
              />

              <ListBlock
                title="Top Priorities"
                items={analysis.summary.top_priorities}
              />
            </section>
          </div>
        )}
      </div>
    </main>
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
    <div className="border border-[#1A3048] bg-[#05070A] p-5">
      <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#5E7187]">
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
    <div className="border border-[#1A3048] bg-[#05070A] p-5">
      <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-[#71849A]">
        {title}
      </div>

      {items.length === 0 ? (
        <p className="mt-4 text-sm text-[#5E7187]">
          No items identified.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((item, index) => (
            <li
              key={`${item}-${index}`}
              className="border-l border-[#294B70] pl-4 text-sm leading-6 text-[#C7D0DA]"
            >
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DataBlock({
  title,
  data,
}: {
  title: string;
  data: Record<string, unknown>;
}) {
  const entries = Object.entries(data);

  return (
    <section className="border border-[#1A3048] bg-[#0B1626] p-6">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#1677E8]">
        {title}
      </div>

      {entries.length === 0 ? (
        <p className="mt-5 text-sm text-[#5E7187]">
          No structured data returned.
        </p>
      ) : (
        <div className="mt-5 space-y-4">
          {entries.map(([key, value]) => (
            <div
              key={key}
              className="border-b border-[#1A3048] pb-4 last:border-b-0"
            >
              <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#5E7187]">
                {formatLabel(key)}
              </div>

              <div className="mt-2 text-sm leading-6 text-[#C7D0DA]">
                {formatValue(value)}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
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
      <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#5E7187]">
        {label}
      </div>

      <p className="mt-2 text-sm leading-6 text-[#C7D0DA]">{value}</p>
    </div>
  );
}

function formatLabel(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value
      .map((item) =>
        typeof item === "object" && item !== null
          ? JSON.stringify(item)
          : String(item),
      )
      .join(" • ");
  }

  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }

  return String(value);
}
