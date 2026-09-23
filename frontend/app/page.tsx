"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, clearTokens, CreatedApiKey, Incident, isUnauthorizedError, login, logout, Membership, register, sendDemoEvents, Service, TelemetryEvent, User } from "../lib/api";
import { Icon, type IconName } from "../components/icons";
import { WorkspaceSidebar } from "../components/workspace-sidebar";
import { PasswordField } from "../components/password-field";
import { ThemeToggle } from "../components/theme-toggle";

type DashboardData = { services: Service[]; events: TelemetryEvent[]; incidents: Incident[] };
const emptyData: DashboardData = { services: [], events: [], incidents: [] };

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [data, setData] = useState<DashboardData>(emptyData);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [secret, setSecret] = useState<CreatedApiKey | null>(null);
  const [sendingDemo, setSendingDemo] = useState(false);
  const [copied, setCopied] = useState(false);
  const selectedOrganization = useRef(organizationId);
  const dashboardRequest = useRef(0);
  selectedOrganization.current = organizationId;

  async function bootstrap() {
    try {
      const [me, orgs] = await Promise.all([api<User>("/api/v1/auth/me"), api<Membership[]>("/api/v1/organizations")]);
      const savedOrganization = sessionStorage.getItem("pulseforge_organization");
      const selectedOrganization = orgs.some((item) => item.organization.id === savedOrganization)
        ? savedOrganization!
        : orgs[0]?.organization.id ?? "";
      dashboardRequest.current += 1;
      setUser(me); setMemberships(orgs);
      setOrganizationId(selectedOrganization);
      setError("");
    } catch (reason) {
      if (isUnauthorizedError(reason)) clearTokens();
      dashboardRequest.current += 1;
      setUser(null); setMemberships([]); setOrganizationId(""); setData(emptyData); setSecret(null);
      setError(isUnauthorizedError(reason) ? "" : friendlyStartupError(reason));
    }
    finally { setLoading(false); }
  }

  async function loadDashboard(id = organizationId) {
    if (!id) return;
    const request = ++dashboardRequest.current;
    const results = await Promise.allSettled([
      api<Service[]>(`/api/v1/services?organization_id=${id}`),
      api<TelemetryEvent[]>(`/api/v1/events?organization_id=${id}&limit=50`),
      api<Incident[]>(`/api/v1/incidents?organization_id=${id}&limit=50`),
    ]);
    if (request !== dashboardRequest.current || selectedOrganization.current !== id) return;
    const failures = results
      .filter((result): result is PromiseRejectedResult => result.status === "rejected")
      .map((result) => message(result.reason));
    if (results.some((result) => result.status === "rejected" && isUnauthorizedError(result.reason))) {
      dashboardRequest.current += 1;
      clearTokens(); setUser(null); setMemberships([]); setOrganizationId(""); setData(emptyData); setSecret(null); setError("");
      return;
    }
    setData({
      services: results[0].status === "fulfilled" ? results[0].value : [],
      events: results[1].status === "fulfilled" ? results[1].value : [],
      incidents: results[2].status === "fulfilled" ? results[2].value : [],
    });
    setError(failures.join(" | "));
  }

  useEffect(() => { void bootstrap(); }, []);
  useEffect(() => { if (organizationId) void loadDashboard(organizationId); }, [organizationId]);

  if (loading) return <div className="center-screen"><ThemeToggle compact /><div className="loader" />Loading PulseForge...</div>;
  if (!user) return <LoginScreen onSuccess={bootstrap} onRetry={bootstrap} error={error} setError={setError} />;
  if (!memberships.length) return <OrganizationSetup user={user} onCreated={bootstrap} />;

  const membership = memberships.find((item) => item.organization.id === organizationId) ?? memberships[0];
  const org = membership.organization;
  const can = (permission: string) => membership.permissions?.includes(permission) ?? false;
  const activeIncidents = data.incidents.filter((item) => item.status !== "RESOLVED");
  const serviceNames = Object.fromEntries(data.services.map((service) => [service.id, service.slug]));

  async function handleLogout() { dashboardRequest.current += 1; await logout(); setUser(null); setMemberships([]); setOrganizationId(""); setData(emptyData); setSecret(null); setError(""); }
  async function createKey(serviceId: string) {
    try {
      const created = await api<CreatedApiKey>(`/api/v1/services/${serviceId}/api-keys`, { method: "POST", body: JSON.stringify({ name: "Dashboard demo key", scopes: ["events:write"], expires_at: null }) });
      setSecret(created); setCopied(false); setError("");
    } catch (reason) { setError(isUnauthorizedError(reason) ? "" : message(reason)); }
  }
  async function runDemo() {
    if (!secret) return;
    setSendingDemo(true);
    try { await sendDemoEvents(secret.api_key); await loadDashboard(); setError(""); }
    catch (reason) { setError(isUnauthorizedError(reason) ? "" : message(reason)); }
    finally { setSendingDemo(false); }
  }
  async function copySecret() {
    if (!secret) return;
    try { await navigator.clipboard.writeText(secret.api_key); setCopied(true); }
    catch { setError("Could not copy the key. Select and copy it manually."); }
  }
  async function changeIncident(id: string, action: "acknowledge" | "resolve") {
    try { await api(`/api/v1/incidents/${id}/${action}`, { method: "POST" }); await loadDashboard(); }
    catch (reason) { setError(isUnauthorizedError(reason) ? "" : message(reason)); }
  }

  return <main className="shell">
    <WorkspaceSidebar user={user} membership={membership} active="Overview" onLogout={handleLogout} incidentCount={activeIncidents.length} />
    <section className="content">
      <header className="topbar"><div className="crumb"><span className="crumb-parent">{org.name}</span><span className="crumb-divider">/</span><span>Overview</span></div><label className="organization-picker"><span>Workspace</span><select aria-label="Organization" value={organizationId} onChange={(event) => { setData(emptyData); setSecret(null); sessionStorage.setItem("pulseforge_organization", event.target.value); setOrganizationId(event.target.value); }}>{memberships.map((item) => <option key={item.organization.id} value={item.organization.id}>{item.organization.name}</option>)}</select></label></header>
      <div className="page-heading dashboard-heading"><div><p className="eyebrow"><span className="live-dot" />V1 LIVE SYSTEM</p><h1>Hello, {user.full_name.split(" ")[0]}.</h1><p className="muted">Real data from your PulseForge API.</p></div><button className="secondary-button" onClick={() => loadDashboard()}><Icon name="refresh" />Refresh data</button></div>
      {error && <div className="error-banner" role="alert"><span>{error}</span><button type="button" aria-label="Dismiss error" onClick={() => setError("")}><Icon name="close" /></button></div>}
      {secret && <div className="secret-banner"><div><strong>Copy this API key now - it will not be shown again.</strong><code>{secret.api_key}</code></div><div className="secret-actions"><button className="copy-button" type="button" onClick={copySecret}>{copied ? "Copied" : "Copy key"}</button><button onClick={runDemo} disabled={sendingDemo}>{sendingDemo ? "Sending..." : "Send 5 demo failures"}</button></div></div>}
      <section className="metrics" aria-label="Workspace metrics"><Metric label="Active incidents" value={String(activeIncidents.length)} detail="Open or acknowledged" tone="red" icon="incidents" href="/incidents" /><Metric label="Services" value={String(data.services.length)} detail="Registered services" tone="green" icon="services" href="/services" /><Metric label="Recent events" value={String(data.events.length)} detail="Latest 50 events" tone="blue" icon="events" href="/events" /><Metric label="Resolved" value={String(data.incidents.filter((item) => item.status === "RESOLVED").length)} detail="Incident history" tone="orange" icon="check" href="/incidents" /></section>
      {can("service:create") && <CreateService organizationId={organizationId} onCreated={loadDashboard} setError={setError} />}
      <section className="grid-top">
        <article className="panel"><div className="panel-header"><div><h2>Incidents</h2><p>Threshold: 5 matching failures in 60 seconds</p></div><Link className="text-link" href="/incidents">View all<Icon name="arrow" /></Link></div><div className="incident-list">{data.incidents.length ? data.incidents.map((incident) => <div className="incident" key={incident.id}><span className={`severity ${incident.severity.toLowerCase()}`}>{incident.severity}</span><div className="incident-info"><strong>{incident.title}</strong><span>{serviceNames[incident.service_id] ?? incident.service_id} - {formatDate(incident.detected_at)}</span></div><span className="status">{incident.status}</span><div className="row-actions">{can("incident:acknowledge") && incident.status === "OPEN" && <button onClick={() => changeIncident(incident.id, "acknowledge")}>Ack</button>}{can("incident:resolve") && incident.status !== "RESOLVED" && <button onClick={() => changeIncident(incident.id, "resolve")}>Resolve</button>}</div></div>) : <Empty text="No incidents yet. Create a key and send demo failures." />}</div></article>
        <article className="panel"><div className="panel-header"><div><h2>Services</h2><p>Organization service registry</p></div><Link className="text-link" href="/services">View all<Icon name="arrow" /></Link></div><div className="health-list">{data.services.length ? data.services.map((service) => <div className="service-row" key={service.id}><div><strong>{service.name}</strong><small>{service.environment} - {service.status}</small></div>{can("api_key:manage") && <button onClick={() => createKey(service.id)}>Create API key</button>}</div>) : <Empty text="Create your first service above." />}</div></article>
      </section>
      <article className="panel"><div className="panel-header"><div><h2>Recent events</h2><p>API-key authenticated telemetry</p></div><Link className="text-link" href="/events">View all<Icon name="arrow" /></Link></div><div className="event-list">{data.events.length ? data.events.map((event) => <div className="event" key={event.id}><span className="mark">{event.level === "CRITICAL" ? "!" : event.level[0]}</span><div><strong>{event.message}</strong><span><em className={event.level.toLowerCase()}>{event.level}</em> - {event.event_type} - {serviceNames[event.service_id] ?? "service"}</span></div><time>{formatDate(event.occurred_at)}</time></div>) : <Empty text="No telemetry received yet." />}</div></article>
    </section>
  </main>;
}

