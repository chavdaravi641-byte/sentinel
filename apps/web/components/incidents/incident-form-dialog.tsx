"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { z } from "zod";
import type { Incident, IncidentStatus } from "@sentinel/shared";
import {
  ALERT_SEVERITY,
  INCIDENT_STATUS,
  INCIDENT_TYPE,
} from "@sentinel/shared";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCameras, useCreateIncident, useUpdateIncident } from "@/lib/queries";

const incidentCreateSchema = z.object({
  title: z.string().min(4, "Requires a descriptive title.").max(255),
  type: z.enum([
    INCIDENT_TYPE.THEFT,
    INCIDENT_TYPE.ASSAULT,
    INCIDENT_TYPE.TRAFFIC,
    INCIDENT_TYPE.FIRE,
    INCIDENT_TYPE.MISSING_PERSON,
    INCIDENT_TYPE.SUSPICIOUS_ACTIVITY,
    INCIDENT_TYPE.VANDALISM,
    INCIDENT_TYPE.OTHER,
  ]),
  severity: z.enum([
    ALERT_SEVERITY.CRITICAL,
    ALERT_SEVERITY.HIGH,
    ALERT_SEVERITY.MEDIUM,
    ALERT_SEVERITY.LOW,
    ALERT_SEVERITY.INFO,
  ]),
  status: z.enum([
    INCIDENT_STATUS.OPEN,
    INCIDENT_STATUS.IN_PROGRESS,
    INCIDENT_STATUS.CLOSED,
  ]),
  camera_id: z.string().nullable().optional(),
  location: z.string().max(255).optional().default(""),
  description: z.string().max(2000).optional().default(""),
});

type IncidentFormValues = z.infer<typeof incidentCreateSchema>;

interface IncidentFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  incident?: Incident | null;
}

export function IncidentFormDialog({
  open,
  onOpenChange,
  incident,
}: IncidentFormDialogProps) {
  const createIncident = useCreateIncident();
  const updateIncident = useUpdateIncident();
  const isEdit = Boolean(incident);

  const { data: cameraData } = useCameras({ pageSize: 200 });
  const cameras = cameraData?.items ?? [];

  const form = useForm<IncidentFormValues>({
    resolver: zodResolver(incidentCreateSchema),
    defaultValues: {
      title: "",
      type: INCIDENT_TYPE.SUSPICIOUS_ACTIVITY,
      severity: ALERT_SEVERITY.MEDIUM,
      status: INCIDENT_STATUS.OPEN,
      camera_id: null,
      location: "",
      description: "",
    },
  });

  useEffect(() => {
    if (open) {
      form.reset(
        incident
          ? {
              title: incident.title,
              type: incident.type,
              severity: incident.severity,
              status: incident.status as IncidentStatus,
              camera_id: incident.camera_id,
              location: incident.location ?? "",
              description: incident.description ?? "",
            }
          : {
              title: "",
              type: INCIDENT_TYPE.SUSPICIOUS_ACTIVITY,
              severity: ALERT_SEVERITY.MEDIUM,
              status: INCIDENT_STATUS.OPEN,
              camera_id: null,
              location: "",
              description: "",
            },
      );
    }
  }, [open, incident, form]);

  const pending = createIncident.isPending || updateIncident.isPending;

  async function onSubmit(values: IncidentFormValues) {
    const payload = {
      title: values.title.trim(),
      type: values.type,
      severity: values.severity,
      status: values.status,
      camera_id: values.camera_id || null,
      location: values.location.trim() || null,
      description: values.description.trim() || null,
    };
    try {
      if (isEdit && incident) {
        await updateIncident.mutateAsync({ id: incident.id, body: payload });
        toast.success("Incident updated.");
      } else {
        await createIncident.mutateAsync(payload);
        toast.success("Incident logged to the board.");
      }
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Operation failed.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-full max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-mono">
            <ShieldAlert className="h-4 w-4 text-primary" />
            {isEdit ? "UPDATE INCIDENT" : "LOG INCIDENT"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? `Amend incident #${incident?.id.slice(0, 8)}.`
              : "Open a new entry on the incident board."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            id="incident-form"
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-4"
            noValidate
          >
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                    Title
                  </FormLabel>
                  <FormControl>
                    <Input placeholder="Vehicle collision at anchor junction…" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Type
                    </FormLabel>
                    <FormControl>
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger className="font-mono text-xs uppercase">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {(Object.keys(INCIDENT_TYPE) as Array<keyof typeof INCIDENT_TYPE>).map(
                            (key) => (
                              <SelectItem
                                key={key}
                                value={INCIDENT_TYPE[key]}
                                className="font-mono uppercase"
                              >
                                {INCIDENT_TYPE[key]}
                              </SelectItem>
                            ),
                          )}
                        </SelectContent>
                      </Select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="severity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Severity
                    </FormLabel>
                    <FormControl>
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger className="font-mono text-xs uppercase">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {(
                            Object.keys(ALERT_SEVERITY) as Array<keyof typeof ALERT_SEVERITY>
                          ).map((key) => (
                            <SelectItem
                              key={key}
                              value={ALERT_SEVERITY[key]}
                              className="font-mono uppercase"
                            >
                              {ALERT_SEVERITY[key]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="status"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Status
                    </FormLabel>
                    <FormControl>
                      <Select
                        value={field.value}
                        onValueChange={(v) => field.onChange(v as IncidentStatus)}
                      >
                        <SelectTrigger className="font-mono text-xs uppercase">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {(
                            Object.keys(INCIDENT_STATUS) as Array<keyof typeof INCIDENT_STATUS>
                          ).map((key) => (
                            <SelectItem
                              key={key}
                              value={INCIDENT_STATUS[key]}
                              className="font-mono uppercase"
                            >
                              {INCIDENT_STATUS[key]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="camera_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Linked Camera
                    </FormLabel>
                    <FormControl>
                      <Select
                        value={field.value ?? "none"}
                        onValueChange={(v) =>
                          field.onChange(v === "none" ? null : v)
                        }
                      >
                        <SelectTrigger className="font-mono text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none" className="font-mono">
                            — unlinked —
                          </SelectItem>
                          {cameras.map((c) => (
                            <SelectItem
                              key={c.id}
                              value={c.id}
                              className="font-mono"
                            >
                              {c.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="location"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                    Location
                  </FormLabel>
                  <FormControl>
                    <Input placeholder="SG Highway, near Mahapuja circle…" {...field} />
                  </FormControl>
                  <FormDescription>Free-text grid reference.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                    Details
                  </FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Chronology, units dispatched, evidence…"
                      rows={4}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </form>
        </Form>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="incident-form"
            disabled={pending}
            className="font-mono uppercase tracking-widest"
          >
            {pending ? <Loader2 className="animate-spin" /> : null}
            {isEdit ? "Save Changes" : "Log Incident"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}