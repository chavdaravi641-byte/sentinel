"use client";

import { useState } from "react";
import { KeyRound, ListChecks, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { IamEmptyState } from "@/components/iam/empty-state";
import { endpoints } from "@/lib/api";
import { iamFetch } from "@/lib/iam";
import { useIamList } from "@/lib/iam-hooks";
import { cn } from "@/lib/utils";

interface Role {
  id: string;
  code: string;
  name: string;
  description: string | null;
  jurisdiction_scope: string;
  is_system: boolean;
  is_active: boolean;
}

export default function IamRolesPage() {
  const { data, loading, error, refetch } = useIamList<Role>(endpoints.iamRoles);
  const [selected, setSelected] = useState<Role | null>(null);
  const [perms, setPerms] = useState<string[] | null>(null);
  const [permLoading, setPermLoading] = useState(false);

  async function handleSelect(role: Role) {
    setSelected(role);
    setPerms(null);
    setPermLoading(true);
    try {
      const p = await iamFetch<string[]>(endpoints.iamRolePermissions(role.id));
      setPerms(p);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load permissions.");
      setPerms([]);
    } finally {
      setPermLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Enterprise IAM"
        title="Roles"
        description="RBAC role catalogue with permission sets"
        actions={
          <Button variant="outline" onClick={refetch} className="font-mono uppercase tracking-widest">
            <RefreshCw /> Refresh
          </Button>
        }
      />

      <div className="mt-2 grid gap-4 lg:grid-cols-2">
        <Panel bodyClassName="p-0">
          {error ? (
            <div className="p-6 font-mono text-xs text-destructive">{error}</div>
          ) : loading ? (
            <div className="flex items-center gap-2 p-6 font-mono text-xs text-muted-foreground">
              <Loader2 className="animate-spin" /> Loading roles…
            </div>
          ) : (data ?? []).length === 0 ? (
            <IamEmptyState
              title="No roles available"
              description="The role catalogue is empty for the current jurisdiction."
            />
          ) : (
            <ul>
              {(data ?? []).map((r) => (
                <li key={r.id}>
                  <button
                    onClick={() => void handleSelect(r)}
                    className={cn(
                      "flex w-full items-center gap-3 border-b border-border/60 px-4 py-2.5 text-left last:border-0 hover:bg-accent/40",
                      selected?.id === r.id && "bg-accent/60",
                    )}
                  >
                    <KeyRound className="h-4 w-4 text-primary" />
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 font-mono text-xs font-semibold">
                        {r.name}
                        {r.is_system && (
                          <Badge variant="outline" className="font-mono text-[8px] uppercase">
                            system
                          </Badge>
                        )}
                      </p>
                      <p className="truncate font-mono text-[10px] text-muted-foreground">
                        {r.description ?? r.code}
                      </p>
                    </div>
                    <Badge variant="outline" className="font-mono text-[9px] uppercase">
                      {r.jurisdiction_scope}
                    </Badge>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title={selected ? `Permissions · ${selected.code}` : "Permission Set"}
          subtitle="assigned codes"
          right={<ListChecks className="h-4 w-4 text-primary" />}
          bodyClassName="max-h-[460px] overflow-y-auto p-4"
        >
          {!selected ? (
            <p className="font-mono text-xs text-muted-foreground">
              Select a role to inspect its permission set.
            </p>
          ) : permLoading ? (
            <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
              <Loader2 className="animate-spin" /> Resolving permissions…
            </div>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {perms?.map((p) => (
                <Badge key={p} variant="outline" className="font-mono text-[9px]">
                  {p}
                </Badge>
              ))}
              {perms?.length === 0 && (
                <p className="font-mono text-xs text-muted-foreground">
                  No explicit permission codes assigned (role may inherit).
                </p>
              )}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
