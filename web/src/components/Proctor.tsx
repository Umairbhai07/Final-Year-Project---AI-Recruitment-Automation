import clsx from "clsx";
import { CameraOff, Eye, Users } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { interviewsApi } from "../api/endpoints";
import type { IntegrityEventType, SnapshotReason } from "../api/types";
import { Button } from "./ui";
import type { FaceSample, FaceState, useCamera, useFaceTracker } from "./useFaceTracker";
import type { ObjectKind } from "./useObjectWatch";

type Tracker = ReturnType<typeof useFaceTracker>;
type Cam = ReturnType<typeof useCamera>;
type Phase = "speaking" | "thinking" | "recording" | "uploading" | "error";

/** Live, mirrored camera picture. */
export function CameraView({ stream, className }: { stream: MediaStream | null; className?: string }) {
  const ref = useRef<HTMLVideoElement | null>(null);
  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    v.srcObject = stream;
    if (stream) v.play().catch(() => undefined);
  }, [stream]);
  return <video ref={ref} muted playsInline autoPlay className={clsx("-scale-x-100 bg-slate-900 object-cover", className)} />;
}

const MESSAGES: Record<FaceState, string> = {
  loading: "Starting face tracking…",
  ok: "Face detected",
  no_face: "We can't see your face",
  multiple_faces: "More than one person is in view",
  looking_away: "Please face the screen",
  eyes_away: "Please look at the screen",
  error: "Face tracking could not start",
};

/** Intro step: allow the camera, check the face is visible and record the "looking at the screen" baseline. */
export function CameraCheck({ cam, tracker, calibrated, onCalibrated }: {
  cam: Cam;
  tracker: Tracker;
  calibrated: boolean;
  onCalibrated: () => void;
}) {
  const [calibrating, setCalibrating] = useState(false);
  const { calibrate } = tracker;
  const onCalibratedRef = useRef(onCalibrated);
  onCalibratedRef.current = onCalibrated;
  const run = useCallback(async () => {
    setCalibrating(true);
    await calibrate();
    setCalibrating(false);
    onCalibratedRef.current();
  }, [calibrate]);

  // Start calibrating by itself once one face has been clearly in view for a moment.
  const st0 = tracker.state;
  useEffect(() => {
    if (calibrated || calibrating || cam.status !== "ready" || st0 !== "ok") return;
    const t = window.setTimeout(run, 250);
    return () => window.clearTimeout(t);
  }, [calibrated, calibrating, cam.status, st0, run]);

  if (cam.status !== "ready") {
    return (
      <div className="mt-3">
        {cam.status === "denied" ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-semibold">Camera access is blocked</p>
            <p className="mt-1">This interview needs your webcam. Click the camera icon in the address bar, choose Allow, then press Try again.</p>
            <Button size="sm" variant="secondary" className="mt-2" onClick={cam.request}>Try again</Button>
          </div>
        ) : cam.status === "error" || cam.status === "ended" ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p>We couldn't use a camera. Check one is connected and not used by another app (Zoom, Teams, Camera).</p>
            <Button size="sm" variant="secondary" className="mt-2" onClick={cam.request}>Try again</Button>
          </div>
        ) : (
          <Button variant="secondary" loading={cam.status === "requesting"} onClick={cam.request}>Allow camera</Button>
        )}
      </div>
    );
  }

  const st = tracker.state;
  const good = st === "ok" || (calibrated && st !== "no_face" && st !== "multiple_faces" && st !== "error");
  return (
    <div className="mt-2 flex flex-col gap-3">
      <div className={clsx("relative w-full overflow-hidden rounded-lg border-2", st === "ok" ? "border-emerald-500" : st === "loading" ? "border-slate-200" : "border-rose-500")}>
        <CameraView stream={cam.stream} className="aspect-video w-full" />
        <span className="absolute inset-x-0 bottom-0 bg-black/60 px-1 py-1 text-center text-[11px] font-medium text-white sm:text-xs">{MESSAGES[st]}</span>
      </div>
      <div className="min-w-0 flex-1 text-sm text-slate-600">
        {tracker.error ? (
          <p className="text-rose-700">Face tracking could not start ({tracker.error}). Please use the latest Chrome or Edge.</p>
        ) : calibrated ? (
          <p className="font-medium text-emerald-700">Camera ready and calibrated.</p>
        ) : calibrating ? (
          <div>
            <p className="font-medium text-brand-700">Look at the middle of the screen…</p>
            <div className="mt-2 h-1.5 w-full max-w-[200px] overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-600 transition-all duration-150" style={{ width: `${Math.round(tracker.progress * 100)}%` }} />
            </div>
          </div>
        ) : st === "loading" ? (
          <p className="text-xs leading-relaxed">Getting the face check ready. This takes a few seconds the first time.</p>
        ) : (
          <>
            <p className="text-xs leading-relaxed">Sit in good light with your face in the picture. Calibration starts by itself.</p>
            <Button size="sm" variant="secondary" className="mt-2" disabled={!good} onClick={run}>Calibrate now</Button>
          </>
        )}
      </div>
    </div>
  );
}

