import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileText, Plus } from "lucide-react";
import { api } from "../lib/api";
import type { Source } from "../lib/types";
import { useSession } from "../app/session";
import {
  Empty,
  ErrorNotice,
  Loading,
  Notice,
  PageHeading,
  Status,
} from "../components/ui";
interface DashboardData {
  counts: {
    documents: number;
    completed_analyses: number;
    pending_analyses: number;
    failed_analyses: number;
  };
  recent_documents: Source[];
  recent_activity: { action: string; object_id: string; created_at: string }[];
}
export default function Dashboard() {
  const { user, loading } = useSession();
  const query = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<DashboardData>("/dashboard"),
    enabled: !!user,
    refetchInterval: 10000,
  });
  if (loading) return <Loading />;
  return (
    <section className="page">
      <PageHeading
        eyebrow="YOUR VERIORA WORKSPACE"
        title="Pick up your document review."
        actions={
          <Link className="button" to="/analyze">
            <Plus size={17} />
            New analysis
          </Link>
        }
      >
        A clear view of your sources, processing work and recent activity.
      </PageHeading>
      {!user ? (
        <div className="panel">
          <Empty title="Start with your first document">
            Analyze a document as a guest, or sign in to revisit saved evidence.
          </Empty>
          <div className="actions center">
            <Link className="button" to="/analyze">
              Analyze a document
            </Link>
            <Link className="button secondary" to="/sign-in">
              Sign in
            </Link>
          </div>
        </div>
      ) : (
        <>
          <ErrorNotice error={query.error} />
          {query.isPending ? (
            <Loading />
          ) : (
            query.data && (
              <>
                {user.guest && (
                  <Notice warning>
                    Your guest workspace is temporary. Create an account in this
                    session to retain these documents.
                  </Notice>
                )}
                <div className="dashboard-counts">
                  {[
                    ["Documents", query.data.counts.documents],
                    [
                      "Completed analyses",
                      query.data.counts.completed_analyses,
                    ],
                    ["In progress", query.data.counts.pending_analyses],
                    ["Need attention", query.data.counts.failed_analyses],
                  ].map(([label, count]) => (
                    <div key={label}>
                      <span>{label}</span>
                      <strong>{count}</strong>
                    </div>
                  ))}
                </div>
                {query.data.counts.failed_analyses > 0 && (
                  <Notice warning>
                    Some analyses did not finish. Open their documents to
                    inspect the failure and retry when appropriate.
                  </Notice>
                )}
                <div className="dashboard-columns">
                  <section className="panel dashboard-recent">
                    <div className="row between">
                      <h2>Recent documents</h2>
                      <Link className="text-link" to="/library">
                        View library
                        <ArrowRight size={15} />
                      </Link>
                    </div>
                    {query.data.recent_documents.length ? (
                      query.data.recent_documents.map((source) => (
                        <Link
                          className="recent-document"
                          key={source.id}
                          to={
                            source.analysis_id
                              ? `/analysis/${source.analysis_id}`
                              : `/source/${source.id}`
                          }
                        >
                          <FileText size={22} />
                          <div>
                            <strong>{source.original_name}</strong>
                            <span>
                              Captured{" "}
                              {new Date(
                                source.captured_at,
                              ).toLocaleDateString()}
                            </span>
                          </div>
                          <Status value={source.status} />
                        </Link>
                      ))
                    ) : (
                      <Empty title="No documents yet">
                        Upload an agreement or paste text to begin.
                      </Empty>
                    )}
                  </section>
                  <section className="panel dashboard-activity">
                    <h2>Recent activity</h2>
                    {query.data.recent_activity.length ? (
                      <ol>
                        {query.data.recent_activity.map((event, index) => (
                          <li key={`${event.object_id}-${index}`}>
                            <span>
                              {event.action
                                .replaceAll(".", " ")
                                .replaceAll("_", " ")}
                            </span>
                            <time dateTime={event.created_at}>
                              {new Date(event.created_at).toLocaleString()}
                            </time>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p className="muted">
                        Document and account activity will appear here.
                      </p>
                    )}
                  </section>
                </div>
              </>
            )
          )}
        </>
      )}
    </section>
  );
}
