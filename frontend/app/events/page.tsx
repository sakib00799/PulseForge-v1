"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { WorkspacePage } from "../../components/workspace-page";
import { useWorkspace } from "../../hooks/use-workspace";
import { api, Service, TelemetryEvent } from "../../lib/api";

export default function EventsPage() {
  const workspace = useWorkspace();
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [level, setLevel] = useState("");
  const [serviceFilter, setServiceFilter] = useState({ organizationId: "", serviceId: "" });
  const serviceId = serviceFilter.organizationId === workspace.organizationId ? serviceFilter.serviceId : "";
  const [loadedScope, setLoadedScope] = useState("");
  const scope = `${workspace.organizationId}:${level}:${serviceId}`;
  const currentScope = useRef(scope);
  const requestNumber = useRef(0);
  currentScope.current = scope;

  const load = useCallback(async () => {
    if (!workspace.organizationId) return;
    const requestedScope = `${workspace.organizationId}:${level}:${serviceId}`;
    const request = ++requestNumber.current;
    try {
      const query = new URLSearchParams({ organization_id: workspace.organizationId, limit: "100" });
      if (level) query.set("level", level); if (serviceId) query.set("service_id", serviceId);
      const [eventData, serviceData] = await Promise.all([api<TelemetryEvent[]>(`/api/v1/events?${query}`), api<Service[]>(`/api/v1/services?organization_id=${workspace.organizationId}`)]);
      if (request !== requestNumber.current || requestedScope !== currentScope.current) return;
      setEvents(eventData); setServices(serviceData); setLoadedScope(requestedScope); workspace.setError("");
    } catch (reason) {
      if (request === requestNumber.current && requestedScope === currentScope.current) workspace.setError(message(reason));
    }
  }, [workspace.organizationId, level, serviceId]);
  useEffect(() => { void load(); }, [load]);
  const visibleEvents = loadedScope === scope ? events : [];
  const visibleServices = loadedScope.startsWith(`${workspace.organizationId}:`) ? services : [];
  const names = Object.fromEntries(visibleServices.map((service) => [service.id, service.name]));

  return <WorkspacePage workspace={workspace} active="Events" title="Telemetry events" subtitle="Inspect recent service signals received through ingestion API keys.">
    <article className="panel"><div className="panel-header"><div><h2>Recent events <span className="count">{visibleEvents.length}</span></h2><p>Showing up to 100 newest events.</p></div><div className="filter-actions"><select value={serviceId} onChange={(event) => setServiceFilter({ organizationId: workspace.organizationId, serviceId: event.target.value })}><option value="">All services</option>{visibleServices.map((service) => <option value={service.id} key={service.id}>{service.name}</option>)}</select><select value={level} onChange={(event) => setLevel(event.target.value)}><option value="">All levels</option><option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option><option>CRITICAL</option></select><button className="secondary-button" onClick={load}>Refresh</button></div></div>
      <div className="event-list">{visibleEvents.map((item) => <div className="event" key={item.id}><span className="mark">{item.level[0]}</span><div><strong>{item.message}</strong><span><em className={item.level.toLowerCase()}>{item.level}</em> · {item.event_type} · {names[item.service_id] || item.service_id}</span></div><time>{formatDate(item.occurred_at)}</time></div>)}{!visibleEvents.length && <p className="empty-state">No events match these filters.</p>}</div>
    </article>
  </WorkspacePage>;
}

function message(reason: unknown) { return reason instanceof Error ? reason.message : "Something went wrong"; }
function formatDate(value: string) { return new Date(value).toLocaleString(); }
