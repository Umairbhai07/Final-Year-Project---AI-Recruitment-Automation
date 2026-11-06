import fixWebmDuration from "fix-webm-duration";
import { useCallback, useEffect, useRef, useState } from "react";

/** Pick a format this browser can record (Chrome/Firefox: webm/ogg, Safari: mp4). */
function pickMimeType(): { mimeType: string; ext: string } {
  const options = [
    { mimeType: "audio/webm;codecs=opus", ext: "webm" },
    { mimeType: "audio/webm", ext: "webm" },
    { mimeType: "audio/mp4", ext: "mp4" },
    { mimeType: "audio/ogg;codecs=opus", ext: "ogg" },
  ];
  for (const o of options) if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(o.mimeType)) return o;
  return { mimeType: "", ext: "webm" };
}

export type MicStatus = "idle" | "requesting" | "ready" | "denied" | "unsupported" | "error";

/** Asks for microphone permission and keeps the stream (shared by the volume meter and the recorder). */
export function useMicrophone() {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [status, setStatus] = useState<MicStatus>("idle");

  const request = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setStatus("unsupported");
      return null;
    }
    setStatus("requesting");
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
      setStream(s);
      setStatus("ready");
      return s;
    } catch (err) {
      const name = (err as DOMException)?.name;
      setStatus(name === "NotAllowedError" || name === "SecurityError" ? "denied" : "error");
      return null;
    }
  }, []);

  useEffect(() => () => stream?.getTracks().forEach((t) => t.stop()), [stream]);
  return { stream, status, request };
}

/** Live microphone volume (0-1) using the Web Audio API. */
export function useVolume(stream: MediaStream | null) {
  const [level, setLevel] = useState(0);
  useEffect(() => {
    if (!stream) return;
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    const data = new Uint8Array(analyser.fftSize);
    let raf = 0;
    const tick = () => {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (const v of data) sum += ((v - 128) / 128) ** 2;
      setLevel(Math.min(1, Math.sqrt(sum / data.length) * 4));
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => {
      cancelAnimationFrame(raf);
      source.disconnect();
      ctx.close();
    };
  }, [stream]);
  return level;
}

/** Records audio with MediaRecorder. stop() resolves with the recorded Blob. */
export function useRecorder(stream: MediaStream | null) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const resolveStop = useRef<((b: Blob) => void) | null>(null);
  const [recording, setRecording] = useState(false);
  const format = useRef(pickMimeType());
  const startedAt = useRef(0);

  const start = useCallback(() => {
    if (!stream) return false;
    chunks.current = [];
    const rec = new MediaRecorder(stream, format.current.mimeType ? { mimeType: format.current.mimeType } : undefined);
    rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
    rec.onstop = async () => {
      const type = rec.mimeType || format.current.mimeType || "audio/webm";
      let blob = new Blob(chunks.current, { type });
      // Chrome writes WebM files without a duration, which breaks seeking and playback in some players.
      if (type.includes("webm")) {
        try { blob = await fixWebmDuration(blob, Date.now() - startedAt.current, { logger: false }); } catch { /* keep original */ }
      }
      resolveStop.current?.(blob);
      resolveStop.current = null;
    };
    startedAt.current = Date.now();
    rec.start(250);
    recorderRef.current = rec;
    setRecording(true);
    return true;
  }, [stream]);

  const stop = useCallback(
    () =>
      new Promise<Blob>((resolve) => {
        const rec = recorderRef.current;
        if (!rec || rec.state === "inactive") {
          resolve(new Blob(chunks.current, { type: format.current.mimeType || "audio/webm" }));
          return;
        }
        resolveStop.current = resolve;
        rec.stop();
        setRecording(false);
      }),
    [],
  );

  useEffect(() => () => { if (recorderRef.current?.state === "recording") recorderRef.current.stop(); }, []);
  return { start, stop, recording, ext: format.current.ext };
}
