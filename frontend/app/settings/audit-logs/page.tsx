"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { WorkspacePage } from "../../../components/workspace-page";
import { useWorkspace } from "../../../hooks/use-workspace";
import { api, AuditLog } from "../../../lib/api";

const PAGE_SIZE = 25;

export default function AuditLogsPage() {
  const workspace = useWorkspace();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loadedOrganizationId, setLoadedOrganizationId] = useState("");
  const currentOrganizationId = useRef(workspace.organizationId);
  const requestNumber = useRef(0);
  currentOrganizationId.current = workspace.organizationId;
  const canRead = workspace.can("audit_log:read");

  const load = useCallback(async (append = false) => {
    const organizationId = workspace.organizationId;
    if (!organizationId || !canRead) return;
    const request = ++requestNumber.current;
    const offset = append && loadedOrganizationId === organizationId ? logs.length : 0;
    try {
      const result = await api<AuditLog[]>(`/api/v1/audit-logs?organization_id=${organizationId}&limit=${PAGE_SIZE}&offset=${offset}`);
      if (request !== requestNumber.current || organizationId !== currentOrganizationId.current) return;
      setLogs((current) => offset ? [...current, ...result] : result);
      setLoadedOrganizationId(organizationId);
      setHasMore(result.length === PAGE_SIZE); workspace.setError("");
    } catch (reason) {
      if (request === requestNumber.current && organizationId === currentOrganizationId.current) workspace.setError(message(reason));
    }
  }, [workspace.organizationId, canRead, loadedOrganizationId, logs.length]);

  useEffect(() => { void load(false); }, [workspace.organizationId, canRead]);
  const visibleLogs = loadedOrganizationId === workspace.organizationId ? logs : [];

  return <WorkspacePage workspace={workspace} active="Audit logs" title="Audit logs" subtitle="Review security-sensitive activity across your organization.">
    {!canRead ? <article className="panel"><p>You do not have permission to view audit logs.</p></article> : <article className="panel"><div className="panel-header"><div><h2>Activity history</h2><p>Newest activity first</p></div><button className="secondary-button" onClick={() => load(false)}>Refresh</button></div><div className="audit-list">{visibleLogs.map((log) => <details className="audit-row" key={log.id}><summary><span className="audit-action">{humanize(log.action)}</span><span>{log.resource_type}</span><time>{formatDate(log.created_at)}</time></summary><div className="audit-details"><span>Actor: {log.actor_user_id || "system"}</span><span>Resource: {log.resource_id || "—"}</span><span>IP: {log.ip_address || "—"}</span>{Object.keys(log.metadata).length > 0 && <code>{JSON.stringify(log.metadata, null, 2)}</code>}</div></details>)}{!visibleLogs.length && <p className="empty-state">No audit activity recorded yet.</p>}</div>{loadedOrganizationId === workspace.organizationId && hasMore && <button className="secondary-button load-more" onClick={() => load(true)}>Load more</button>}</article>}
  </WorkspacePage>;
}

function message(reason: unknown) { return reason instanceof Error ? reason.message : "Something went wrong"; }
function formatDate(value: string) { return new Date(value).toLocaleString(); }
function humanize(value: string) { return value.toLowerCase().replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase()); }
