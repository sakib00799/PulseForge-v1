"use client";

import { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { logout, Membership, User } from "../lib/api";
import { WorkspaceSidebar } from "./workspace-sidebar";

type Props = {
  active: string;
  title: string;
  subtitle: string;
  user: User;
  memberships: Membership[];
  organizationId: string;
  onOrganizationChange: (id: string) => void;
  children: ReactNode;
};

export function WorkspaceShell(props: Props) {
  const router = useRouter();
  const membership = props.memberships.find((item) => item.organization.id === props.organizationId)
    ?? props.memberships[0];
  const organization = membership.organization;

  async function signOut() {
    await logout();
    router.replace("/");
    router.refresh();
  }

  return <main className="shell">
    <WorkspaceSidebar user={props.user} membership={membership} active={props.active} onLogout={signOut} />
    <section className="content">
      <header className="topbar"><div className="crumb"><span className="crumb-parent">{organization.name}</span><span className="crumb-divider">/</span><span>{props.active}</span></div><label className="organization-picker"><span>Workspace</span><select aria-label="Organization" value={props.organizationId} onChange={(event) => props.onOrganizationChange(event.target.value)}>{props.memberships.map((item) => <option key={item.organization.id} value={item.organization.id}>{item.organization.name}</option>)}</select></label></header>
      <div className="page-heading"><div><p className="eyebrow">PULSEFORGE WORKSPACE</p><h1>{props.title}</h1><p className="muted">{props.subtitle}</p></div></div>
      {props.children}
    </section>
  </main>;
}
