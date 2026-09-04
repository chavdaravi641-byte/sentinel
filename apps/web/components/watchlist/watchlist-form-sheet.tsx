"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { z } from "zod";
import type { Watchlist } from "@sentinel/shared";
import {
  WATCHLIST_CATEGORY,
  WATCHLIST_SOURCE_DB,
  WATCHLIST_TARGET_TYPE,
} from "@sentinel/shared";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useCreateWatchlist, useUpdateWatchlist } from "@/lib/queries";

const watchlistSchema = z.object({
  target_type: z.enum([WATCHLIST_TARGET_TYPE.VEHICLE, WATCHLIST_TARGET_TYPE.PERSON]),
  identifier_number: z
    .string()
    .min(6, "Requires at least 6 characters.")
    .max(64, "Too long."),
  category: z.enum([
    WATCHLIST_CATEGORY.STOLEN_VEHICLE,
    WATCHLIST_CATEGORY.WANTED,
    WATCHLIST_CATEGORY.MISSING,
    WATCHLIST_CATEGORY.UNINSURED,
    WATCHLIST_CATEGORY.BLACKLISTED,
    WATCHLIST_CATEGORY.SUSPECT,
    WATCHLIST_CATEGORY.OTHER,
  ]),
  source_db: z.enum([
    WATCHLIST_SOURCE_DB.VAHAN,
    WATCHLIST_SOURCE_DB.EGUJCOP,
    WATCHLIST_SOURCE_DB.SARTHI,
    WATCHLIST_SOURCE_DB.INTERNAL,
    WATCHLIST_SOURCE_DB.MANUAL,
  ]),
  notes: z.string().max(2000).optional().default(""),
});

type WatchlistFormValues = z.infer<typeof watchlistSchema>;

interface WatchlistFormSheetProps {
  open: boolean;
  entry?: Watchlist | null;
  onOpenChange: (open: boolean) => void;
}

const CATEGORY_ITEMS: { value: string; label: string }[] = [
  { value: WATCHLIST_CATEGORY.STOLEN_VEHICLE, label: "Stolen Vehicle" },
  { value: WATCHLIST_CATEGORY.WANTED, label: "Wanted" },
  { value: WATCHLIST_CATEGORY.MISSING, label: "Missing" },
  { value: WATCHLIST_CATEGORY.UNINSURED, label: "Uninsured" },
  { value: WATCHLIST_CATEGORY.BLACKLISTED, label: "Blacklisted" },
  { value: WATCHLIST_CATEGORY.SUSPECT, label: "Suspect" },
  { value: WATCHLIST_CATEGORY.OTHER, label: "Other" },
];

const SOURCE_ITEMS: { value: string; label: string }[] = [
  { value: WATCHLIST_SOURCE_DB.VAHAN, label: "VAHAN" },
  { value: WATCHLIST_SOURCE_DB.EGUJCOP, label: "eGujCop" },
  { value: WATCHLIST_SOURCE_DB.SARTHI, label: "SARTHI" },
  { value: WATCHLIST_SOURCE_DB.INTERNAL, label: "Internal" },
  { value: WATCHLIST_SOURCE_DB.MANUAL, label: "Manual" },
];

export function WatchlistFormSheet({
  open,
  entry,
  onOpenChange,
}: WatchlistFormSheetProps) {
  const create = useCreateWatchlist();
  const update = useUpdateWatchlist();

  const form = useForm<WatchlistFormValues>({
    resolver: zodResolver(watchlistSchema),
    defaultValues: {
      target_type: WATCHLIST_TARGET_TYPE.VEHICLE,
      identifier_number: "",
      category: WATCHLIST_CATEGORY.STOLEN_VEHICLE,
      source_db: WATCHLIST_SOURCE_DB.VAHAN,
      notes: "",
    },
  });

  useEffect(() => {
    if (open) {
      form.reset(
        entry
          ? {
              target_type: entry.target_type,
              identifier_number: entry.identifier_number,
              category: entry.category,
              source_db: entry.source_db,
              notes: entry.notes ?? "",
            }
          : {
              target_type: WATCHLIST_TARGET_TYPE.VEHICLE,
              identifier_number: "",
              category: WATCHLIST_CATEGORY.STOLEN_VEHICLE,
              source_db: WATCHLIST_SOURCE_DB.VAHAN,
              notes: "",
            },
      );
    }
  }, [open, entry, form]);

  async function handleSubmit(values: WatchlistFormValues) {
    const plate = values.identifier_number.trim().toUpperCase().replace(/\s+/g, "");
    if (!plate) {
      toast.error("Identifier number is required.");
      return;
    }
    try {
      if (entry) {
        await update.mutateAsync({ id: entry.id, ...values, identifier_number: plate });
        toast.success(`Updated ${plate}.`);
      } else {
        await create.mutateAsync({ ...values, identifier_number: plate });
        toast.success(`Added ${plate} to watchlist.`);
      }
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed.");
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full border-l border-border bg-card sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="font-mono uppercase tracking-widest">
            {entry ? "Edit Watchlist Entry" : "Add Watchlist Entry"}
          </SheetTitle>
          <SheetDescription>
            Flag a vehicle or person for real-time ANPR cross-referencing.
          </SheetDescription>
        </SheetHeader>

        <form onSubmit={form.handleSubmit(handleSubmit)} className="mt-5 space-y-4">
          <div>
            <Label className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Target Type
            </Label>
            <Select
              value={form.watch("target_type")}
              onValueChange={(v) => form.setValue("target_type", v as WatchlistFormValues["target_type"])}
            >
              <SelectTrigger className="mt-1.5 font-mono uppercase">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={WATCHLIST_TARGET_TYPE.VEHICLE}>Vehicle</SelectItem>
                <SelectItem value={WATCHLIST_TARGET_TYPE.PERSON}>Person</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Identifier Number / Plate
            </Label>
            <Input
              {...form.register("identifier_number")}
              placeholder="GJ01AB1234"
              className="mt-1.5 font-mono uppercase"
            />
            {form.formState.errors.identifier_number && (
              <p className="mt-1 font-mono text-[10px] text-destructive">
                {form.formState.errors.identifier_number.message}
              </p>
            )}
          </div>

          <div>
            <Label className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Category
            </Label>
            <Select
              value={form.watch("category")}
              onValueChange={(v) => form.setValue("category", v as WatchlistFormValues["category"])}
            >
              <SelectTrigger className="mt-1.5 font-mono uppercase">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORY_ITEMS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Source Database
            </Label>
            <Select
              value={form.watch("source_db")}
              onValueChange={(v) => form.setValue("source_db", v as WatchlistFormValues["source_db"])}
            >
              <SelectTrigger className="mt-1.5 font-mono uppercase">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SOURCE_ITEMS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Notes
            </Label>
            <Textarea
              {...form.register("notes")}
              placeholder="Context for command center operators..."
              className="mt-1.5 min-h-24 font-mono text-xs"
            />
          </div>

          <SheetFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="font-mono uppercase tracking-widest"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={create.isPending || update.isPending}
              className="font-mono uppercase tracking-widest"
            >
              {entry ? "Save Changes" : "Add Entry"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}