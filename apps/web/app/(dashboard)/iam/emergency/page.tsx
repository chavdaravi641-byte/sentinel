"use client";

import { useState } from "react";
import { CheckCircle2, Loader2, RefreshCw, ShieldAlert, XCircle } from "lucide-react";
import { toast } from "sonner";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { IamEmptyState } from "@/components/iam/empty-state";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { endpoints } from "@/lib/api";
import { iamFetch } from "@/lib/iam";
import { useIamList } from "@/lib/iam-hooks";
import { cn } from "@/lib/utils";

interface Emergency {
  id: string;
  officer_id: string;
  department_id: string;
  reason: string;
  case_reference: string | null;
  status: string;
  grant: string;
  duration_seconds: number;
  created_at: string;
  expires_at: string | null;
}

const STYLE: Record<string, string> = {
  REQUESTED: "text-amber-300",
  APPROVED: "text-primary",
  ACTIVE: "text-success",
  REVOKED: "text-destructive",
  EXPIRED: "text-muted-foreground",
};

const requestSchema = z.object({
  reason: z.string().min(4, "Reason required."),
  case_reference: z.string().optional(),
  duration_seconds: z.coerce.number().int().min(60).max(86400),
});

type RequestValues = z.infer<typeof requestSchema>;

export default function IamEmergencyPage() {
  const { data, loading, error, refetch } = useIamList<Emergency>(
    endpoints.iamEmergency,
  );
  const [busy, setBusy] = useState<string | null>(null);

  const form = useForm<RequestValues>({
    resolver: zodResolver(requestSchema),
    defaultValues: {
      reason: "",
      case_reference: "",
      duration_seconds: 1800,
    },
  });

  async function handleSubmit(values: RequestValues) {
    try {
      await iamFetch(endpoints.iamEmergencyRequest, {
        method: "POST",
        body: {
          reason: values.reason,
          case_reference: values.case_reference || undefined,
          duration_seconds: values.duration_seconds,
        },
      });
      toast.success("Emergency access requested.");
      form.reset();
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Request failed.");
    }
  }

  async function handleAction(id: string, action: "approve" | "activate" | "revoke") {
    setBusy(id);
    try {
      const endpoint =
        action === "approve"
          ? endpoints.iamEmergencyApprove(id)
          : action === "activate"
            ? endpoints.iamEmergencyActivate(id)
            : endpoints.iamEmergencyRevoke(id);
      await iamFetch(endpoint, {
        method: "POST",
        body: action === "approve" ? { approve: true } : undefined,
      });
      toast.success(`Emergency ${action}d.`);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `${action} failed.`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Enterprise IAM"
        title="Emergency Access"
        description="Break-glass requests, approvals and automatic expiry"
        actions={
          <Button variant="outline" onClick={refetch} className="font-mono uppercase tracking-widest">
            <RefreshCw /> Refresh
          </Button>
        }
      />

      <div className="mt-2 grid gap-4 lg:grid-cols-3">
        <Panel
          title="Request"
          subtitle="break-glass"
          right={<ShieldAlert className="h-4 w-4 text-primary" />}
        >
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-3" noValidate>
              <FormField
                control={form.control}
                name="reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                      Justification
                    </FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="Urgent cross-department read…" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-2 gap-3">
                <FormField
                  control={form.control}
                  name="case_reference"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                        Case ref
                      </FormLabel>
                      <FormControl>
                        <Input {...field} placeholder="C-1234" />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="duration_seconds"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                        Duration (s)
                      </FormLabel>
                      <FormControl>
                        <Input type="number" min={60} max={86400} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <Button type="submit" className="w-full font-mono uppercase tracking-widest">
                <ShieldAlert className="h-4 w-4" />
                Request access
              </Button>
            </form>
          </Form>
        </Panel>

        <div className="lg:col-span-2">
          <Panel bodyClassName="overflow-x-auto p-0">
            {error ? (
              <div className="p-6 font-mono text-xs text-destructive">{error}</div>
            ) : loading ? (
              <div className="flex items-center gap-2 p-6 font-mono text-xs text-muted-foreground">
                <Loader2 className="animate-spin" /> Loading requests…
              </div>
            ) : (data ?? []).length === 0 ? (
              <IamEmptyState
                title="No emergency requests"
                description="Emergency access requests will appear here when submitted."
              />
            ) : (
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Reason</th>
                    <th className="px-4 py-2">Grant</th>
                    <th className="px-4 py-2">Expiry</th>
                    <th className="px-4 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(data ?? []).map((r) => (
                    <tr key={r.id} className="border-b border-border/60 last:border-0 hover:bg-accent/40">
                      <td className="px-4 py-2.5">
                        <Badge variant="outline" className={cn("gap-1.5 font-mono text-[9px] uppercase", STYLE[r.status])}>
                          {r.status}
                        </Badge>
                      </td>
                      <td className="max-w-[220px] px-4 py-2.5">
                        <p className="truncate font-mono text-xs">{r.reason}</p>
                        <p className="font-mono text-[10px] text-muted-foreground">
                          {r.case_reference ?? "no case ref"}
                        </p>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[10px] uppercase text-muted-foreground">
                        {r.grant}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[10px] text-muted-foreground">
                        {r.expires_at
                          ? new Date(r.expires_at).toLocaleString()
                          : "—"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2.5 text-right">
                        {r.status === "REQUESTED" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busy === r.id}
                            onClick={() => void handleAction(r.id, "approve")}
                            className="font-mono text-[10px] uppercase tracking-widest"
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" /> Approve
                          </Button>
                        )}
                        {r.status === "APPROVED" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busy === r.id}
                            onClick={() => void handleAction(r.id, "activate")}
                            className="font-mono text-[10px] uppercase tracking-widest"
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" /> Activate
                          </Button>
                        )}
                        {(r.status === "APPROVED" || r.status === "ACTIVE" || r.status === "REQUESTED") && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busy === r.id}
                            onClick={() => void handleAction(r.id, "revoke")}
                            className="font-mono text-[10px] uppercase tracking-widest text-destructive"
                          >
                            <XCircle className="h-3.5 w-3.5" /> Revoke
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
