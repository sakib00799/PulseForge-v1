"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { WorkspacePage } from "../../components/workspace-page";
import { useWorkspace } from "../../hooks/use-workspace";
import { api, Incident, Service } from "../../lib/api";

export default function IncidentsPage() {
  const workspace = useWorkspace();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [status, setStatus] = useState("");
  const [loadedScope, setLoadedScope] = useState("");
  const scope = `${workspace.organizationId}:${status}`;
  const currentScope = useRef(scope);
  const requestNumber = useRef(0);
  currentScope.current = scope;

  const load = useCallback(async () => {
    if (!workspace.organizationId) return;
    const requestedScope = `${workspace.organizationId}:${status}`;
    const request = ++requestNumber.current;
    try {
      const suffix = status ? `&status=${status}` : "";
      const [incidentData, serviceData] = await Promise.all([
        api<Incident[]>(`/api/v1/incidents?organization_id=${workspace.organizationId}&limit=100${suffix}`),
        api<Service[]>(`/api/v1/services?organization_id=${workspace.organizationId}`),
      ]);
      if (request !== requestNumber.current || requestedScope !== currentScope.current) return;
      setIncidents(incidentData); setServices(serviceData); setLoadedScope(requestedScope); workspace.setError("");
    } catch (reason) {
      if (request === requestNumber.current && requestedScope === currentScope.current) workspace.setError(message(reason));
    }
  }, [workspace.organizationId, status]);
  useEffect(() => { void load(); }, [load]);
  const visibleIncidents = loadedScope === scope ? incidents : [];
  const visibleServices = loadedScope.startsWith(`${workspace.organizationId}:`) ? services : [];

  async function transition(id: string, action: "acknowledge" | "resolve") {
    try { await api(`/api/v1/incidents/${id}/${action}`, { method: "POST" }); await load(); }
    catch (reason) { workspace.setError(message(reason)); }
  }
  const names = Object.fromEntries(visibleServices.map((service) => [service.id, service.name]));

  return <WorkspacePage workspace={workspace} active="Incidents" title="Incidents" subtitle="Triage, acknowledge, and resolve detected failures.">
    <article className="panel"><div className="panel-header"><div><h2>Incident queue <span className="count">{visibleIncidents.length}</span></h2><p>Filter by current lifecycle state.</p></div><div className="filter-actions"><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option><option>OPEN</option><option>ACKNOWLEDGED</option><option>RESOLVED</option></select><button className="secondary-button" onClick={load}>Refresh</button></div></div>
      <div className="incident-list">{visibleIncidents.map((incident) => <div className="incident" key={incident.id}><span className="severity sev-2">{incident.severity}</span><div className="incident-info"><strong>{incident.title}</strong><span>{names[incident.service_id] || incident.service_id} · {formatDate(incident.detected_at)}</span></div><span className="status">{incident.status}</span><div className="row-actions">{workspace.can("incident:acknowledge") && incident.status === "OPEN" && <button onClick={() => transition(incident.id, "acknowledge")}>Acknowledge</button>}{workspace.can("incident:resolve") && incident.status !== "RESOLVED" && <button onClick={() => transition(incident.id, "resolve")}>Resolve</button>}</div></div>)}{!visibleIncidents.length && <p className="empty-state">No incidents match this filter.</p>}</div>
    </article>
  </WorkspacePage>;
}

function message(reason: unknown) { return reason instanceof Error ? reason.message : "Something went wrong"; }
function formatDate(value: string) { return new Date(value).toLocaleString(); }
