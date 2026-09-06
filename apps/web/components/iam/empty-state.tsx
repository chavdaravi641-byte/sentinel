import { Inbox } from "lucide-react";

export function IamEmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <Inbox className="h-8 w-8 text-muted-foreground/45" aria-hidden="true" />
      <p className="font-mono text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        {title}
      </p>
      <p className="max-w-md text-xs text-muted-foreground/70">{description}</p>
    </div>
  );
}
