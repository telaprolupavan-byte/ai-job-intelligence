"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiRequest, ApiError } from "@/lib/api";
import { getAuthToken } from "@/lib/auth";

type Resume = {
  id: string;
  filename: string;
  created_at: string;
};

type ResumeVersion = {
  id: string;
  resume_id: string;
  name: string;
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

export default function Page() {
  const router = useRouter();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string>("");

  const [analysis, setAnalysis] = useState<ResumeAnalysis | null>(null);

  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadResumes() {
      if (!getAuthToken()) {
        router.replace("/login");
        return;
      }

      try {
        setLoading(true);
        setError(null);

        const resumeData = await authenticatedRequest<Resume[]>("/resumes");
        setResumes(resumeData);

        if (resumeData.length === 0) {
          setVersions([]);
          setSelectedVersionId("");
          return;
        }

        const versionData = await authenticatedRequest<ResumeVersion[]>(
          `/resumes/${resumeData[0].id}/versions`,
        );

        setVersions(versionData);

        const masterVersion =
          versionData.find((version) => version.is_master) ??
          versionData[0];

        if (masterVersion) {
          setSelectedVersionId(masterVersion.id);
        }
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
      } finally {
        setLoading(false);
      }
    }

    loadResumes();
  }, [router]);

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
            Evidence-backed analysis of your resume positioning, skills,
            experience, technical depth, structure, and improvement priorities.
          </p>
        </header>

        <section className="mt-8 border border-[#1A3048] bg-[#0B1626] p-6">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#71849A]">
            Resume Selection
          </div>

          {loading ? (
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
            <>
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

              {selectedVersion && (
                <div className="mt-3 font-mono text-[9px] uppercase tracking-wider text-[#5E7187]">
                  VERSION CREATED{" "}
                  {new Date(selectedVersion.created_at).toLocaleDateString()}
                </div>
              )}

              <button
                type="button"
                onClick={analyzeResume}
                disabled={!selectedVersionId || analyzing}
                className="mt-6 bg-[#E50920] px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] text-white transition hover:bg-[#FF1E32] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {analyzing ? "Analyzing Resume..." : "Analyze Resume"}
              </button>
            </>
          )}

          {error && (
            <div className="mt-5 border border-[#E50920]/40 bg-[#E50920]/5 p-4">
              <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#E50920]">
                Analysis Error
              </div>

              <p className="mt-2 text-sm text-[#F2F5F8]">{error}</p>
            </div>
          )}
        </section>

        {analysis && (
          <div className="mt-8 space-y-8">
            <section className="border border-[#1A3048] bg-[#0B1626] p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#1677E8]">
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