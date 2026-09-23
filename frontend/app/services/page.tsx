"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { WorkspacePage } from "../../components/workspace-page";
import { useWorkspace } from "../../hooks/use-workspace";
import { api, CreatedApiKey, Service } from "../../lib/api";

export default function ServicesPage() {
  const workspace = useWorkspace();
  const [services, setServices] = useState<Service[]>([]);
  const [secret, setSecret] = useState<CreatedApiKey | null>(null);
  const [secretOrganizationId, setSecretOrganizationId] = useState("");
  const [loadedOrganizationId, setLoadedOrganizationId] = useState("");
  const currentOrganizationId = useRef(workspace.organizationId);
  const requestNumber = useRef(0);
  currentOrganizationId.current = workspace.organizationId;
  const load = useCallback(async () => {
    const organizationId = workspace.organizationId;
    if (!organizationId) return;
    const request = ++requestNumber.current;
    try {
      const result = await api<Service[]>(`/api/v1/services?organization_id=${organizationId}`);
      if (request !== requestNumber.current || organizationId !== currentOrganizationId.current) return;
      setServices(result); setLoadedOrganizationId(organizationId); workspace.setError("");
    } catch (reason) {
      if (request === requestNumber.current && organizationId === currentOrganizationId.current) workspace.setError(message(reason));
    }
  }, [workspace.organizationId]);
  useEffect(() => { setSecret(null); void load(); }, [load]);
  const visibleServices = loadedOrganizationId === workspace.organizationId ? services : [];

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form);
    try { await api("/api/v1/services", { method: "POST", body: JSON.stringify({ organization_id: workspace.organizationId, name: values.get("name"), slug: slugify(String(values.get("slug"))), description: values.get("description") || null, environment: values.get("environment") }) }); form.reset(); await load(); }
    catch (reason) { workspace.setError(message(reason)); }
  }
  async function createKey(serviceId: string) {
    const organizationId = workspace.organizationId;
    try {
      const created = await api<CreatedApiKey>(`/api/v1/services/${serviceId}/api-keys`, { method: "POST", body: JSON.stringify({ name: "Dashboard ingestion key", scopes: ["events:write"], expires_at: null }) });
      if (organizationId === currentOrganizationId.current) {
        setSecret(created); setSecretOrganizationId(organizationId);
      }
    }
    catch (reason) { workspace.setError(message(reason)); }
  }

  return <WorkspacePage workspace={workspace} active="Services" title="Services" subtitle="Manage monitored applications and their ingestion credentials.">
    {secret && secretOrganizationId === workspace.organizationId && <div className="secret-banner"><div><strong>Copy this key now. It will not be shown again.</strong><code>{secret.api_key}</code></div><button onClick={() => navigator.clipboard.writeText(secret.api_key)}>Copy key</button></div>}
    {workspace.can("service:create") && <article className="panel form-panel"><div><h2>Register a service</h2><p className="muted">Use a lowercase URL-safe slug.</p></div><form onSubmit={create}><input name="name" required aria-label="Service name" placeholder="Payment Service" /><input name="slug" required aria-label="Service slug" placeholder="payment-service" /><input name="description" aria-label="Service description" placeholder="Optional description" /><select name="environment" aria-label="Environment" defaultValue="production"><option>production</option><option>staging</option><option>development</option></select><button className="primary-button">Create service</button></form></article>}
    <article className="panel"><div className="panel-header"><div><h2>Service registry <span className="count">{visibleServices.length}</span></h2><p>Services in the selected organization.</p></div><button className="secondary-button" onClick={load}>Refresh</button></div><div className="data-list">{visibleServices.map((service) => <div className="data-row" key={service.id}><div><strong>{service.name}</strong><small>{service.slug} · {service.environment} · {service.status}</small>{service.description && <small>{service.description}</small>}</div>{workspace.can("api_key:manage") && <button className="secondary-button" onClick={() => createKey(service.id)}>Create API key</button>}</div>)}{!visibleServices.length && <p className="empty-state">No services registered yet.</p>}</div></article>
  </WorkspacePage>;
}

function message(reason: unknown) { return reason instanceof Error ? reason.message : "Something went wrong"; }
function slugify(value: string) { return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
