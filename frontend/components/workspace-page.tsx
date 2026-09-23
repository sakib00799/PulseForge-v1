"use client";

import { ReactNode } from "react";
import { WorkspaceShell } from "./workspace-shell";
import { Workspace } from "../hooks/use-workspace";

export function WorkspacePage({ workspace, active, title, subtitle, children }: { workspace: Workspace; active: string; title: string; subtitle: string; children: ReactNode }) {
  if (workspace.loading) return <div className="center-screen"><div className="loader" />Loading workspace...</div>;
  if (!workspace.user || !workspace.membership) {
    if (workspace.error) return <div className="center-screen"><p>{workspace.error}</p><button className="secondary-button" onClick={() => void workspace.reloadWorkspace()}>Try again</button></div>;
    return <div className="center-screen">Redirecting to sign in...</div>;
  }
  return <WorkspaceShell active={active} title={title} subtitle={subtitle} user={workspace.user} memberships={workspace.memberships} organizationId={workspace.organizationId} onOrganizationChange={workspace.setOrganizationId}>
    {workspace.error && <div className="error-banner" role="alert"><span>{workspace.error}</span><button type="button" aria-label="Dismiss error" onClick={() => workspace.setError("")}>×</button></div>}
    {children}
  </WorkspaceShell>;
}
