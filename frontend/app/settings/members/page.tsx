"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { WorkspacePage } from "../../../components/workspace-page";
import { useWorkspace } from "../../../hooks/use-workspace";
import { api, Member } from "../../../lib/api";

export default function MembersPage() {
  const workspace = useWorkspace();
  const [members, setMembers] = useState<Member[]>([]);
  const [busy, setBusy] = useState(false);
  const [loadedOrganizationId, setLoadedOrganizationId] = useState("");
  const currentOrganizationId = useRef(workspace.organizationId);
  const requestNumber = useRef(0);
  currentOrganizationId.current = workspace.organizationId;
  const canManage = workspace.can("member:manage");
  const actorRole = workspace.membership?.role;
  const assignableRoles = actorRole === "OWNER" ? ["ADMIN", "ENGINEER", "VIEWER"] : ["ENGINEER", "VIEWER"];
  const canManageMember = (member: Member) => actorRole === "OWNER" ? member.role !== "OWNER" : member.role === "ENGINEER" || member.role === "VIEWER";

  const load = useCallback(async () => {
    const organizationId = workspace.organizationId;
    if (!organizationId) return;
    const request = ++requestNumber.current;
    try {
      const result = await api<Member[]>(`/api/v1/organizations/${organizationId}/members`);
      if (request !== requestNumber.current || organizationId !== currentOrganizationId.current) return;
      setMembers(result); setLoadedOrganizationId(organizationId); workspace.setError("");
    } catch (reason) {
      if (request === requestNumber.current && organizationId === currentOrganizationId.current) workspace.setError(message(reason));
    }
  }, [workspace.organizationId]);

  useEffect(() => { void load(); }, [load]);
  const visibleMembers = loadedOrganizationId === workspace.organizationId ? members : [];

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const form = event.currentTarget; const values = new FormData(form);
    try {
      await api(`/api/v1/organizations/${workspace.organizationId}/members`, { method: "POST", body: JSON.stringify({ email: values.get("email"), role: values.get("role") }) });
      form.reset(); await load();
    } catch (reason) { workspace.setError(message(reason)); }
    finally { setBusy(false); }
  }

  async function update(memberId: string, role: string) {
    try { await api(`/api/v1/organizations/${workspace.organizationId}/members/${memberId}`, { method: "PATCH", body: JSON.stringify({ role }) }); await load(); }
    catch (reason) { workspace.setError(message(reason)); }
  }

  async function remove(member: Member) {
    if (!window.confirm(`Remove ${member.full_name} from this organization?`)) return;
    try { await api(`/api/v1/organizations/${workspace.organizationId}/members/${member.id}`, { method: "DELETE" }); await load(); }
    catch (reason) { workspace.setError(message(reason)); }
  }

  return <WorkspacePage workspace={workspace} active="Team" title="Team management" subtitle="Invite registered users and control their organization role.">
    {canManage && <article className="panel form-panel"><div><h2>Add a team member</h2><p className="muted">The user must create a PulseForge account first.</p></div><form onSubmit={add}><input name="email" type="email" required aria-label="Member email" placeholder="engineer@example.com" /><select name="role" aria-label="Member role" defaultValue="ENGINEER">{assignableRoles.map((role) => <option key={role}>{role}</option>)}</select><button className="primary-button" disabled={busy}>{busy ? "Adding..." : "Add member"}</button></form></article>}
    <article className="panel"><div className="panel-header"><div><h2>Organization members</h2><p>{visibleMembers.length} member{visibleMembers.length === 1 ? "" : "s"}</p></div><button className="secondary-button" onClick={load}>Refresh</button></div>
      <div className="data-list">{visibleMembers.map((member) => <div className="data-row" key={member.id}><div className="identity"><span className="avatar navy">{member.full_name.slice(0, 2).toUpperCase()}</span><span><strong>{member.full_name}</strong><small>{member.email} · joined {formatDate(member.joined_at)}</small></span></div><div className="row-actions">{canManage && canManageMember(member) ? <><select aria-label={`Role for ${member.full_name}`} value={member.role} onChange={(event) => update(member.id, event.target.value)}>{assignableRoles.map((role) => <option key={role}>{role}</option>)}</select><button className="danger-button" onClick={() => remove(member)}>Remove</button></> : <span className="role-badge">{member.role}</span>}</div></div>)}</div>
    </article>
  </WorkspacePage>;
}

function message(reason: unknown) { return reason instanceof Error ? reason.message : "Something went wrong"; }
function formatDate(value: string) { return new Date(value).toLocaleDateString(); }
