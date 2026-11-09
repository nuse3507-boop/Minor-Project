import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { api, post } from "../lib/api";
import type { Source } from "../lib/types";
import { useSession } from "../app/session";
import { CoverageNotice } from "../components/CoverageNotice";
import { SourceViewer } from "../components/SourceViewer";
import {
  ErrorNotice,
  Loading,
  Notice,
  PageHeading,
  Status,
} from "../components/ui";
export default function SourcePage() {
  const { id = "" } = useParams();
  const { user } = useSession();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [provider, setProvider] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const query = useQuery({
    queryKey: ["source", id],
    queryFn: () => api<Source>(`/sources/${id}`),
    refetchInterval: (q) =>
      ["QUEUED", "PROCESSING"].includes(q.state.data?.status || "")
        ? 2000
        : false,
  });
  async function analyze() {
    setBusy(true);
    setError(undefined);
    try {
      const result = await post<{ analysis_id: string }>("/analyses", {
        source_ids: [id],
        provider,
        consent,
        privacy_mode: "external",
      });
      navigate(`/analysis/${result.analysis_id}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <section className="page">
        <ErrorNotice error={query.error} />
        <Link to="/library">Back to library</Link>
      </section>
    );
  const source = query.data!;
  return (
    <section className="page">
      <PageHeading
        eyebrow="CAPTURED SOURCE"
        title={source.original_name}
        actions={
          <Link className="button secondary" to="/library">
            Back to library
          </Link>
        }
      >
        Preserved original source, separate from AI interpretation.
      </PageHeading>
      <ErrorNotice error={error} />
      <ErrorNotice error={source.processing_error} />
      {["FAILED", "CANCELLED"].includes(source.job_state || "") &&
        source.job_id && (
          <div className="notice">
            <p>
              Extraction did not complete. You can retry the preserved source or
              upload a corrected copy.
            </p>
            <button
              className="button secondary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError(undefined);
                try {
                  await post(`/jobs/${source.job_id}/retry`);
                  await qc.invalidateQueries({ queryKey: ["source", id] });
                } catch (e) {
                  setError(e);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Retry extraction
            </button>
          </div>
        )}
      {source.warnings?.map((w) => (
        <Notice warning key={w}>
          {w}
        </Notice>
      ))}
      <CoverageNotice coverage={source.coverage} extraction />
      <div className="source-detail-layout">
        <div className="panel">
          <SourceViewer sourceId={id} />
        </div>
        <aside>
          <section className="panel passport">
            <h2>Source provenance</h2>
            <Status value={source.status} />
            <dl>
              <dt>Captured</dt>
              <dd>{new Date(source.captured_at).toLocaleString()}</dd>
              <dt>Source identifier / version</dt>
              <dd className="mono">{source.id}</dd>
              <dt>SHA-256 of original bytes</dt>
              <dd className="mono">{source.sha256}</dd>
              <dt>Original source</dt>
              <dd>{source.source_url || "Uploaded file or pasted text"}</dd>
            </dl>
            <Notice>
              A hash identifies these captured bytes. It does not prove remote
              origin, conduct, or legal admissibility.
            </Notice>
          </section>
          <section className="panel passport">
            <h2>Analyze this source</h2>
            <p className="muted">
              External interpretation requires a configured provider and your
              consent.
            </p>
            <label>
              AI provider
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                <option value="">Choose configured provider</option>
                {user?.providers
                  ?.filter((p) => p.configured)
                  .map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.name} · {p.model}
                    </option>
                  ))}
              </select>
            </label>
            <label className="check-label">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              I authorize sending this document text to the selected provider.
              Its processing and retention terms apply.
            </label>
            <button
              className="button"
              disabled={
                !provider || !consent || busy || !source.sections?.length
              }
              onClick={() => void analyze()}
            >
              {busy ? "Starting…" : "Analyze document"}
              <ArrowRight size={16} />
            </button>
            {!user?.providers?.some((p) => p.configured) && (
              <Notice warning>
                AI analysis is unavailable until an administrator configures a
                provider. No analysis has been generated.
              </Notice>
            )}
          </section>
        </aside>
      </div>
    </section>
  );
}
