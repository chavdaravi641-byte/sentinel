"use client";

import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";
import { AudioLines, Loader2, Radio, VideoOff } from "lucide-react";

import { cn } from "@/lib/utils";

interface LiveStreamPlayerProps {
  name: string;
  running?: boolean;
  hlsUrl?: string | null;
  mjpegUrl?: string | null;
  whepUrl?: string | null;
  recording?: boolean;
  fps?: number | null;
  state?: string;
  whep?: boolean;
  className?: string;
}

const pad = (n: number) => String(n).padStart(2, "0");

/**
 * Phase 2 live feed player.
 *
 * Priority: WebRTC (WHEP, opt-in) → HLS (hls.js) → MJPEG (fallback) →
 * synthetic NO-SIGNAL placeholder. Media URLs are short-lived signed streams
 * proxied through the API, so no extra auth headers are needed.
 */
export function LiveStreamPlayer({
  name,
  running = false,
  hlsUrl,
  mjpegUrl,
  whepUrl,
  recording = false,
  fps,
  state,
  whep = false,
  className,
}: LiveStreamPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [hlsFailed, setHlsFailed] = useState(false);
  const [whepFailed, setWhepFailed] = useState(false);
  const [stamp, setStamp] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setStamp(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  /* HLS (or native Safari). */
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !running || !hlsUrl || whep) return;
    setHlsFailed(false);
    let hls: Hls | null = null;
    if (Hls.isSupported()) {
      hls = new Hls({
        liveDurationInfinity: true,
        backBufferLength: 30,
        maxLiveSyncPlaybackRate: 1.5,
      });
      hls.loadSource(hlsUrl);
      hls.attachMedia(video);
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (!data.fatal) return;
        if (data.type === Hls.ErrorTypes.NETWORK_ERROR && hls) {
          hls.startLoad();
        } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR && hls) {
          hls.recoverMediaError();
        } else {
          setHlsFailed(true);
        }
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = hlsUrl;
    } else {
      setHlsFailed(true);
    }
    return () => {
      hls?.destroy();
    };
  }, [running, hlsUrl, whep]);

  /* WebRTC WHEP relay (recvonly). */
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !running || !whep || !whepUrl || whepFailed) return;
    let pc: RTCPeerConnection | null = null;
    let cancelled = false;

    (async () => {
      try {
        pc = new RTCPeerConnection({ iceServers: [] });
        pc.addTransceiver("video", { direction: "recvonly" });
        video.srcObject = new MediaStream();
        pc.ontrack = (event) => {
          if (event.track.kind === "video" && video.srcObject instanceof MediaStream) {
            video.srcObject.addTrack(event.track);
          }
        };
        pc.onconnectionstatechange = () => {
          if (!cancelled && pc?.connectionState === "failed") setWhepFailed(true);
        };
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        const res = await fetch(whepUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/sdp",
            Accept: "application/sdp",
          },
          body: offer.sdp,
        });
        if (!res.ok) throw new Error(`WHEP ${res.status}`);
        const answer = await res.text();
        if (cancelled) return;
        await pc.setRemoteDescription({ type: "answer", sdp: answer });
      } catch {
        if (!cancelled) setWhepFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      pc?.close();
      if (video.srcObject instanceof MediaStream) {
        video.srcObject.getTracks().forEach((track) => track.stop());
        video.srcObject = null;
      }
    };
  }, [running, whep, whepUrl, whepFailed]);

  const whepMode = running && whep && Boolean(whepUrl) && !whepFailed;
  const hlsMode = running && !whepMode && Boolean(hlsUrl) && !hlsFailed;
  const mjpegMode =
    running && !whepMode && Boolean(mjpegUrl) && (!hlsUrl || hlsFailed);
  const offline = !running;
  const establishing = running && !whepMode && !hlsMode && !mjpegMode;

  const modeLabel = whepMode
    ? "WHEP"
    : hlsMode
      ? "HLS"
      : mjpegMode
        ? "MJPEG"
        : offline
          ? "OFFLINE"
          : establishing
            ? "LINKING"
            : "LINKING";

  const clock = `${pad(stamp.getHours())}:${pad(stamp.getMinutes())}:${pad(stamp.getSeconds())}`;

  return (
    <div
      className={cn(
        "relative overflow-hidden bg-[#04070d] bg-command-grid",
        className,
      )}
    >
      {(hlsMode || whepMode) && (
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="absolute inset-0 h-full w-full object-cover"
        />
      )}
      {mjpegMode && (
        // eslint-disable-next-line @next/next/no-img-element -- live multipart stream, must not go through next/image
        <img
          key={mjpegUrl ?? undefined}
          src={mjpegUrl ?? undefined}
          alt={name}
          className="absolute inset-0 h-full w-full object-cover"
        />
      )}

      {(offline || establishing) && (
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-gradient-to-b from-[#081120] via-[#0a1424] to-[#05090f]" />
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
            {establishing ? (
              <Loader2 className="h-5 w-5 animate-spin text-primary/70" />
            ) : (
              <VideoOff className="h-5 w-5 text-slate-600" />
            )}
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-slate-500">
              {establishing ? "Establishing feed" : "No signal"}
            </span>
          </div>
        </div>
      )}

      {!offline && <div className="scanline" />}

      {/* corner brackets */}
      <div className="pointer-events-none absolute inset-2">
        <span className="absolute left-0 top-0 h-4 w-4 border-l border-t border-primary/50" />
        <span className="absolute right-0 top-0 h-4 w-4 border-r border-t border-primary/50" />
        <span className="absolute bottom-0 left-0 h-4 w-4 border-b border-l border-primary/50" />
        <span className="absolute bottom-0 right-0 h-4 w-4 border-b border-r border-primary/50" />
      </div>

      {/* HUD top */}
      <div className="absolute left-2.5 top-2 flex items-center gap-2">
        {running && recording && (
          <span className="flex items-center gap-1.5 font-mono text-[9px] font-bold uppercase tracking-widest text-rose-400">
            <span className="live-dot" />
            REC
          </span>
        )}
        <span
          className={cn(
            "font-mono text-[9px] uppercase tracking-widest",
            running ? "text-cyan-300/90" : "text-slate-500",
          )}
        >
          {running ? "LIVE" : "OFFLINE"}
        </span>
      </div>

      <div className="absolute right-2.5 top-2 flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-slate-300/80">
        <Radio className="h-3 w-3" />
        {modeLabel}
      </div>

      {/* HUD bottom */}
      <div className="absolute bottom-2 left-2.5 flex items-center gap-3">
        <span className="truncate font-mono text-[9px] tracking-widest text-muted-foreground">
          CAM · {name}
        </span>
      </div>
      <div className="absolute bottom-2 right-2.5 flex items-center gap-2">
        {running && fps != null && (
          <span className="font-mono text-[9px] tabular-nums tracking-widest text-emerald-300/90">
            {fps.toFixed(0)} FPS
          </span>
        )}
        {state && (
          <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/80">
            {state}
          </span>
        )}
        <AudioLines className="h-3 w-3 text-muted-foreground/60" />
        <span className="font-mono text-[9px] tabular-nums tracking-widest text-muted-foreground">
          {clock} UTC
        </span>
      </div>

      {/* vignette */}
      <div className="pointer-events-none absolute inset-0 shadow-[inset_0_0_60px_rgba(0,0,0,0.55)]" />
    </div>
  );
}