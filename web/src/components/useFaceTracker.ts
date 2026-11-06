import type { FaceLandmarker, FaceLandmarkerResult } from "@mediapipe/tasks-vision";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Webcam face tracking that runs entirely in the browser (Google MediaPipe Face Landmarker, 478 face points + eye
 * blendshapes). No video is uploaded: only the conclusions (and a few small snapshots, elsewhere) leave the device.
 *
 * Per frame we work out:
 * - how many faces are visible,
 * - head direction from face points: nose position between the cheeks (left/right) and between forehead and chin
 *   (up/down),
 * - eye direction from the eyeLookIn/Out/Up/Down blendshapes.
 * Everything is compared with the candidate's own "looking at the screen" baseline taken during calibration, so
 * different faces, glasses and camera positions don't cause false alarms.
 */

export type FaceState = "loading" | "ok" | "no_face" | "multiple_faces" | "looking_away" | "eyes_away" | "error";

export interface FaceSample {
  faces: number;
  yaw: number; // -1 (turned to one side) .. 1 (other side)
  pitch: number; // 0 (top) .. 1 (chin)
  gazeX: number; // eyes left/right
  gazeY: number; // eyes down (+) / up (-)
  eyesClosed: boolean;
}

export interface Baseline {
  yaw: number;
  pitch: number;
  gazeX: number;
  gazeY: number;
}

// How far from the baseline counts as "away" (tuned so normal small movements and blinking are fine).
export const LIMITS = { yaw: 0.36, pitchUp: 0.13, pitchDown: 0.15, gazeX: 0.42, gazeDown: 0.42, gazeUp: 0.45 };

const MODEL_URL = "/mediapipe/face_landmarker.task";
const WASM_URL = "/mediapipe/wasm";
const INTERVAL_MS = 150;
const CALIBRATION_INTERVAL_MS = 100;
const CALIBRATION_SAMPLES = 6; // under a second of looking at the screen

let landmarkerPromise: Promise<FaceLandmarker> | null = null;

