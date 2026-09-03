"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Video } from "lucide-react";
import { toast } from "sonner";
import { z } from "zod";
import type { Camera, CameraStatus } from "@sentinel/shared";
import { CAMERA_STATUS } from "@sentinel/shared";

import { Button } from "@/components/ui/button";
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useCreateCamera, useUpdateCamera } from "@/lib/queries";

const cameraSchema = z.object({
  name: z
    .string()
    .min(2, "Requires at least 2 characters.")
    .max(160, "Too long."),
  rtsp_url: z
    .string()
    .min(7)
    .regex(
      /^(rtsp|rtsps|rtmp|http|https|hls):\/\/.+$/i,
      "Must be a stream URL e.g. rtsp://user:pass@host:554/stream",
    ),
  location: z.string().min(2, "Requires a location identifier.").max(255),
  latitude: z.coerce
    .number()
    .min(-90, "Latitude out of range.")
    .max(90, "Latitude out of range."),
  longitude: z.coerce
    .number()
    .min(-180, "Longitude out of range.")
    .max(180, "Longitude out of range."),
  status: z.enum([
    CAMERA_STATUS.ONLINE,
    CAMERA_STATUS.OFFLINE,
    CAMERA_STATUS.MAINTENANCE,
    CAMERA_STATUS.UNKNOWN,
  ]),
  description: z.string().max(2000).optional().default(""),
});

type CameraFormValues = z.infer<typeof cameraSchema>;

interface CameraFormSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  camera?: Camera | null;
}

export function CameraFormSheet({
  open,
  onOpenChange,
  camera,
}: CameraFormSheetProps) {
  const createCamera = useCreateCamera();
  const updateCamera = useUpdateCamera();
  const isEdit = Boolean(camera);

  const form = useForm<CameraFormValues>({
    resolver: zodResolver(cameraSchema),
    defaultValues: {
      name: "",
      rtsp_url: "",
      location: "",
      latitude: 23.02,
      longitude: 72.57,
      status: CAMERA_STATUS.UNKNOWN,
      description: "",
    },
  });

  useEffect(() => {
    if (open) {
      form.reset(
        camera
          ? {
              name: camera.name,
              rtsp_url: camera.rtsp_url,
              location: camera.location,
              latitude: camera.latitude,
              longitude: camera.longitude,
              status: camera.status as CameraStatus,
              description: camera.description ?? "",
            }
          : {
              name: "",
              rtsp_url: "",
              location: "",
              latitude: 23.02,
              longitude: 72.57,
              status: CAMERA_STATUS.UNKNOWN,
              description: "",
            },
      );
    }
  }, [open, camera, form]);

  const pending = createCamera.isPending || updateCamera.isPending;

  async function onSubmit(values: CameraFormValues) {
    const payload = {
      name: values.name.trim(),
      rtsp_url: values.rtsp_url.trim(),
      location: values.location.trim(),
      latitude: values.latitude,
      longitude: values.longitude,
      status: values.status,
      description: values.description.trim() || null,
    };
    try {
      if (isEdit && camera) {
        await updateCamera.mutateAsync({ id: camera.id, body: payload });
        toast.success(`Camera ${camera.name} updated.`);
      } else {
        await createCamera.mutateAsync(payload);
        toast.success(`Camera ${values.name} registered.`);
      }
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Operation failed.");
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2 font-mono">
            <Video className="h-4 w-4 text-primary" />
            {isEdit ? "MODIFY CAMERA" : "REGISTER CAMERA"}
          </SheetTitle>
          <SheetDescription>
            {isEdit
              ? `Updating sensor ${camera?.name}.`
              : "Provision a new CCTV sensor into the grid."}
          </SheetDescription>
        </SheetHeader>

        <Form {...form}>
          <form
            id="camera-form"
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-4"
            noValidate
          >
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                    Designation
                  </FormLabel>
                  <FormControl>
                    <Input
                      placeholder="AHM-SGH-01"
                      className="font-mono"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="rtsp_url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                    Stream URL (RTSP)
                  </FormLabel>
                  <FormControl>
                    <Input
                      placeholder="rtsp://user:pass@10.10.1.11:554/streaming/channels/1"
                      className="font-mono text-xs"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    rtsp / rtsps / rtmp / hls schemes supported.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="latitude"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Latitude
                    </FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="any"
                        placeholder="23.0225"
                        className="font-mono"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="longitude"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Longitude
                    </FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="any"
                        placeholder="72.5714"
                        className="font-mono"
                        {...field}
                      />
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
                    <Input
                      placeholder="SG Highway, Ahmedabad"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                    Operational Status
                  </FormLabel>
                  <FormControl>
                    <Select
                      value={field.value}
                      onValueChange={(v) => field.onChange(v as CameraStatus)}
                    >
                      <SelectTrigger className="font-mono">
                        <SelectValue placeholder="Select status" />
                      </SelectTrigger>
                      <SelectContent>
                        {(Object.keys(CAMERA_STATUS) as Array<keyof typeof CAMERA_STATUS>).map(
                          (key) => (
                            <SelectItem
                              key={key}
                              value={CAMERA_STATUS[key]}
                              className="font-mono uppercase"
                            >
                              {CAMERA_STATUS[key]}
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
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                    Notes
                  </FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Optional operator notes…"
                      rows={3}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </form>
        </Form>

        <SheetFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            form="camera-form"
            disabled={pending}
            className="font-mono uppercase tracking-widest"
          >
            {pending ? <Loader2 className="animate-spin" /> : null}
            {isEdit ? "Save Changes" : "Register"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}