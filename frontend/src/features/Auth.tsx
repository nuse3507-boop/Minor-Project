import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, FileText } from "lucide-react";
import type { User } from "../lib/types";
import { post } from "../lib/api";
import { useSession } from "../app/session";
import { ErrorNotice, Notice } from "../components/ui";
export default function Auth() {
  const [params] = useSearchParams();
  const [mode, setMode] = useState(
    params.has("token")
      ? params.get("purpose") === "recover"
        ? "reset"
        : "verify"
      : "login",
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState(params.get("token") || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const { refresh } = useSession();
  const navigate = useNavigate();
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(undefined);
    setMessage("");
    setBusy(true);
    try {
      if (mode === "recover") {
        await post("/auth/recover", { email });
        setMessage(
          "If this account can be recovered, recovery instructions will be sent to its email address.",
        );
      } else if (mode === "verify") {
        await post("/auth/verify", { token });
        setMessage("Email verified. You can now sign in.");
        setMode("login");
      } else if (mode === "reset") {
        await post("/auth/reset", { token, password });
        setMessage("Password updated. Sign in with your new password.");
        setMode("login");
      } else {
        const profile = await post<User>(
          `/auth/${mode === "register" ? "register" : "login"}`,
          { email, password },
        );
        if (mode === "register" && !profile.verified) {
          await refresh();
          setMessage(
            "Account created. Check your email to verify your account before signing in.",
          );
          setMode("login");
        } else {
          await refresh();
          navigate("/library");
        }
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="auth-page page">
      <div className="auth-intro">
        <p className="eyebrow">A PRIVATE PLACE FOR YOUR DOCUMENTS</p>
        <h1>
          Keep the source.
          <br />
          <em>Keep the context.</em>
        </h1>
        <p>
          Return to your analyses, inspect supporting passages and export a
          record of your findings.
        </p>
        <div className="auth-detail">
          <FileText size={26} />
          <p>Evidence stays connected to the document version you reviewed.</p>
        </div>
      </div>
      <div className="panel auth-form">
        <p className="eyebrow">YOUR VERIORA WORKSPACE</p>
        <h2>
          {
            (
              {
                login: "Welcome back",
                register: "Create an account",
                recover: "Recover your account",
                verify: "Verify your email",
                reset: "Set a new password",
              } as Record<string, string>
            )[mode]
          }
        </h2>
        <p className="muted">
          {mode === "register"
            ? "Save your documents and revisit your evidence."
            : "Use your account to access your saved documents."}
        </p>
        <form onSubmit={submit} className="fields">
          {!["verify", "reset"].includes(mode) && (
            <label>
              Email address
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
          )}
          {["login", "register", "reset"].includes(mode) && (
            <label>
              Password
              <input
                type="password"
                aria-label="Password"
                aria-describedby="password-help"
                required
                minLength={12}
                maxLength={128}
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <small id="password-help" className="muted">
                At least 12 characters.
              </small>
            </label>
          )}
          {["verify", "reset"].includes(mode) && (
            <label>
              {mode === "reset" ? "Recovery" : "Verification"} token
              <input
                required
                value={token}
                onChange={(e) => setToken(e.target.value)}
              />
            </label>
          )}
          <ErrorNotice error={error} />
          {message && <Notice>{message}</Notice>}
          <button className="button" disabled={busy}>
            {busy
              ? "Please wait…"
              : (
                  {
                    login: "Sign in",
                    register: "Create account",
                    recover: "Send recovery instructions",
                    verify: "Verify email",
                    reset: "Update password",
                  } as Record<string, string>
                )[mode]}
            <ArrowRight size={17} />
          </button>
        </form>
        <div className="auth-links">
          {mode === "login" ? (
            <>
              <button className="text-link" onClick={() => setMode("recover")}>
                Forgot your password?
              </button>
              <p>
                New to Veriora?{" "}
                <button
                  className="text-link"
                  onClick={() => {
                    setMode("register");
                    setError(undefined);
                  }}
                >
                  Create an account
                </button>
              </p>
            </>
          ) : (
            <button
              className="text-link"
              onClick={() => {
                setMode("login");
                setError(undefined);
              }}
            >
              Back to sign in
            </button>
          )}
          <div className="row wrap">
            <button className="text-link" onClick={() => setMode("verify")}>
              Verify email
            </button>
            <button className="text-link" onClick={() => setMode("reset")}>
              Use recovery token
            </button>
          </div>
        </div>
        <p className="small-copy muted">
          Just exploring?{" "}
          <Link to="/analyze">Start with a limited guest session.</Link>
        </p>
      </div>
    </section>
  );
}