/** Loads the model once per page (about 4 MB, served by our own frontend, so it also works offline). */
export function loadFaceLandmarker(): Promise<FaceLandmarker> {
  if (!landmarkerPromise) {
    landmarkerPromise = (async () => {
      const { FaceLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision");
      const fileset = await FilesetResolver.forVisionTasks(WASM_URL);
      const options = (delegate: "GPU" | "CPU") => ({
        baseOptions: { modelAssetPath: MODEL_URL, delegate },
        runningMode: "VIDEO" as const,
        numFaces: 2,
        minFaceDetectionConfidence: 0.5,
        minFacePresenceConfidence: 0.5,
        minTrackingConfidence: 0.5,
        outputFaceBlendshapes: true,
      });
      let lm: FaceLandmarker;
      try {
        lm = await FaceLandmarker.createFromOptions(fileset, options("GPU"));
      } catch {
        lm = await FaceLandmarker.createFromOptions(fileset, options("CPU"));
      }
      warmUp(lm);
      return lm;
    })();
    landmarkerPromise.catch(() => {
      landmarkerPromise = null;
    });
  }
  return landmarkerPromise;
}

/**
 * The very first detection is slow (the graphics card prepares its programs, up to 2 seconds on slow machines).
 * Run it once on a blank picture while the candidate is still reading, so the camera check itself is quick.
 */
function warmUp(lm: { detectForVideo: (img: HTMLCanvasElement, ts: number) => unknown }) {
  try {
    const c = document.createElement("canvas");
    c.width = 64;
    c.height = 48;
    c.getContext("2d")?.fillRect(0, 0, 64, 48);
    lm.detectForVideo(c, performance.now());
  } catch {
    /* only an optimisation */
  }
}

function sampleFrom(result: FaceLandmarkerResult): FaceSample {
  const faces = result.faceLandmarks.length;
  if (faces === 0) return { faces, yaw: 0, pitch: 0, gazeX: 0, gazeY: 0, eyesClosed: false };
  const p = result.faceLandmarks[0];
  const nose = p[1], left = p[234], right = p[454], top = p[10], chin = p[152];
  const yaw = ((nose.x - left.x) / Math.max(1e-6, right.x - left.x) - 0.5) * 2;
  const pitch = (nose.y - top.y) / Math.max(1e-6, chin.y - top.y);
  const bs: Record<string, number> = {};
  for (const c of result.faceBlendshapes[0]?.categories ?? []) bs[c.categoryName] = c.score;
  const toRight = ((bs.eyeLookInLeft ?? 0) + (bs.eyeLookOutRight ?? 0)) / 2;
  const toLeft = ((bs.eyeLookOutLeft ?? 0) + (bs.eyeLookInRight ?? 0)) / 2;
  const down = ((bs.eyeLookDownLeft ?? 0) + (bs.eyeLookDownRight ?? 0)) / 2;
  const up = ((bs.eyeLookUpLeft ?? 0) + (bs.eyeLookUpRight ?? 0)) / 2;
  const eyesClosed = (bs.eyeBlinkLeft ?? 0) > 0.6 && (bs.eyeBlinkRight ?? 0) > 0.6;
  return { faces, yaw, pitch, gazeX: toRight - toLeft, gazeY: down - up, eyesClosed };
}

/** Classify one sample against the candidate's baseline. */
export function classify(s: FaceSample, b: Baseline | null): FaceState {
  if (s.faces === 0) return "no_face";
  if (s.faces > 1) return "multiple_faces";
  if (!b) return "ok";
  const dPitch = s.pitch - b.pitch;
  if (Math.abs(s.yaw - b.yaw) > LIMITS.yaw || dPitch < -LIMITS.pitchUp || dPitch > LIMITS.pitchDown) return "looking_away";
  if (s.eyesClosed) return "ok"; // a blink is not looking away
  const dgx = s.gazeX - b.gazeX, dgy = s.gazeY - b.gazeY;
  if (Math.abs(dgx) > LIMITS.gazeX || dgy > LIMITS.gazeDown || dgy < -LIMITS.gazeUp) return "eyes_away";
  return "ok";
}

/**
 * Runs face tracking on a camera stream. `onSample` gets every result (about 7 per second).
 * `calibrate()` resolves with the baseline once the candidate has looked straight at the screen for about a second.
 */
export function useFaceTracker(stream: MediaStream | null, onSample?: (s: FaceSample, state: FaceState) => void) {
  const [state, setState] = useState<FaceState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [progress, setProgress] = useState(0); // calibration progress, 0 to 1
  const baselineRef = useRef<Baseline | null>(null);
  const calib = useRef<{ samples: FaceSample[]; resolve: (b: Baseline) => void } | null>(null);
  const onSampleRef = useRef(onSample);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  onSampleRef.current = onSample;

  useEffect(() => {
    if (!stream) return;
    let stopped = false;
    let timer = 0;
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    videoRef.current = video;
    (async () => {
      try {
        await video.play();
        const landmarker = await loadFaceLandmarker();
        if (stopped) return;
        let lastTs = 0;
        const tick = () => {
          if (stopped) return;
          if (video.readyState >= 2 && video.videoWidth > 0) {
            const ts = Math.max(performance.now(), lastTs + 1);
            lastTs = ts;
            const sample = sampleFrom(landmarker.detectForVideo(video, ts));
            const c = calib.current;
            if (c) {
              // Blinks, missed frames and small movements are simply skipped; only a second face starts over.
              // A sample far from the others (the head moving) replaces the oldest instead of being averaged in.
              if (sample.faces === 1 && !sample.eyesClosed) {
                const last = c.samples[c.samples.length - 1];
                if (last && Math.abs(sample.yaw - last.yaw) > 0.2) c.samples = [sample];
                else c.samples.push(sample);
              } else if (sample.faces > 1) {
                c.samples = [];
              }
              setProgress(Math.min(1, c.samples.length / CALIBRATION_SAMPLES));
              if (c.samples.length >= CALIBRATION_SAMPLES) {
                const avg = (k: keyof Baseline) => c.samples.reduce((t, x) => t + x[k], 0) / c.samples.length;
                const b = { yaw: avg("yaw"), pitch: avg("pitch"), gazeX: avg("gazeX"), gazeY: avg("gazeY") };
                baselineRef.current = b;
                setBaseline(b);
                calib.current = null;
                c.resolve(b);
              }
            }
            const st = classify(sample, baselineRef.current);
            setState(st);
            onSampleRef.current?.(sample, st);
          }
          timer = window.setTimeout(tick, calib.current ? CALIBRATION_INTERVAL_MS : INTERVAL_MS);
        };
        tick();
      } catch (e) {
        if (!stopped) {
          setState("error");
          setError(e instanceof Error ? e.message : "Face tracking could not start");
        }
      }
    })();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      video.srcObject = null;
    };
  }, [stream]);

  const calibrate = useCallback(
    () => new Promise<Baseline>((resolve) => {
      setProgress(0);
      calib.current = { samples: [], resolve };
    }),
    [],
  );

  /** A small JPEG of the current camera frame (320 px wide). */
  const snapshot = useCallback(async (): Promise<Blob | null> => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return null;
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = Math.round((320 * v.videoHeight) / v.videoWidth);
    canvas.getContext("2d")?.drawImage(v, 0, 0, canvas.width, canvas.height);
    return new Promise((r) => canvas.toBlob((b) => r(b), "image/jpeg", 0.7));
  }, []);

  return { state, error, baseline, calibrate, snapshot, progress };
}

/** Asks for the webcam (separately from the microphone). */
export function useCamera() {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [status, setStatus] = useState<"idle" | "requesting" | "ready" | "denied" | "error" | "ended">("idle");
  const request = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("error");
      return null;
    }
    setStatus("requesting");
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" } });
      s.getVideoTracks()[0]?.addEventListener("ended", () => setStatus("ended"));
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
