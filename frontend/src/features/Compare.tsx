import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowLeftRight } from "lucide-react";
import { api, post } from "../lib/api";
import type { Section, Source } from "../lib/types";
import { useSession } from "../app/session";
import {
  Empty,
  ErrorNotice,
  Loading,
  Notice,
  PageHeading,
} from "../components/ui";
interface Comparison {
  sources: Source[];
  changes: { kind: string; before: Section[]; after: Section[] }[];
  counts: Record<string, number>;
  limitations: string[];
}
export default function Compare() {
  const { user } = useSession();
  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: () => api<Source[]>("/sources"),
    enabled: !!user,
  });
  const [before, setBefore] = useState("");
  const [after, setAfter] = useState("");
  const [result, setResult] = useState<Comparison>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [showSame, setShowSame] = useState(false);
  const available =
    sources.data?.filter((s) => ["READY", "PARTIAL"].includes(s.status)) || [];
  async function compare(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      setResult(
        await post<Comparison>("/comparisons", { source_ids: [before, after] }),
      );
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="page">
      <Link className="back-link" to="/library">
        <ArrowLeft size={15} />
        Document library
      </Link>
      <PageHeading
        eyebrow="SOURCE SNAPSHOT COMPARISON"
        title="See what the wording changed."
      >
        Compare two captured sources side by side. Changes reflect text
        differences, without a legal conclusion.
      </PageHeading>
      <Notice>
        Capture dates record when sources were acquired. They do not establish a
        policy’s effective date or a complete history.
      </Notice>
      <ErrorNotice error={error || sources.error} />
      {!user ? (
        <Empty title="Your sources are private">
          <Link className="text-link" to="/sign-in">
            Sign in to compare your documents.
          </Link>
        </Empty>
      ) : sources.isPending ? (
        <Loading />
      ) : (
        <>
          <form className="panel comparison-form" onSubmit={compare}>
            <label>
              Earlier / first source
              <select
                value={before}
                onChange={(e) => setBefore(e.target.value)}
                required
              >
                <option value="">Choose a source</option>
                {available.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.original_name} ·{" "}
                    {new Date(s.captured_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </label>
            <ArrowLeftRight size={20} />
            <label>
              Later / second source
              <select
                value={after}
                onChange={(e) => setAfter(e.target.value)}
                required
              >
                <option value="">Choose a source</option>
                {available
                  .filter((s) => s.id !== before)
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.original_name} ·{" "}
                      {new Date(s.captured_at).toLocaleDateString()}
                    </option>
                  ))}
              </select>
            </label>
            <button
              className="button"
              disabled={busy || !before || !after || before === after}
            >
              {busy ? "Comparing…" : "Compare sources"}
            </button>
          </form>
          {available.length < 2 && (
            <p className="muted small-copy">
              Upload at least two sources and wait for extraction before
              comparing them.
            </p>
          )}
          {result && (
            <>
              <div className="comparison-meta">
                {result.sources.map((s) => (
                  <div key={s.id}>
                    <strong>{s.original_name}</strong>
                    <p className="muted small-copy">
                      Captured {new Date(s.captured_at).toLocaleString()}
                    </p>
                    <p className="mono">SHA-256 {s.sha256}</p>
                  </div>
                ))}
              </div>
              <div className="row between comparison-counts">
                <span>
                  {Object.entries(result.counts)
                    .map(([k, v]) => `${v} ${k}`)
                    .join(" · ")}
                </span>
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={showSame}
                    onChange={(e) => setShowSame(e.target.checked)}
                  />
                  Show unchanged passages
                </label>
              </div>
              <div className="diff-table">
                <div className="diff-head">
                  <strong>First captured source</strong>
                  <strong>Second captured source</strong>
                </div>
                {result.changes
                  .filter((c) => showSame || c.kind !== "unchanged")
                  .map((c, i) => (
                    <article className={`diff-row ${c.kind}`} key={i}>
                      <span className="diff-label">{c.kind}</span>
                      <div>
                        {c.before.length ? (
                          c.before.map((s) => (
                            <div
                              className="diff-passage"
                              key={s.section_id || s.id}
                            >
                              <span className="tiny-label">
                                {s.page
                                  ? `Page ${s.page}`
                                  : s.heading || "Source section"}
                              </span>
                              <p>{s.text}</p>
                            </div>
                          ))
                        ) : (
                          <p className="muted small-copy">
                            No corresponding passage in this source.
                          </p>
                        )}
                      </div>
                      <div>
                        {c.after.length ? (
                          c.after.map((s) => (
                            <div
                              className="diff-passage"
                              key={s.section_id || s.id}
                            >
                              <span className="tiny-label">
                                {s.page
                                  ? `Page ${s.page}`
                                  : s.heading || "Source section"}
                              </span>
                              <p>{s.text}</p>
                            </div>
                          ))
                        ) : (
                          <p className="muted small-copy">
                            No corresponding passage in this source.
                          </p>
                        )}
                      </div>
                    </article>
                  ))}
              </div>
              {!result.changes.some((c) => c.kind !== "unchanged") && (
                <Empty title="No textual changes found">
                  The compared source passages match. This does not establish
                  identical real-world practices.
                </Empty>
              )}
              {result.limitations.map((l) => (
                <p className="muted small-copy" key={l}>
                  {l}
                </p>
              ))}
            </>
          )}
        </>
      )}
    </section>
  );
}
