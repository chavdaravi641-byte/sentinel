"use client";

import { useState } from "react";
import { Loader2, RefreshCw, ScrollText } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { IamEmptyState } from "@/components/iam/empty-state";
import { endpoints } from "@/lib/api";
import { useIamList } from "@/lib/iam-hooks";
import { cn } from "@/lib/utils";

interface AuditRecord {
  id: string;
  at: string;
  actor: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  department_id: string | null;
  severity: string;
  access_mode: string | null;
  old_value: unknown;
  new_value: unknown;
}

const SEVERITY_DOT: Record<string, string> = {
  INFO: "bg-success",
  WARNING: "bg-amber-400",
  CRITICAL: "bg-destructive",
};

function fmtValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") {
    try {
      return JSON.stringify(v);
    } catch {
      return String(v);
    }
  }
  return String(v);
}

export default function IamAuditPage() {
  const { data, loading, error, refetch } = useIamList<AuditRecord>(
    endpoints.iamAudit,
  );
  const [actionFilter, setActionFilter] = useState("");
  const [applied, setApplied] = useState("");

  async function handleSearch() {
    setApplied(actionFilter.trim());
  }

  const filtered = (data ?? []).filter((r) => {
    const q = applied.toLowerCase();
    if (!q) return true;
    return r.action.toLowerCase().includes(q);
  });

  return (
    <>
      <PageHeader
        eyebrow="Enterprise IAM"
        title="Audit Log"
        description="Immutable, jurisdiction-scoped audit trail of IAM events"
        actions={
          <Button variant="outline" onClick={refetch} className="font-mono uppercase tracking-widest">
            <RefreshCw /> Refresh
          </Button>
        }
      />

      <Panel bodyClassName="flex flex-wrap items-center gap-3 p-3">
        <Input
          placeholder="Filter by action (e.g. department.create)…"
          className="max-w-xs font-mono text-xs"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void handleSearch();
          }}
        />
        <Button
          variant="outline"
          onClick={() => void handleSearch()}
          className="font-mono uppercase tracking-widest"
        >
          Apply filter
        </Button>
        <Badge variant="outline" className="ml-auto font-mono text-[9px] uppercase">
          {filtered.length} records
        </Badge>
      </Panel>

      <div className="mt-5">
        <Panel bodyClassName="overflow-x-auto p-0">
          {error ? (
            <div className="p-6 font-mono text-xs text-destructive">{error}</div>
          ) : loading ? (
            <div className="flex items-center gap-2 p-6 font-mono text-xs text-muted-foreground">
              <Loader2 className="animate-spin" /> Loading audit trail…
            </div>
          ) : filtered.length === 0 ? (
            <IamEmptyState
              title="No audit events"
              description={applied ? "No events match the current action filter." : "No IAM events have been recorded yet."}
            />
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  <th className="px-4 py-2">Time</th>
                  <th className="px-4 py-2">Actor</th>
                  <th className="px-4 py-2">Action</th>
                  <th className="px-4 py-2">Resource</th>
                  <th className="px-4 py-2">Severity</th>
                  <th className="px-4 py-2">Delta</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id} className="border-b border-border/60 last:border-0 hover:bg-accent/40">
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[10px] text-muted-foreground">
                      {new Date(r.at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs">{r.actor}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{r.action}</td>
                    <td className="px-4 py-2.5 font-mono text-[10px] text-muted-foreground">
                      <span className="flex items-center gap-1.5">
                        <ScrollText className="h-3 w-3 text-primary" />
                        {r.resource_type ?? "—"}
                        {r.resource_id ? ` · ${r.resource_id.slice(0, 8)}` : ""}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge
                        variant="outline"
                        className={cn(
                          "gap-1.5 font-mono text-[9px] uppercase",
                        )}
                      >
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            SEVERITY_DOT[r.severity] ?? "bg-muted-foreground",
                          )}
                        />
                        {r.severity}
                      </Badge>
                    </td>
                    <td className="max-w-[260px] truncate px-4 py-2.5 font-mono text-[10px] text-muted-foreground">
                      {fmtValue(r.new_value)}
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
