"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Database, KeyRound, Loader2, RefreshCw, Shield, User as UserIcon } from "lucide-react";
import { toast } from "sonner";
import { z } from "zod";
import { USER_ROLE } from "@sentinel/shared";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useAuth } from "@/lib/auth";
import { useHealth } from "@/lib/queries";
import { api, endpoints } from "@/lib/api";
import { initials } from "@/lib/utils";

const passwordSchema = z
  .object({
    current_password: z.string().min(6, "Current password required."),
    new_password: z
      .string()
      .min(8, "Requires at least 8 characters.")
      .max(256),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, {
    message: "Passwords do not match.",
    path: ["confirm"],
  });

type PasswordValues = z.infer<typeof passwordSchema>;

type HealthStatus = "ok" | "degraded" | "unknown";

function HealthPill({
  label,
  status,
}: {
  label: string;
  status: HealthStatus;
}) {
  const isHealthy = status === "ok";
  return (
    <div className="flex items-center gap-2.5 rounded-md border border-border/60 bg-card/60 px-3 py-2">
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          isHealthy ? "bg-success radar-pulse" : status === "degraded" ? "bg-amber-400" : "bg-muted-foreground"
        }`}
      />
      <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
        {label}
      </span>
      <span
        className={`ml-auto font-mono text-[10px] uppercase tracking-widest ${
          isHealthy ? "text-success" : status === "degraded" ? "text-amber-300" : "text-muted-foreground"
        }`}
      >
        {status}
      </span>
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const { data: health, refetch, isFetching, isError: healthError } = useHealth();
  const [pending, setPending] = useState(false);

  const components = health?.components;
  const healthStatus: HealthStatus = healthError
    ? "unknown"
    : health?.status ?? "unknown";

  const form = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });

  async function onSubmit(values: PasswordValues) {
    setPending(true);
    try {
      await api.post<{ message: string }>(endpoints.changePassword, {
        current_password: values.current_password,
        new_password: values.new_password,
      });
      toast.success("Credentials rotated. Refresh tokens revoked.");
      form.reset();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Password change failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        description="Operator identity, credential rotation and stack health"
      />

      <div className="grid gap-4 xl:grid-cols-2">
        {/* Operator profile */}
        <Panel
          title="Operator Profile"
          subtitle="active session"
          bodyClassName="p-4"
        >
          <div className="flex items-center gap-4">
            <Avatar className="h-14 w-14 border border-primary/40">
              <AvatarFallback className="bg-primary/10 font-mono text-primary">
                {initials(user?.full_name)}
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="flex items-center gap-2 font-mono text-base font-semibold">
                {user?.full_name ?? "Operator"}
                <Badge
                  variant="outline"
                  className="hidden font-mono text-[9px] uppercase xl:inline-flex"
                >
                  {user?.role ?? USER_ROLE.OPERATOR}
                </Badge>
              </p>
              <p className="font-mono text-xs text-muted-foreground">{user?.email}</p>
            </div>
          </div>

          <Separator className="my-4" />

          <dl className="space-y-2 font-mono text-xs">
            <div className="flex justify-between">
              <dt className="uppercase tracking-widest text-muted-foreground">
                Session
              </dt>
              <dd className="text-success">VALID</dd>
            </div>
            <div className="flex justify-between">
              <dt className="uppercase tracking-widest text-muted-foreground">
                Access token
              </dt>
              <dd className="text-muted-foreground">rotating · 15 min TTL</dd>
            </div>
            <div className="flex justify-between">
              <dt className="uppercase tracking-widest text-muted-foreground">
                Refresh token
              </dt>
              <dd className="text-muted-foreground">httpOnly · rotated on use</dd>
            </div>
          </dl>
        </Panel>

        {/* Change password */}
        <Panel
          title="Credential Rotation"
          subtitle="rotate access keys"
          right={<KeyRound className="h-4 w-4 text-primary" />}
        >
          <Form {...form}>
            <form
              id="password-form"
              onSubmit={form.handleSubmit(onSubmit)}
              className="space-y-4"
              noValidate
            >
              <FormField
                control={form.control}
                name="current_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Current password
                    </FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="current-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-2 gap-3">
                <FormField
                  control={form.control}
                  name="new_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                        New password
                      </FormLabel>
                      <FormControl>
                        <Input
                          type="password"
                          autoComplete="new-password"
                          placeholder="min 8 chars"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="confirm"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                        Confirm
                      </FormLabel>
                      <FormControl>
                        <Input type="password" autoComplete="new-password" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <Button
                type="submit"
                form="password-form"
                disabled={pending}
                className="font-mono uppercase tracking-widest"
              >
                {pending ? <Loader2 className="animate-spin" /> : <KeyRound className="h-4 w-4" />}
                Rotate credentials
              </Button>
            </form>
          </Form>
        </Panel>

        {/* System health */}
        <Panel
          title="Stack Health"
          subtitle="live probes"
          right={
            <Button
              variant="ghost"
              size="icon"
              aria-label="Refresh stack health"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={isFetching ? "animate-spin" : ""} />
            </Button>
          }
          bodyClassName="space-y-2 p-4"
        >
          <HealthPill label="API gateway" status={healthStatus} />
          <HealthPill label="PostgreSQL" status={components?.database?.status ?? "unknown"} />
          <HealthPill label="Redis" status={components?.redis?.status ?? "unknown"} />
          <p className="flex items-center gap-2 pt-1 font-mono text-[11px] text-muted-foreground">
            <Shield className="h-3.5 w-3.5 text-primary" />
            Sentinel AI core v{health?.version ?? "?"}
          </p>
        </Panel>

        {/* Grid preferences */}
        <Panel
          title="Preferences"
          subtitle="command center defaults"
          bodyClassName="p-4"
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-mono text-sm">Auto-refresh sensor grid</p>
                <p className="font-mono text-[11px] text-muted-foreground">
                  Poll dashboard every 30s
                </p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-mono text-sm">Sound alerts</p>
                <p className="font-mono text-[11px] text-muted-foreground">
                  Audible cue on CRITICAL detections
                </p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-mono text-sm">Perceptual flagging</p>
                <p className="font-mono text-[11px] text-muted-foreground">
                  Computer-vision analytics (phase 2)
                </p>
              </div>
              <Switch disabled />
            </div>
          </div>

          <Separator className="my-4" />

          <div className="flex items-center justify-between font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Database className="h-3.5 w-3.5" />
              system scopes granted
            </span>
            <span className="flex items-center gap-1.5">
              <UserIcon className="h-3.5 w-3.5" />
              {user?.role ?? USER_ROLE.OPERATOR}
            </span>
          </div>
        </Panel>
      </div>
    </>
  );
}