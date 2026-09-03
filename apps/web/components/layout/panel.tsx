"use client";

import type { ReactNode } from "react";

interface PanelProps {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

/**
 * Bordered command-center panel with a mono header strip.
 */
export function Panel({
  title,
  subtitle,
  right,
  className,
  bodyClassName,
  children,
}: PanelProps) {
  return (
    <section
      className={`overflow-hidden rounded-lg border bg-card/70 backdrop-blur ${className ?? ""}`}
    >
      {(title || right) && (
        <header className="flex h-10 items-center justify-between gap-3 border-b border-border bg-muted/30 px-4">
          <div className="flex items-baseline gap-2">
            {title && (
              <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.2em] text-foreground">
                {title}
              </h2>
            )}
            {subtitle && (
              <span className="hidden font-mono text-[10px] uppercase tracking-widest text-muted-foreground sm:inline">
                {subtitle}
              </span>
            )}
          </div>
          {right}
        </header>
      )}
      <div className={bodyClassName ?? "p-4"}>{children}</div>
    </section>
  );
}