function LoginScreen({ onSuccess, onRetry, error, setError }: { onSuccess: () => Promise<void>; onRetry: () => Promise<void>; error: string; setError: (value: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [registering, setRegistering] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    setBusy(true); setError("");
    try {
      if (registering) await register(String(form.get("full_name")), email, password);
      else await login(email, password);
      await onSuccess();
    } catch (reason) { setError(message(reason)); }
    finally { setBusy(false); }
  }
  function switchMode() { setRegistering((current) => !current); setError(""); }
  return <main className="auth-shell"><ThemeToggle compact /><section className="auth-card"><div className="brand auth-brand"><span className="brand-mark">PF</span><span>pulseforge</span></div><p className="eyebrow">INCIDENT INTELLIGENCE</p><h1>{registering ? "Create your account" : "Sign in to your workspace"}</h1><p className="muted">{registering ? "Start your PulseForge organization in a minute." : "Welcome back to your incident dashboard."}</p>{error && <div className="error-banner">{error}</div>}{error.startsWith("Cannot reach PulseForge") && <button className="secondary-button" type="button" onClick={() => void onRetry()}>Retry connection</button>}<form onSubmit={submit}>{registering && <label>Full name<input name="full_name" required minLength={1} maxLength={120} autoComplete="name" /></label>}<label>Email<input name="email" type="email" required autoComplete="email" /></label><PasswordField label="Password" name="password" minLength={registering ? 12 : 1} maxLength={128} autoComplete={registering ? "new-password" : "current-password"} hint={registering ? "At least 12 characters" : undefined} /><button className="primary-button" disabled={busy}>{busy ? "Please wait..." : registering ? "Create account" : "Sign in"}</button></form><div className="auth-switch"><span>{registering ? "Already have an account?" : "New to PulseForge?"}</span><button type="button" onClick={switchMode}>{registering ? "Sign in" : "Create account"}</button></div></section></main>;
}

function OrganizationSetup({ user, onCreated }: { user: User; onCreated: () => Promise<void> }) {
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); try { await api("/api/v1/organizations", { method: "POST", body: JSON.stringify({ name: form.get("name"), slug: form.get("slug") }) }); await onCreated(); } catch (reason) { setError(message(reason)); } }
  return <main className="auth-shell"><ThemeToggle compact /><section className="auth-card"><h1>Welcome, {user.full_name}</h1><p className="muted">Create your first organization.</p>{error && <div className="error-banner">{error}</div>}<form onSubmit={submit}><label>Name<input name="name" required placeholder="Acme Corp" /></label><label>Slug<input name="slug" required placeholder="acme-corp" /></label><button className="primary-button">Create organization</button></form></section></main>;
}

