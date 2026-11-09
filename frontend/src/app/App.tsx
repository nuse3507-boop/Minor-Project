import { lazy, Suspense, useState } from "react";
import { Link, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { ArrowUpRight, FileText, LogOut, Settings2 } from "lucide-react";
import { useSession } from "./session";
import { post } from "../lib/api";
import { ErrorNotice, Loading } from "../components/ui";
const Landing = lazy(() => import("../features/Landing"));
const Intake = lazy(() => import("../features/Intake"));
const Auth = lazy(() => import("../features/Auth"));
const Library = lazy(() => import("../features/Library"));
const Dashboard = lazy(() => import("../features/Dashboard"));
const Settings = lazy(() => import("../features/Settings"));
const Workspace = lazy(() => import("../features/Workspace"));
const Compare = lazy(() => import("../features/Compare"));
const SourcePage = lazy(() => import("../features/SourcePage"));
export default function App() {
  const { user, refresh } = useSession();
  const navigate = useNavigate();
  const [authError, setAuthError] = useState<unknown>();
  const [signingOut, setSigningOut] = useState(false);
  async function logout() {
    setSigningOut(true);
    setAuthError(undefined);
    try {
      await post("/auth/logout");
      await refresh();
      navigate("/");
    } catch (error) {
      setAuthError(error);
    } finally {
      setSigningOut(false);
    }
  }
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <Link className="brand" to="/" aria-label="Veriora home">
          <span className="brand-mark">
            <FileText size={21} />
          </span>
          veriora<span className="brand-dot">.</span>
        </Link>
        <nav aria-label="Main navigation">
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/analyze">Analyze</NavLink>
          <NavLink to="/library">Library</NavLink>
        </nav>
        <div className="account-nav">
          {user ? (
            <>
              <Link className="account" to="/settings">
                <Settings2 size={17} />
                <span>{user.guest ? "Guest session" : "Account"}</span>
              </Link>
              <button
                className="icon-button"
                title="Sign out"
                aria-label="Sign out"
                disabled={signingOut}
                onClick={() => void logout()}
              >
                <LogOut size={17} />
              </button>
              {user.guest && (
                <Link className="button small" to="/sign-in">
                  Save your work <ArrowUpRight size={15} />
                </Link>
              )}
            </>
          ) : (
            <Link className="button secondary small" to="/sign-in">
              Sign in <ArrowUpRight size={15} />
            </Link>
          )}
        </div>
      </header>
      <main id="main">
        <ErrorNotice error={authError} />
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/analyze" element={<Intake />} />
            <Route path="/discover" element={<Intake initialMode="url" />} />
            <Route path="/sign-in" element={<Auth />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/library" element={<Library />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/analysis/:id" element={<Workspace />} />
            <Route path="/source/:id" element={<SourcePage />} />
            <Route
              path="*"
              element={
                <section className="page narrow">
                  <h1>Page not found</h1>
                  <p>This address is unavailable.</p>
                  <Link className="button" to="/analyze">
                    Analyze a document
                  </Link>
                </section>
              }
            />
          </Routes>
        </Suspense>
      </main>
      <footer className="footer">
        <Link className="brand" to="/">
          veriora<span className="brand-dot">.</span>
        </Link>
        <span>Document intelligence. Evidence first.</span>
        <span>
          Interpretations inform your review. They are not legal advice.
        </span>
      </footer>
    </>
  );
}
