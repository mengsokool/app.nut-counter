import { LoaderCircle, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Detection, DetectionFrame } from "../../api/client";

type CameraState = "loading" | "ready" | "error";

const RETRY_DELAYS_MS = [500, 1000, 2000, 5000];

export default function CameraFeed({ trayPresent }: { trayPresent: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [state, setState] = useState<CameraState>("loading");
  const [errorMsg, setErrorMsg] = useState("กำลังเปิดกล้อง");
  const [sessionId, setSessionId] = useState(0);
  const detectionsRef = useRef<Detection[]>([]);

  // --- Clear detections on tray removed --------------------------------------
  useEffect(() => {
    if (!trayPresent) {
      detectionsRef.current = [];
    }
  }, [trayPresent]);

  // --- WebRTC video stream -------------------------------------------------
  useEffect(() => {
    function refreshStream() {
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      detectionsRef.current = [];
      retryCountRef.current = 0;
      setState("loading");
      setErrorMsg("กำลังเปิดกล้อง");
      setSessionId((current) => current + 1);
    }

    window.addEventListener("nut-counter-camera-refresh", refreshStream);
    return () => {
      window.removeEventListener("nut-counter-camera-refresh", refreshStream);
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
    };
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const videoEl = video;
    let isClosed = false;
    let pc: RTCPeerConnection | null = null;

    function scheduleReconnect(message: string) {
      if (isClosed || retryTimerRef.current) return;
      setState("error");
      setErrorMsg(`${message} กำลังเชื่อมต่อใหม่`);
      const delay =
        RETRY_DELAYS_MS[Math.min(retryCountRef.current, RETRY_DELAYS_MS.length - 1)];
      retryCountRef.current += 1;
      retryTimerRef.current = setTimeout(() => {
        retryTimerRef.current = null;
        setState("loading");
        setErrorMsg("กำลังเชื่อมต่อกล้องใหม่");
        setSessionId((current) => current + 1);
      }, delay);
    }

    async function connect() {
      try {
        pc = new RTCPeerConnection({ iceServers: [] });
        const transceiver = pc.addTransceiver("video", { direction: "recvonly" });
        preferHighQualityVideo(transceiver);

        pc.ontrack = (event) => {
          const stream = event.streams[0] ?? new MediaStream([event.track]);
          videoEl.srcObject = stream;
          void videoEl.play().catch(() => {});
        };

        pc.onconnectionstatechange = () => {
          if (!pc || isClosed) return;
          if (pc.connectionState === "connected") retryCountRef.current = 0;
          if (["failed", "closed", "disconnected"].includes(pc.connectionState)) {
            scheduleReconnect("WebRTC กล้องขาดหาย");
          }
        };

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        await waitForIceGathering(pc);
        if (!pc.localDescription) {
          throw new Error("สร้าง WebRTC offer ไม่สำเร็จ");
        }

        const response = await fetch("/api/camera/webrtc/offer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sdp: pc.localDescription.sdp,
            type: pc.localDescription.type,
          }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(
            "error" in payload && typeof payload.error === "string"
              ? payload.error
              : "WebRTC backend ไม่พร้อม",
          );
        }
        await pc.setRemoteDescription(payload as RTCSessionDescriptionInit);
      } catch (caught) {
        scheduleReconnect(caught instanceof Error ? caught.message : "เปิดกล้องไม่สำเร็จ");
      }
    }

    const handlePlaying = () => {
      retryCountRef.current = 0;
      setState("ready");
    };
    video.addEventListener("loadeddata", handlePlaying);
    video.addEventListener("playing", handlePlaying);
    void connect();

    let lastCurrentTime = -1;
    let stalledSince: number | null = null;
    const stallCheck = setInterval(() => {
      if (isClosed || video.readyState < 2 || video.paused) return;
      const ct = video.currentTime;
      if (ct !== lastCurrentTime) {
        lastCurrentTime = ct;
        stalledSince = null;
      } else if (stalledSince === null) {
        stalledSince = Date.now();
      } else if (Date.now() - stalledSince > 5000) {
        stalledSince = null;
        scheduleReconnect("กล้องค้าง");
      }
    }, 1000);

    return () => {
      isClosed = true;
      clearInterval(stallCheck);
      video.removeEventListener("loadeddata", handlePlaying);
      video.removeEventListener("playing", handlePlaying);
      const stream = video.srcObject;
      if (stream instanceof MediaStream) {
        stream.getTracks().forEach((track) => track.stop());
      }
      video.srcObject = null;
      pc?.close();
    };
  }, [sessionId]);

  // --- Detection SSE -------------------------------------------------------
  useEffect(() => {
    const source = new EventSource("/api/detections");
    source.onopen = () => {
      detectionsRef.current = [];
    };
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as DetectionFrame;
        detectionsRef.current = payload.detections ?? [];
      } catch {
        detectionsRef.current = [];
      }
    };
    source.onerror = () => {
      detectionsRef.current = [];
    };
    return () => {
      source.close();
      detectionsRef.current = [];
    };
  }, [sessionId]);

  // --- Overlay render loop -------------------------------------------------
  useEffect(() => {
    const canvas = overlayRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    const draw = () => {
      const w = video.clientWidth;
      const h = video.clientHeight;
      const dpr = window.devicePixelRatio || 1;

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);
      }
      ctx.clearRect(0, 0, w, h);

      const detections = detectionsRef.current;
      if (detections.length > 0 && w > 0 && h > 0) {
        ctx.lineWidth = Math.max(2, Math.round(w * 0.003));
        ctx.strokeStyle = "rgba(34, 211, 238, 0.95)";
        ctx.fillStyle = "rgba(34, 211, 238, 0.18)";
        ctx.font = `${Math.max(11, Math.round(w * 0.012))}px ui-sans-serif, system-ui`;
        ctx.textBaseline = "top";

        for (const d of detections) {
          const x = d.x * w;
          const y = d.y * h;
          const bw = d.w * w;
          const bh = d.h * h;
          ctx.fillRect(x, y, bw, bh);
          ctx.strokeRect(x, y, bw, bh);

          if (d.label) {
            const text = `${d.label} ${(d.confidence * 100).toFixed(0)}%`;
            const padding = 4;
            const metrics = ctx.measureText(text);
            const labelW = metrics.width + padding * 2;
            const labelH = parseInt(ctx.font, 10) + padding * 2;
            ctx.save();
            ctx.fillStyle = "rgba(8, 47, 73, 0.9)";
            ctx.fillRect(x, Math.max(0, y - labelH), labelW, labelH);
            ctx.fillStyle = "rgba(224, 242, 254, 1)";
            ctx.fillText(text, x + padding, Math.max(0, y - labelH) + padding);
            ctx.restore();
          }
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div className="relative h-full w-full bg-[var(--machine-dark)]">
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className="block h-full w-full object-cover"
      />
      <canvas
        ref={overlayRef}
        className="pointer-events-none absolute inset-0 h-full w-full"
      />

      {state !== "ready" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[var(--machine-dark)] text-[var(--machine-light)]">
          {state === "loading" ? (
            <LoaderCircle className="h-10 w-10 animate-spin text-[var(--machine-display-label)]" />
          ) : (
            <TriangleAlert className="h-10 w-10 text-[var(--machine-danger-strong)]" />
          )}
          <div className="text-center">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.32em] text-[var(--machine-display-label)]">
              camera
            </div>
            <div className="text-xl font-bold">{errorMsg}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function waitForIceGathering(pc: RTCPeerConnection) {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise<void>((resolve) => {
    const timeout = window.setTimeout(done, 1500);
    function done() {
      window.clearTimeout(timeout);
      pc.removeEventListener("icegatheringstatechange", onChange);
      resolve();
    }
    function onChange() {
      if (pc.iceGatheringState === "complete") done();
    }
    pc.addEventListener("icegatheringstatechange", onChange);
  });
}

function preferHighQualityVideo(transceiver: RTCRtpTransceiver) {
  const capabilities = RTCRtpSender.getCapabilities?.("video");
  const codecs = capabilities?.codecs;
  if (!codecs || typeof transceiver.setCodecPreferences !== "function") return;

  const h264 = codecs.filter((codec) => codec.mimeType.toLowerCase() === "video/h264");
  const rest = codecs.filter((codec) => codec.mimeType.toLowerCase() !== "video/h264");
  if (h264.length > 0) {
    transceiver.setCodecPreferences([...h264, ...rest]);
  }
}