function CreateService({ organizationId, onCreated, setError }: { organizationId: string; onCreated: () => Promise<void>; setError: (value: string) => void }) {
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = event.currentTarget; const values = new FormData(form); const slug = slugify(String(values.get("slug"))); try { await api("/api/v1/services", { method: "POST", body: JSON.stringify({ organization_id: organizationId, name: values.get("name"), slug, description: values.get("description") || null, environment: values.get("environment") }) }); form.reset(); setError(""); await onCreated(); } catch (reason) { setError(message(reason)); } }
  return <article className="panel quick-create"><div><h2>Register a service</h2><p className="muted">Needed before generating an ingestion key.</p></div><form onSubmit={submit}><input name="name" required aria-label="Service name" placeholder="Payment Service" /><input name="slug" required aria-label="Service slug" placeholder="payment-service" title="Lowercase URL name; spaces will become hyphens" /><input name="description" aria-label="Service description" placeholder="Optional description" /><select name="environment" aria-label="Environment"><option value="production">production</option><option value="staging">staging</option><option value="development">development</option></select><button className="primary-button">Create service</button></form></article>;
}

function Metric({ label, value, detail, tone, icon, href }: { label: string; value: string; detail: string; tone: string; icon: IconName; href: string }) { return <Link href={href} className="metric"><div className={`metric-icon ${tone}`}><Icon name={icon} /></div><p>{label}</p><strong>{value}</strong><small>{detail}</small></Link>; }
function Empty({ text }: { text: string }) { return <p className="empty-state">{text}</p>; }
function formatDate(value: string) { return new Date(value).toLocaleString(); }
function message(reason: unknown) { return reason instanceof Error ? reason.message : "Something went wrong"; }
function friendlyStartupError(reason: unknown) { return reason instanceof TypeError ? "Cannot reach PulseForge right now. Please try again." : "Your session could not be restored. Please sign in again."; }
function slugify(value: string) { return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
