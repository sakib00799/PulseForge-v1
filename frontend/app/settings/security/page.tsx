"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { WorkspacePage } from "../../../components/workspace-page";
import { PasswordField } from "../../../components/password-field";
import { useWorkspace } from "../../../hooks/use-workspace";
import { changePassword, isUnauthorizedError, listSessions, logoutAll, revokeSession, SessionInfo } from "../../../lib/api";

export default function SecurityPage() {
  const workspace = useWorkspace();
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setSessions(await listSessions()); workspace.setError(""); }
    catch (reason) {
      if (isUnauthorizedError(reason)) router.replace("/");
      else workspace.setError(message(reason));
    }
  }, []);
  useEffect(() => { if (workspace.user) void load(); }, [workspace.user, load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setNotice("");
    const values = new FormData(event.currentTarget);
    if (values.get("new_password") !== values.get("confirm_password")) { workspace.setError("New passwords do not match"); setBusy(false); return; }
    try {
      await changePassword(String(values.get("current_password")), String(values.get("new_password")));
      router.replace("/");
    } catch (reason) { workspace.setError(message(reason)); setBusy(false); }
  }

  async function revoke(id: string) {
    try { await revokeSession(id); setNotice("Session revoked."); await load(); }
    catch (reason) { workspace.setError(message(reason)); }
  }

  async function endAll() {
    if (!window.confirm("Sign out every active session, including this browser?")) return;
    try { await logoutAll(); router.replace("/"); }
    catch (reason) { workspace.setError(message(reason)); }
  }

  return <WorkspacePage workspace={workspace} active="Security" title="Account security" subtitle="Change your password and manage signed-in devices.">
    {notice && <div className="success-banner" role="status"><span>{notice}</span><button type="button" aria-label="Dismiss notification" onClick={() => setNotice("")}>×</button></div>}
    <section className="settings-grid">
      <article className="panel"><div className="panel-header"><div><h2>Change password</h2><p>All current sessions will be revoked.</p></div></div><form className="stack-form" onSubmit={submit}><PasswordField label="Current password" name="current_password" autoComplete="current-password" /><PasswordField label="New password" name="new_password" minLength={12} maxLength={128} autoComplete="new-password" /><PasswordField label="Confirm new password" name="confirm_password" minLength={12} maxLength={128} autoComplete="new-password" /><button className="primary-button" disabled={busy}>{busy ? "Updating..." : "Update password"}</button></form></article>
      <article className="panel"><div className="panel-header"><div><h2>Active sessions</h2><p>Revoke devices you do not recognize.</p></div><button className="danger-button" onClick={endAll}>Sign out all</button></div><div className="data-list">{sessions.map((session) => <div className="data-row compact" key={session.id}><div><strong>{session.user_agent || "Unknown browser"}</strong><small>{session.ip_address || "Unknown IP"} · expires {formatDate(session.expires_at)}</small></div><button className="secondary-button" onClick={() => revoke(session.id)}>Revoke</button></div>)}{!sessions.length && <p className="empty-state">No active refresh sessions.</p>}</div></article>
    </section>
  </WorkspacePage>;
}

function message(reason: unknown) { return reason instanceof Error ? reason.message : "Something went wrong"; }
function formatDate(value: string) { return new Date(value).toLocaleString(); }