// How long something must last before it is reported (short glances and blinks are normal).
const SUSTAIN_MS: Record<string, number> = { no_face: 2500, multiple_faces: 1000, looking_away: 2500, eyes_away: 3000 };
const SUSTAIN_THINKING_MS: Record<string, number> = { ...SUSTAIN_MS, looking_away: 4000, eyes_away: 5000 }; // people look up to think
const WARN_AFTER_MS = 1200;
const OK_RESET_MS = 700;
const SNAPSHOT_GAP_MS = 12_000;
const MAX_SNAPSHOTS = 30;

/**
 * Turns the face tracker's per-frame results into what the recruiter sees:
 * - an event for each sustained problem (no face, two faces, head turned away, eyes off the screen),
 * - the share of each answer spent looking at the screen ("attention"),
 * - a few small photos (at the start, once at a random moment in each answer, and when something is flagged).
 * The candidate gets an on-screen warning as soon as a problem lasts more than about a second.
 */
export function useProctor({ enabled, sessionId, questionIndex, tracker, report }: {
  enabled: boolean;
  sessionId: string;
  questionIndex: number;
  tracker: Tracker;
  report: (type: IntegrityEventType, detail?: string) => void;
}) {
  const [warning, setWarning] = useState<FaceState | null>(null);
  const phase = useRef<Phase>("speaking");
  const episode = useRef<{ type: FaceState; since: number; reported: boolean } | null>(null);
  const okSince = useRef<number | null>(null);
  const counts = useRef({ ok: 0, total: 0 });
  const snaps = useRef({ count: 0, lastFlag: 0 });
  const randomTimer = useRef(0);
  const qIndex = useRef(questionIndex);
  const enabledRef = useRef(enabled);
  const takePhoto = tracker.snapshot; // stable
  qIndex.current = questionIndex;
  enabledRef.current = enabled;

  const snapshot = useCallback(async (reason: SnapshotReason) => {
    if (!enabledRef.current || snaps.current.count >= MAX_SNAPSHOTS) return;
    if (reason !== "start" && reason !== "random" && reason !== "multiple_faces") {
      if (Date.now() - snaps.current.lastFlag < SNAPSHOT_GAP_MS) return;
      snaps.current.lastFlag = Date.now();
    }
    snaps.current.count += 1;
    const blob = await takePhoto();
    if (blob) interviewsApi.snapshot(sessionId, blob, reason, qIndex.current).catch(() => undefined);
  }, [sessionId, takePhoto]);

  const onSample = useCallback((_s: FaceSample, st: FaceState) => {
    if (!enabledRef.current || st === "loading" || st === "error") return;
    const p = phase.current;
    const now = Date.now();
    if (p === "recording") {
      counts.current.total += 1;
      if (st === "ok") counts.current.ok += 1;
    }
    if (st === "ok") {
      okSince.current ??= now;
      if (now - okSince.current >= OK_RESET_MS) {
        episode.current = null;
        setWarning(null);
      }
      return;
    }
    okSince.current = null;
    if (episode.current?.type !== st) episode.current = { type: st, since: now, reported: false };
    const ep = episode.current;
    const lasted = now - ep.since;
    if (lasted >= WARN_AFTER_MS || st === "multiple_faces") setWarning(st);
    const limit = (p === "thinking" || p === "speaking" ? SUSTAIN_THINKING_MS : SUSTAIN_MS)[st];
    if (!ep.reported && limit !== undefined && lasted >= limit && p !== "uploading" && p !== "error") {
      ep.reported = true;
      report(st as IntegrityEventType, p === "recording" ? "while answering" : p === "thinking" ? "while thinking" : "while the question was read");
      snapshot(st as SnapshotReason);
    }
  }, [report, snapshot]);

  /** QuestionScreen tells us its phase; one random photo is taken during each answer. */
  const onPhase = useCallback((p: Phase) => {
    phase.current = p;
    window.clearTimeout(randomTimer.current);
    if (p === "recording" && enabledRef.current) {
      counts.current = { ok: 0, total: 0 };
      randomTimer.current = window.setTimeout(() => snapshot("random"), 3000 + Math.random() * 15000);
    }
  }, [snapshot]);

  /** Percent of the answer the candidate was looking at the screen, or null without a camera. */
  const attention = useCallback(() => {
    const c = counts.current;
    return enabledRef.current && c.total >= 5 ? (100 * c.ok) / c.total : null;
  }, []);

  useEffect(() => () => window.clearTimeout(randomTimer.current), []);

  return { onSample, onPhase, attention, snapshot, warning };
}

