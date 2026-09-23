"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearTokens, isUnauthorizedError, Membership, User } from "../lib/api";

const ORGANIZATION_KEY = "pulseforge_organization";

export function useWorkspace() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [organizationId, setOrganizationIdState] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const bootstrap = useCallback(async () => {
    try {
      const [me, organizations] = await Promise.all([
        api<User>("/api/v1/auth/me"),
        api<Membership[]>("/api/v1/organizations"),
      ]);
      if (!organizations.length) {
        router.replace("/");
        return;
      }
      const saved = sessionStorage.getItem(ORGANIZATION_KEY);
      const selected = organizations.some((item) => item.organization.id === saved)
        ? saved!
        : organizations[0].organization.id;
      setUser(me);
      setMemberships(organizations);
      setOrganizationIdState(selected);
      setError("");
    } catch (reason) {
      if (isUnauthorizedError(reason)) {
        clearTokens();
        router.replace("/");
      } else {
        setError(reason instanceof Error ? reason.message : "Could not load your workspace");
      }
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => { void bootstrap(); }, [bootstrap]);

  function setOrganizationId(value: string) {
    sessionStorage.setItem(ORGANIZATION_KEY, value);
    setOrganizationIdState(value);
  }

  const membership = useMemo(
    () => memberships.find((item) => item.organization.id === organizationId) ?? memberships[0],
    [memberships, organizationId],
  );

  return {
    user, memberships, organizationId, setOrganizationId, membership,
    loading, error, setError, reloadWorkspace: bootstrap,
    can: (permission: string) => membership?.permissions.includes(permission) ?? false,
  };
}

export type Workspace = ReturnType<typeof useWorkspace>;
