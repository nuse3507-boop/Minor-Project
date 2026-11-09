import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Copy,
  Download,
  FileSearch,
  MessageSquare,
  Search,
} from "lucide-react";
import { api, apiPage, download, post } from "../lib/api";
import {
  active,
  type Analysis,
  type Finding,
  type Job,
  type Citation,
} from "../lib/types";
import { citationValid } from "../lib/evidence";
import { useSession } from "../app/session";
import { CoverageNotice } from "../components/CoverageNotice";
import QuestionPanel from "./QuestionPanel";
import { Tabs } from "../components/Tabs";
import { pageOffset } from "../lib/query";
import { Pagination } from "../components/Pagination";
import { SourceViewer } from "../components/SourceViewer";
import {
  Empty,
  ErrorNotice,
  Loading,
  PageHeading,
  Status,
} from "../components/ui";
function display(value: unknown) {
  return typeof value === "string" ? value : JSON.stringify(value);
}
export default function Workspace() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const { user } = useSession();
  const [selectedId, setSelectedId] = useState(params.get("finding") || "");
  const [mobileTab, setMobileTab] = useState("insights");
  const [view, setView] = useState("findings");
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const analysis = useQuery({
    queryKey: ["analysis", id],
    queryFn: () => api<Analysis>(`/analyses/${id}`),
    refetchInterval: (q) => (active(q.state.data?.status) ? 1800 : false),
  });
  const jobId = analysis.data?.job_id;
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api<Job>(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => (active(q.state.data?.state) ? 1600 : false),
  });
  const [answerCitation, setAnswerCitation] = useState<Citation>();
  const offset = pageOffset(params.get("offset"), 30);
  const findingQuery = new URLSearchParams({
    offset: String(offset),
    limit: "30",
  });
  for (const [urlKey, apiKey] of [
    ["q", "q"],
    ["category", "category"],
    ["status", "status"],
    ["source", "source_id"],
  ]) {
    const value = params.get(urlKey);
    if (value) findingQuery.set(apiKey, value);
  }
  if (view === "duties" && !params.get("category"))
    findingQuery.set(
      "category",
      "RIGHT,OBLIGATION,RESTRICTION,CONSENT,EXCEPTION",
    );
  const findings = useQuery({
    queryKey: ["findings", id, analysis.data?.status, findingQuery.toString()],
    queryFn: () => apiPage<Finding>(`/analyses/${id}/findings?${findingQuery}`),
    enabled: !!analysis.data,
    refetchInterval: () => (active(analysis.data?.status) ? 2500 : false),
  });
  const selectedQuery = useQuery({
    queryKey: ["finding", id, selectedId],
    queryFn: () => api<Finding>(`/analyses/${id}/findings/${selectedId}`),
    enabled:
      !!selectedId &&
      !findings.data?.items.some((f) => f.finding_id === selectedId),
  });
  const data = analysis.data;
  const all = useMemo(() => findings.data?.items || [], [findings.data?.items]);
  const selected = selectedId
    ? all.find((f) => f.finding_id === selectedId) || selectedQuery.data
    : undefined;
  const citation = answerCitation || selected?.citations[0];
  const sourceId =
    citation?.source_id ||
    params.get("source") ||
    data?.source_ids?.[0] ||
    data?.sources?.[0]?.id;
  const source = data?.sources?.find((s) => s.id === sourceId);
  const state = job.data?.state || data?.status;
  const filtered = all;
  function filter(key: string, value: string) {
    const p = new URLSearchParams(params);
    if (value) p.set(key, value);
    else p.delete(key);
    if (key !== "finding" && key !== "offset") p.delete("offset");
    setParams(p, { replace: true });
  }
  function select(f: Finding) {
    setAnswerCitation(undefined);
    setSelectedId(f.finding_id);
    filter("finding", f.finding_id);
    setMobileTab("source");
    setCopied(false);
  }
  useEffect(() => {
    setSelectedId(params.get("finding") || "");
  }, [params]);
  useEffect(() => {
    if (!selectedId && !answerCitation && all.length)
      setSelectedId(all[0].finding_id);
  }, [all, selectedId, answerCitation]);
  async function jobAction(action: string) {
    setBusy(true);
    setError(undefined);
    try {
      await post(`/jobs/${jobId}/${action}`);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["analysis", id] }),
        qc.invalidateQueries({ queryKey: ["job", jobId] }),
      ]);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function exportReport(format: string) {
    setError(undefined);
    setBusy(true);
    try {
      await download(
        `/analyses/${id}/exports?format=${format}`,
        `veriora-${id}.${format}`,
      );
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function copy() {
    setError(undefined);
    try {
      await navigator.clipboard.writeText(
        `${selected?.statement}\n“${citation?.quote}”\nSource ${sourceId}, section ${citation?.section_id}, ${citation?.page ? `page ${citation.page}, ` : ""}SHA-256 ${source?.sha256}`,
      );
      setCopied(true);
    } catch {
      setError(
        "Clipboard access is unavailable. Select and copy the reference text from the Evidence Passport.",
      );
    }
  }
  if (analysis.isPending) return <Loading label="Opening your analysis…" />;
  if (analysis.error)
    return (
      <section className="page">
        <ErrorNotice error={analysis.error} />
        <Link to="/library">Back to library</Link>
      </section>
    );
  return (
    <section className="page workspace-page">
      <Link className="back-link" to="/library">
        <ArrowLeft size={15} />
        Document library
      </Link>
      <PageHeading
        eyebrow="ANALYSIS WORKSPACE"
        title={
          data?.sources?.length === 1
            ? data.sources[0].original_name
            : `${data?.sources?.length || data?.source_ids?.length || 1} document analysis`
        }
        actions={
          <>
            <button
              className="button secondary"
              disabled={
                busy ||
                user?.guest ||
                !["COMPLETED", "PARTIAL_COMPLETION"].includes(state || "")
              }
              onClick={() => void exportReport("json")}
            >
              <Download size={16} />
              Manifest
            </button>
            <button
              className="button"
              disabled={
                busy ||
                user?.guest ||
                !["COMPLETED", "PARTIAL_COMPLETION"].includes(state || "")
              }
              onClick={() => void exportReport("pdf")}
            >
              <Download size={16} />
              PDF report
            </button>
          </>
        }
      >
        Findings you can inspect. Source evidence you can follow.
      </PageHeading>
      <ErrorNotice error={error || job.error || selectedQuery.error} />
      {user?.guest && (
        <p className="small-copy muted">
          <Link to="/sign-in">Sign in</Link> to export a report. Guest results
          are temporary.
        </p>
      )}
      {active(state) && (
        <section className="panel processing" aria-live="polite">
          <Loading
            label={`${job.data?.stage || "Queued"} · ${job.data?.state || data?.status}`}
          />
          <p className="muted">
            You can safely leave this page. Processing continues on the server.
          </p>
          <div className="processing-stages">
            {["RECEIVED", "GENERATING", "VERIFYING", "AGGREGATING"].map((s) => (
              <span key={s} className={job.data?.stage === s ? "current" : ""}>
                {s.toLowerCase()}
              </span>
            ))}
          </div>
          {job.data?.progress && (
            <dl className="progress-units">
              {Object.entries(job.data.progress).map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd>{display(value)}</dd>
                </div>
              ))}
            </dl>
          )}
          <button
            className="button secondary small"
            disabled={busy}
            onClick={() => void jobAction("cancel")}
          >
            Cancel processing
          </button>
        </section>
      )}
      {["FAILED", "CANCELLED", "CANCELED"].includes(state || "") && (
        <div className="notice error">
          <FileSearch size={20} />
          <div>
            <strong>
              {state === "FAILED"
                ? "Analysis could not be completed"
                : "Processing was canceled"}
            </strong>
            <p>
              {job.data?.error ||
                "No complete analysis is available. Preserved sources remain inspectable."}
            </p>
            <button
              className="button secondary small"
              disabled={busy}
              onClick={() => void jobAction("retry")}
            >
              Retry analysis
            </button>
          </div>
        </div>
      )}
      <CoverageNotice coverage={data?.coverage} state={state} />
      {data?.overview && (
        <section className="panel analysis-overview">
          <h2>Analysis overview</h2>
          <p>{data.overview.summary}</p>
          {data.overview.document_cues.map((cue, i) => (
            <p className="small-copy muted" key={i}>
              {cue.label} · {cue.method}
            </p>
          ))}
          {data.overview.explicit_party_labels.length > 0 && (
            <details>
              <summary>Parties explicitly labelled in the source</summary>
              {data.overview.explicit_party_labels.map((party, i) => (
                <p key={i}>
                  {party.text}
                  <small className="muted"> · {party.method}</small>
                </p>
              ))}
            </details>
          )}
        </section>
      )}
      <div className="workspace-nav">
        <Tabs
          label="Analysis views"
          value={view}
          onChange={(key) => {
            setView(key);
            if (key === "duties") filter("category", "");
          }}
          items={[
            { value: "findings", label: "Findings" },
            { value: "duties", label: "Rights & duties" },
            {
              value: "ask",
              label: (
                <>
                  <MessageSquare size={16} />
                  Ask Veriora
                </>
              ),
            },
            { value: "coverage", label: "Coverage" },
          ]}
        />
        <span className="muted small-copy">
          {data?.findings_count || 0} findings
        </span>
      </div>
      {view === "coverage" ? (
        <section className="panel coverage-detail">
          <h2>What was processed</h2>
          <CoverageNotice coverage={data?.coverage} state={state} />
          <h3>Limitations</h3>
          {data?.limitations?.map((l) => (
            <p key={l}>{l}</p>
          ))}
          <details>
            <summary>Provider and model execution metadata</summary>
            <pre>{JSON.stringify(data?.model_calls || [], null, 2)}</pre>
          </details>
        </section>
      ) : view === "ask" ? (
        <QuestionPanel
          analysisId={id}
          sourceCount={data?.source_ids?.length || 0}
          disabled={
            active(state) ||
            !["COMPLETED", "PARTIAL_COMPLETION"].includes(state || "")
          }
          onCitation={(c) => {
            if (citationValid(c)) {
              setAnswerCitation(c);
              setSelectedId("");
              setView("findings");
              setMobileTab("source");
            } else if (c.finding_id) {
              setSelectedId(c.finding_id);
              filter("finding", c.finding_id);
              setView("findings");
              setMobileTab("source");
            }
          }}
        />
      ) : (
        <>
          <Tabs
            className="mobile-workspace-tabs"
            label="Workspace panels"
            value={mobileTab}
            onChange={setMobileTab}
            items={[
              { value: "insights", label: "Insights" },
              { value: "source", label: "Source & evidence" },
            ]}
          />
          <div className="workspace-grid">
            <section
              className={`findings-panel ${mobileTab === "insights" ? "mobile-active" : ""}`}
            >
              <div className="finding-filters">
                <label className="search-field">
                  <Search size={17} />
                  <span className="sr-only">Search findings</span>
                  <input
                    placeholder="Search findings or source text"
                    value={params.get("q") || ""}
                    onChange={(e) => filter("q", e.target.value)}
                  />
                </label>
                <div className="filter-row">
                  <label>
                    <span className="sr-only">Finding category</span>
                    <select
                      value={params.get("category") || ""}
                      onChange={(e) => filter("category", e.target.value)}
                    >
                      <option value="">All categories</option>
                      {[
                        "CLAUSE",
                        "OBLIGATION",
                        "RIGHT",
                        "RESTRICTION",
                        "CONSENT",
                        "EXCEPTION",
                        "RISK_NOTE",
                        "PRIVACY",
                        "PAYMENT",
                        "TERMINATION",
                        "DISPUTE",
                        "PERMISSION",
                        "OTHER",
                      ].map((c) => (
                        <option value={c} key={c}>
                          {c.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span className="sr-only">Evidence status</span>
                    <select
                      value={params.get("status") || ""}
                      onChange={(e) => filter("status", e.target.value)}
                    >
                      <option value="">All evidence states</option>
                      {[
                        "SUPPORTED",
                        "PARTIALLY_SUPPORTED",
                        "UNSUPPORTED",
                        "AMBIGUOUS",
                      ].map((s) => (
                        <option value={s} key={s}>
                          {s.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {(data?.sources?.length || 0) > 1 && (
                  <label>
                    Source document
                    <select
                      value={params.get("source") || ""}
                      onChange={(e) => filter("source", e.target.value)}
                    >
                      <option value="">All documents</option>
                      {data?.sources?.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.original_name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>
              <ErrorNotice error={findings.error} />
              {findings.isPending ? (
                <Loading label="Loading findings…" />
              ) : (
                (view === "duties"
                  ? filtered.filter((f) =>
                      [
                        "RIGHT",
                        "OBLIGATION",
                        "RESTRICTION",
                        "CONSENT",
                        "EXCEPTION",
                      ].includes(f.category),
                    )
                  : filtered
                ).map((f) => (
                  <article
                    className={`finding-card ${f.finding_id === selectedId ? "selected" : ""}`}
                    key={f.finding_id}
                  >
                    <div className="row between">
                      <span className="tiny-label">
                        {f.category.replaceAll("_", " ")}
                      </span>
                      <Status
                        value={f.support_status}
                        valid={
                          f.citations.length > 0 &&
                          f.citations.every(citationValid)
                        }
                      />
                    </div>
                    <h2>{f.statement}</h2>
                    <p>{f.rationale}</p>
                    {f.qualifications?.length > 0 && (
                      <p className="qualification">
                        Qualification: {f.qualifications.join(" ")}
                      </p>
                    )}
                    <div className="row between">
                      <span className="muted small-copy">
                        {f.citations[0]?.page
                          ? `Page ${f.citations[0].page}`
                          : "Source section"}
                        {f.citations[0]?.clause_label &&
                          ` · ${f.citations[0].clause_label}`}
                      </span>
                      <button
                        className="text-link"
                        onClick={() => select(f)}
                        aria-pressed={f.finding_id === selectedId}
                      >
                        View evidence <ArrowRight size={15} />
                      </button>
                    </div>
                  </article>
                ))
              )}
              <Pagination
                offset={offset}
                total={findings.data?.total ?? null}
                pageSize={30}
                count={all.length}
                onChange={(n) => filter("offset", String(n))}
              />
              {!findings.isPending && !filtered.length && (
                <Empty
                  title={
                    active(state)
                      ? "Findings are being prepared"
                      : findings.error
                        ? "Findings unavailable"
                        : "No findings in this view"
                  }
                >
                  {active(state)
                    ? "Results appear as the server completes verification."
                    : "Try changing filters. No findings does not establish that a term is absent or that the document is safe."}
                </Empty>
              )}
            </section>
            <aside
              className={`evidence-panel ${mobileTab === "source" ? "mobile-active" : ""}`}
            >
              {sourceId ? (
                <div className="panel viewer-panel">
                  <SourceViewer sourceId={sourceId} citation={citation} />
                </div>
              ) : (
                <Empty title="No captured source available" />
              )}
              {selected && (
                <section className="panel passport">
                  <div className="row between">
                    <h2>Evidence Passport</h2>
                    <button className="text-link" onClick={() => void copy()}>
                      <Copy size={15} />
                      {copied ? "Copied" : "Copy reference"}
                    </button>
                  </div>
                  <Status
                    value={selected.support_status}
                    valid={
                      selected.citations.length > 0 &&
                      selected.citations.every(citationValid)
                    }
                  />
                  <blockquote>
                    {citation?.quote || "No source quotation was provided."}
                  </blockquote>
                  <p>{selected.statement}</p>
                  <dl>
                    <dt>Source document</dt>
                    <dd>{source?.original_name || citation?.source_id}</dd>
                    <dt>Original source</dt>
                    <dd>
                      {source?.source_url || "Uploaded file or pasted text"}
                    </dd>
                    <dt>Source identifier / version</dt>
                    <dd className="mono">{sourceId}</dd>
                    <dt>Acquired</dt>
                    <dd>
                      {source?.captured_at
                        ? new Date(source.captured_at).toLocaleString()
                        : "Unavailable"}
                    </dd>
                    <dt>Source SHA-256</dt>
                    <dd className="mono">{source?.sha256 || "Unavailable"}</dd>
                    <dt>Location</dt>
                    <dd>
                      {citation?.page ? `Page ${citation.page} · ` : ""}
                      {citation?.section_id} · Unicode offsets {citation?.start}
                      –{citation?.end}
                    </dd>
                    <dt>Citation validity</dt>
                    <dd>{citation?.match_status || "INVALID"}</dd>
                    <dt>Qualifications</dt>
                    <dd>
                      {selected.qualifications?.join(" ") ||
                        "No additional qualifications recorded; inspect surrounding source context."}
                    </dd>
                  </dl>
                  <details>
                    <summary>Verification method & execution metadata</summary>
                    <p className="small-copy">
                      Generator: {selected.provider} / {selected.model}
                    </p>
                    <pre>
                      {JSON.stringify(selected.verification || {}, null, 2)}
                    </pre>
                    <p className="small-copy muted">
                      A model verifier is not independent human adjudication.
                      Source matching and semantic interpretation are separate
                      checks.
                    </p>
                  </details>
                  <p className="small-copy muted">
                    This record supports inspection of the captured document. It
                    does not prove real-world compliance, legal enforceability
                    or admissibility.
                  </p>
                </section>
              )}
            </aside>
          </div>
        </>
      )}
    </section>
  );
}
