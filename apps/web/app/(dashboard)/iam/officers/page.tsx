"use client";

import { useState } from "react";
import { Loader2, RefreshCw, Search, ShieldCheck, UserX } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { endpoints } from "@/lib/api";
import { iamFetch } from "@/lib/iam";
import { useIamList } from "@/lib/iam-hooks";

interface Officer {
  id: string;
  badge_number: string;
  full_name: string;
  email: string;
  rank: string;
  designation: string | null;
  status: string;
  department_id: string;
  role_id: string | null;
}

export default function IamOfficersPage() {
  const { data, loading, error, refetch } = useIamList<Officer>(
    endpoints.iamOfficers,
  );
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const filtered = (data ?? []).filter((o) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      o.full_name.toLowerCase().includes(q) ||
      o.badge_number.toLowerCase().includes(q) ||
      o.email.toLowerCase().includes(q)
    );
  });

  async function handleToggle(o: Officer) {
    const target = o.status === "active" ? "suspended" : "active";
    setBusy(o.id);
    try {
      await iamFetch(endpoints.iamOfficerStatus(o.id), {
        method: "PUT",
        body: { status: target },
      });
      toast.success(`${o.badge_number} → ${target}.`);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Status update failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Enterprise IAM"
        title="Officers"
        description="Officer directory with rank, role and account state"
        actions={
          <Button variant="outline" onClick={refetch} className="font-mono uppercase tracking-widest">
            <RefreshCw /> Refresh
          </Button>
        }
      />

      <Panel bodyClassName="flex flex-wrap items-center gap-3 p-3">
        <div className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search badge / name / email…"
            className="pl-9 font-mono text-xs"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Badge variant="outline" className="ml-auto font-mono text-[9px] uppercase">
          {filtered.length} officers
        </Badge>
      </Panel>

      <div className="mt-5">
        <Panel bodyClassName="overflow-x-auto p-0">
          {error ? (
            <div className="p-6 font-mono text-xs text-destructive">{error}</div>
          ) : loading ? (
            <div className="flex items-center gap-2 p-6 font-mono text-xs text-muted-foreground">
              <Loader2 className="animate-spin" /> Loading directory…
            </div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  <th className="px-4 py-2">Badge</th>
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Rank</th>
                  <th className="px-4 py-2">Designation</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((o) => {
                  const active = o.status === "active";
                  return (
                    <tr
                      key={o.id}
                      className="border-b border-border/60 last:border-0 hover:bg-accent/40"
                    >
                      <td className="px-4 py-2.5 font-mono text-xs font-semibold">
                        {o.badge_number}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="font-mono text-xs">{o.full_name}</span>
                        <span className="block font-mono text-[10px] text-muted-foreground">
                          {o.email}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge variant="outline" className="font-mono text-[9px] uppercase">
                          {o.rank}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[11px] text-muted-foreground">
                        {o.designation ?? "—"}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge
                          variant={active ? "outline" : "secondary"}
                          className={
                            active
                              ? "gap-1.5 font-mono text-[9px] uppercase"
                              : "font-mono text-[9px] uppercase"
                          }
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              active ? "bg-success" : "bg-destructive"
                            }`}
                          />
                          {o.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={busy === o.id}
                          onClick={() => void handleToggle(o)}
                          className="font-mono text-[10px] uppercase tracking-widest"
                        >
                          {active ? <UserX className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                          {active ? "Suspend" : "Activate"}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </>
  );
}