const WARN_TEXT: Partial<Record<FaceState, { icon: typeof Eye; text: string }>> = {
  no_face: { icon: CameraOff, text: "We can't see your face. Stay in front of the camera." },
  multiple_faces: { icon: Users, text: "Someone else is in view. Only you may be in the room." },
  looking_away: { icon: Eye, text: "Please turn back to the screen." },
  eyes_away: { icon: Eye, text: "Please keep your eyes on the screen." },
};

/** Small camera picture shown during the interview, with a coloured border and a warning when needed. */
const OBJECT_TEXT: Record<ObjectKind, string> = {
  phone: "A mobile phone is visible. Put it away, out of view.",
  book: "A book or notes are visible. Put them away.",
  screen: "Another screen is visible. Turn it off or move it away.",
  person: "Someone else is in view. Only you may be in the room.",
};

export function ProctorPreview({ stream, state, warning, objects = [] }: { stream: MediaStream | null; state: FaceState; warning: FaceState | null; objects?: ObjectKind[] }) {
  const w = objects.length ? { text: OBJECT_TEXT[objects[0]] } : warning ? WARN_TEXT[warning] : undefined;
  return (
    <>
      {/* in the page above the question on phones and tablets, in the top corner on large screens */}
      <div className={clsx("relative mx-auto mb-4 w-fit overflow-hidden rounded-lg border-2 shadow-lg lg:fixed lg:right-4 lg:top-4 lg:z-[95] lg:mb-0",
        state === "ok" && !objects.length ? "border-emerald-500" : state === "loading" ? "border-slate-300" : "border-rose-500")}>
        <CameraView stream={stream} className="h-44 w-60 sm:h-52 sm:w-72 lg:h-56 lg:w-80" />
        <span className="absolute inset-x-0 bottom-0 bg-black/60 px-1 py-1 text-center text-[11px] font-medium text-white sm:text-xs">
          {state === "ok" ? "Camera on" : MESSAGES[state]}
        </span>
      </div>
      {w && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm font-medium text-rose-800" role="alert">
          {w.text} This is recorded for the recruiter.
        </div>
      )}
    </>
  );
}
