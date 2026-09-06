"use client";

import { useState } from "react";
import { Building2, Loader2, RefreshCw, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { IamEmptyState } from "@/components/iam/empty-state";
import { endpoints } from "@/lib/api";
import { iamFetch } from "@/lib/iam";
import { useIamList } from "@/lib/iam-hooks";

interface Department {
  id: string;
  code: string;
  name: string;
  dept_type: string;
  hierarchy_level: number;
  jurisdiction_scope: string;
  district: string | null;
  state: string | null;
  contact_email: string | null;
  description: string | null;
  parent_id: string | null;
}

export default function IamDepartmentsPage() {
  const { data, loading, error, refetch } = useIamList<Department>(
    endpoints.iamDepartments,
  );
  const [search, setSearch] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);

  const filtered = (data ?? []).filter((d) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      d.name.toLowerCase().includes(q) ||
      d.code.toLowerCase().includes(q) ||
      (d.district ?? "").toLowerCase().includes(q)
    );
  });

  async function handleDelete(d: Department) {
    setRemoving(d.id);
    try {
      await iamFetch(endpoints.iamDepartment(d.id), { method: "DELETE" });
      toast.success(`Department ${d.name} marked deleted.`);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setRemoving(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Enterprise IAM"
        title="Departments"
        description="Hierarchical police department registry with jurisdiction scoping"
        actions={
          <Button
            variant="outline"
            onClick={refetch}
            className="font-mono uppercase tracking-widest"
          >
            <RefreshCw /> Refresh
          </Button>
        }
      />

      <Panel bodyClassName="flex flex-wrap items-center gap-3 p-3">
        <div className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search code / name / district…"
            className="pl-9 font-mono text-xs"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Badge variant="outline" className="ml-auto font-mono text-[9px] uppercase">
          {filtered.length} visible
        </Badge>
      </Panel>

      <div className="mt-5">
        <Panel bodyClassName="overflow-x-auto p-0">
          {error ? (
            <div className="p-6 font-mono text-xs text-destructive">{error}</div>
          ) : loading ? (
            <div className="flex items-center gap-2 p-6 font-mono text-xs text-muted-foreground">
              <Loader2 className="animate-spin" /> Loading registry…
            </div>
          ) : filtered.length === 0 ? (
            <IamEmptyState
              title="No departments found"
              description={search ? "No departments match the current search." : "Register a department to establish an IAM boundary."}
            />
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  <th className="px-4 py-2">Code</th>
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Jurisdiction</th>
                  <th className="px-4 py-2">District / State</th>
                  <th className="px-4 py-2">Lvl</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((d) => (
                  <tr
                    key={d.id}
                    className="border-b border-border/60 last:border-0 hover:bg-accent/40"
                  >
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2 font-mono text-xs font-semibold">
                        <Building2 className="h-3.5 w-3.5 text-primary" />
                        {d.code}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs">{d.name}</td>
                    <td className="px-4 py-2.5">
                      <Badge variant="outline" className="font-mono text-[9px] uppercase">
                        {d.dept_type}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[10px] uppercase text-muted-foreground">
                      {d.jurisdiction_scope}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-muted-foreground">
                      {d.district ?? "—"} / {d.state ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs">{d.hierarchy_level}</td>
                    <td className="px-4 py-2.5 text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete department ${d.name}`}
                        disabled={removing === d.id}
                        onClick={() => void handleDelete(d)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </>
  );
}
