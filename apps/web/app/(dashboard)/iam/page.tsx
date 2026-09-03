"use client";

import { useMemo } from "react";
import {
  Building2,
  KeyRound,
  Loader2,
  ScrollText,
  Shield,
  ShieldAlert,
  Unlock,
  Users,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { endpoints } from "@/lib/api";
import { useIamList, useIamPrincipal } from "@/lib/iam-hooks";

interface DeptNode {
  id: string;
  code: string;
  name: string;
  type: string;
  hierarchy_level: number;
  children?: DeptNode[];
}

const LINKS = [
  { href: "/iam/departments", label: "Departments", icon: Building2 },
  { href: "/iam/officers", label: "Officers", icon: Users },
  { href: "/iam/roles", label: "Roles", icon: KeyRound },
  { href: "/iam/audit", label: "Audit Log", icon: ScrollText },
  { href: "/iam/emergency", label: "Emergency", icon: ShieldAlert },
] as const;

function TreeView({ node, depth = 0 }: { node: DeptNode; depth?: number }) {
  return (
    <li>
      <div
        className="flex items-center gap-2 py-1 font-mono text-xs"
        style={{ paddingLeft: depth * 16 }}
      >
        <Building2 className="h-3 w-3 text-primary" />
        <span className="text-foreground">{node.name}</span>
        <Badge variant="outline" className="font-mono text-[9px] uppercase">
          {node.code}
        </Badge>
        <span className="text-[9px] uppercase tracking-widest text-muted-foreground">
          L{node.hierarchy_level}
        </span>
      </div>
      {node.children?.length ? (
        <ul>
          {node.children.map((c) => (
            <TreeView key={c.id} node={c} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export default function IamOverviewPage() {
  const { meta, connecting, connect } = useIamPrincipal();
  const departments = useIamList<DeptNode>(endpoints.iamDepartmentTree);
  const officers = useIamList<Record<string, unknown>>(endpoints.iamOfficers);
  const roles = useIamList<Record<string, unknown>>(endpoints.iamRoles);

  const forest = useMemo(
    () => departments.data ?? [],
    [departments.data],
  );

  async function handleConnect() {
    try {
      await connect();
      toast.success("IAM session established.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "IAM connect failed.");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Identity & Access"
        title="IAM"
        description="Enterprise identity, role-based access control and audit for the federation"
        actions={
          <Button
            onClick={handleConnect}
            disabled={connecting || meta !== null}
            className="font-mono uppercase tracking-widest"
          >
            {connecting ? (
              <Loader2 className="animate-spin" />
            ) : meta ? (
              <Shield className="h-4 w-4" />
            ) : (
              <Unlock className="h-4 w-4" />
            )}
            {meta ? "Connected" : "Connect session"}
          </Button>
        }
      />

      {meta && (
        <Panel
          title="Principal"
          subtitle="federation session"
          bodyClassName="flex flex-wrap items-center gap-6 p-4"
        >
          <div className="flex items-center gap-2 font-mono text-sm">
            <span className="text-primary">{meta.full_name}</span>
            <Badge className="font-mono text-[9px] uppercase">{meta.badge_number}</Badge>
          </div>
          <div className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            role · {meta.role}
          </div>
          <div className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            officer · {meta.officer_id.slice(0, 8)}
          </div>
          <Badge variant="outline" className="gap-1.5 font-mono text-[9px] uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-success radar-pulse" />
            session active
          </Badge>
        </Panel>
      )}

      <div className="mt-5 grid gap-4 md:grid-cols-3">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href}>
            <Panel
              title={l.label}
              right={<l.icon className="h-4 w-4 text-primary" />}
              bodyClassName="flex items-center justify-between p-4"
            >
              <div className="flex items-center gap-2">
                <l.icon className="h-4 w-4 text-primary" />
                <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
                  {l.label}
                </span>
              </div>
              <span className="font-mono text-[10px] text-primary">&rarr;</span>
            </Panel>
          </Link>
        ))}
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <Panel
          title="Department Hierarchy"
          subtitle="jurisdiction tree"
          right={
            <Badge variant="outline" className="font-mono text-[9px] uppercase">
              {forest.length} roots
            </Badge>
          }
          bodyClassName="max-h-[420px] overflow-y-auto p-3"
        >
          {departments.loading ? (
            <Loader2 className="animate-spin text-primary" />
          ) : (
            <ul>
              {forest.map((n) => (
                <TreeView key={n.id} node={n} />
              ))}
            </ul>
          )}
        </Panel>

        <div className="grid gap-4">
          <Panel
            title="Directory"
            subtitle="registered identities"
            bodyClassName="p-4"
          >
            <div className="flex items-center gap-3">
              <Users className="h-4 w-4 text-primary" />
              <span className="font-mono text-sm">Officers</span>
              <span className="ml-auto font-mono text-lg text-foreground">
                {officers.loading ? "–" : officers.data?.length ?? 0}
              </span>
            </div>
          </Panel>
          <Panel
            title="Roles"
            subtitle="RBAC catalogue"
            bodyClassName="p-4"
          >
            <div className="flex items-center gap-3">
              <KeyRound className="h-4 w-4 text-primary" />
              <span className="font-mono text-sm">Defined roles</span>
              <span className="ml-auto font-mono text-lg text-foreground">
                {roles.loading ? "–" : roles.data?.length ?? 0}
              </span>
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
