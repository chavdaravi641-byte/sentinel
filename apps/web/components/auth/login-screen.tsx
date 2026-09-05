"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Loader2,
  Lock,
  ShieldAlert,
  Mail,
  Radar,
  Eye,
  EyeOff,
} from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

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
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { CLIENT_VERSION } from "@sentinel/shared";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(6, "Password must be at least 6 characters."),
});

type LoginValues = z.infer<typeof loginSchema>;

const DEMO_CREDENTIALS = {
  email: "admin@sentinel.gp",
  password: "Admin@2026",
};

const SHOW_DEMO_CREDENTIALS = process.env.NEXT_PUBLIC_ENVIRONMENT !== "production";

export function LoginScreen() {
  const router = useRouter();
  const { status, login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  const { isSubmitting } = form.formState;

  // Already authenticated → head to the command center.
  useEffect(() => {
    if (status === "authenticated") router.replace("/app");
  }, [status, router]);

  async function onSubmit(values: LoginValues) {
    setError(null);
    try {
      await login(values);
      router.replace("/app");
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Unable to reach the authentication service.");
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-command-grid">
      {/* ambient glows */}
      <div className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[42rem] -translate-x-1/2 rounded-full bg-primary/10 blur-[120px] animate-flicker" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-80 w-80 translate-x-1/3 translate-y-1/3 rounded-full bg-cyan-900/10 blur-[100px]" />

      <div className="relative z-10 w-full max-w-sm px-6">
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 shadow-[0_0_28px_-6px] shadow-primary/40">
            <Radar className="h-7 w-7 text-primary" />
          </div>
          <div className="text-center">
            <h1 className="font-mono text-xl font-bold tracking-[0.3em] text-glow-cyan">
              SENTINEL
            </h1>
            <p className="mt-1 text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
              Gujarat Police · CCTV Intelligence
            </p>
          </div>
        </div>

        <div className="rounded-lg border bg-card/80 p-6 shadow-2xl backdrop-blur">
          <div className="mb-5 flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-primary" />
            <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
              Restricted access · authenticate
            </span>
          </div>

          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="space-y-4"
              noValidate
            >
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Operator Email
                    </FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
                        <Input
                          placeholder="operator@sentinel.gp"
                          autoComplete="email"
                          className="pl-9 font-mono text-sm"
                          {...field}
                        />
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Passphrase
                    </FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
                        <Input
                          type={showPassword ? "text" : "password"}
                          placeholder="••••••••••••"
                          autoComplete="current-password"
                          className="pl-9 pr-9 font-mono text-sm"
                          {...field}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword((v) => !v)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 transition-colors hover:text-foreground"
                          aria-label="Toggle password visibility"
                        >
                          {showPassword ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {error && (
                <div className="rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  {error}
                </div>
              )}

              <Button
                type="submit"
                className="w-full font-mono text-sm uppercase tracking-widest"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="animate-spin" /> Authenticating
                  </>
                ) : (
                  "Sign In"
                )}
              </Button>
            </form>
          </Form>

          <Separator className="my-4" />

          {SHOW_DEMO_CREDENTIALS && (
            <div className="rounded border border-border/80 bg-muted/40 px-3 py-2.5">
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                Demo operator credentials
              </p>
              <p className="mt-1 font-mono text-[11px] text-cyan-300">
                {DEMO_CREDENTIALS.email} · {DEMO_CREDENTIALS.password}
              </p>
            </div>
          )}
        </div>

        <p className="mt-6 flex items-center justify-center gap-1.5 text-center font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70">
          <Radar className="h-3 w-3" />
          Sentinel AI v{CLIENT_VERSION} · Restricted law-enforcement system
        </p>
      </div>
    </main>
  );
}