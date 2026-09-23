"use client";

import Link from "next/link";
import { useState } from "react";
import type { Membership, User } from "../lib/api";
import { Icon, type IconName } from "./icons";
import { ThemeToggle } from "./theme-toggle";

type NavItem = { label: string; href: string; icon: IconName; permission?: string };

const primary: NavItem[] = [
  { label: "Overview", href: "/", icon: "overview" },
  { label: "Incidents", href: "/incidents", icon: "incidents" },
  { label: "Events", href: "/events", icon: "events" },
  { label: "Services", href: "/services", icon: "services" },
];
const settings: NavItem[] = [
  { label: "Team", href: "/settings/members", icon: "team", permission: "member:read" },
  { label: "Security", href: "/settings/security", icon: "security" },
  { label: "Audit logs", href: "/settings/audit-logs", icon: "audit", permission: "audit_log:read" },
];

export function WorkspaceSidebar({ user, membership, active, onLogout, incidentCount }: {
  user: User;
  membership: Membership;
  active: string;
  onLogout: () => void | Promise<void>;
  incidentCount?: number;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const organization = membership.organization;

  function links(items: NavItem[]) {
    return items.filter((item) => !item.permission || membership.permissions.includes(item.permission)).map((item) => (
      <Link
        key={item.href}
        href={item.href}
        className={`nav-item${active === item.label ? " active" : ""}`}
        aria-current={active === item.label ? "page" : undefined}
        onClick={() => setMenuOpen(false)}
      >
        <span className="nav-icon"><Icon name={item.icon} /></span>
        <span>{item.label}</span>
        {item.label === "Incidents" && incidentCount !== undefined && incidentCount > 0 && <b>{incidentCount}</b>}
      </Link>
    ));
  }

  return <aside className={`sidebar${menuOpen ? " menu-open" : ""}`}>
    <div className="sidebar-header">
      <Link className="brand brand-link" href="/" onClick={() => setMenuOpen(false)}><span className="brand-mark">PF</span><span>pulseforge</span></Link>
      <button className="menu-toggle" type="button" aria-label={menuOpen ? "Close navigation" : "Open navigation"} aria-expanded={menuOpen} aria-controls="workspace-navigation" onClick={() => setMenuOpen((open) => !open)}><Icon name={menuOpen ? "close" : "menu"} /></button>
    </div>
    <div className="workspace"><span className="avatar">{organization.name.slice(0, 2).toUpperCase()}</span><div><strong>{organization.name}</strong><small>{membership.role.toLowerCase()} workspace</small></div><span className="workspace-indicator" aria-hidden="true" /></div>
    <nav id="workspace-navigation" aria-label="Workspace navigation">
      <p className="nav-heading">WORKSPACE</p>
      {links(primary)}
      <p className="nav-heading">SETTINGS</p>
      {links(settings)}
    </nav>
    <div className="sidebar-bottom"><ThemeToggle /><button className="user" type="button" aria-label={`Sign out ${user.full_name}`} onClick={() => void onLogout()}><span className="avatar navy">{user.full_name.slice(0, 2).toUpperCase()}</span><span className="user-details"><strong>{user.full_name}</strong><small>Sign out</small></span><Icon className="logout-icon" name="logout" /></button></div>
  </aside>;
}
