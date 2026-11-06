import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { MicOff } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { Link, useParams } from "react-router-dom";
import { deviceTokens, errorMessage } from "../../api/client";
import { interviewsApi } from "../../api/endpoints";
import type { EventsResult, IntegrityEventType, InterviewState, SnapshotReason } from "../../api/types";
import { CameraCheck, ProctorPreview, useProctor } from "../../components/Proctor";
import { Button, Card, ErrorState, FullPageSpinner, Modal } from "../../components/ui";
import { loadFaceLandmarker, useCamera, useFaceTracker, type FaceSample, type FaceState } from "../../components/useFaceTracker";
import { loadObjectDetector, useObjectWatch, type ObjectKind } from "../../components/useObjectWatch";
import { hasSecondScreen, useLockdown } from "../../components/useLockdown";
import { useMicrophone, useRecorder, useVolume, type MicStatus } from "../../components/useRecorder";
import { useSpeech } from "../../components/useSpeech";

function VolumeMeter({ level }: { level: number }) {
  const bars = 20;
  return (
    <div className="flex h-8 items-end gap-0.5" aria-label="Microphone volume" role="meter" aria-valuenow={Math.round(level * 100)} aria-valuemin={0} aria-valuemax={100}>
      {Array.from({ length: bars }, (_, i) => (
        <div key={i} className={clsx("w-2 rounded-sm transition-all", i / bars < level ? (i > bars * 0.8 ? "bg-amber-500" : "bg-emerald-500") : "bg-slate-200")}
          style={{ height: `${30 + (i / bars) * 70}%` }} />
      ))}
    </div>
  );
}

function PermissionHelp({ status, onRetry }: { status: MicStatus; onRetry: () => void }) {
  if (status === "unsupported") {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
        Your browser doesn't support audio recording. Please open this link in the latest <b>Chrome</b>, <b>Edge</b>, <b>Firefox</b> or <b>Safari</b>.
        The page must be opened over HTTPS (or on localhost).
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
      <p className="flex items-center gap-2 font-semibold"><MicOff className="h-4 w-4" /> Microphone access is blocked</p>
      <p className="mt-1">The interview needs your microphone. Allow it, then press “Try again”.</p>
      <ul className="mt-3 list-disc space-y-1.5 pl-5">
        <li><b>Chrome:</b> click the lock/settings icon left of the address bar → Site settings → Microphone → Allow, then reload.</li>
        <li><b>Edge:</b> click the lock icon in the address bar → Permissions for this site → Microphone → Allow, then reload.</li>
        <li><b>Firefox:</b> click the microphone/permissions icon in the address bar → remove “Blocked temporarily”, then press Try again and choose Allow.</li>
        <li><b>Safari (Mac):</b> Safari menu → Settings for This Website → Microphone → Allow. <b>iPhone:</b> tap “aA” in the address bar → Website Settings → Microphone → Allow.</li>
        <li>Also check your computer's privacy settings allow the browser to use the microphone.</li>
      </ul>
      <Button size="sm" variant="secondary" className="mt-3" onClick={onRetry}>Try again</Button>
    </div>
  );
}

function ReportIssue({ sessionId }: { sessionId: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const send = useMutation({
    mutationFn: () => interviewsApi.reportIssue(sessionId, text),
    onSuccess: () => { toast.success("Thanks, the recruiter has been notified of the problem."); setOpen(false); setText(""); },
    onError: (err) => toast.error(errorMessage(err)),
  });
  return (
    <>
      <button onClick={() => setOpen(true)} className="inline-flex items-center gap-1 text-xs text-slate-500 underline-offset-2 hover:text-slate-800 hover:underline">
        Report a technical problem
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title="Report a technical problem"
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
          <Button loading={send.isPending} disabled={text.trim().length < 3} onClick={() => send.mutate()}>Send report</Button></>}>
        <label htmlFor="issue" className="label">What went wrong?</label>
        <textarea id="issue" rows={4} className="input" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000}
          placeholder="e.g. My microphone stopped working during question 3." />
        <p className="mt-2 text-xs text-slate-500">The recruiter will see this together with your interview.</p>
      </Modal>
    </>
  );
}

function formatTime(s: number) {
  const v = Math.max(0, Math.ceil(s));
  return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, "0")}`;
}

/** Re-renders a few times a second. Timers use the wall clock, so a throttled tab can't stretch them. */
function useNow(active: boolean) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => setNow(Date.now()), 200);
    return () => window.clearInterval(t);
  }, [active]);
  return now;
}

type Phase = "speaking" | "thinking" | "recording" | "uploading" | "error";

function TimerRing({ seconds, total, label, danger }: { seconds: number; total: number; label: string; danger?: boolean }) {
  const pct = total > 0 ? Math.max(0, Math.min(1, seconds / total)) : 0;
  return (
    <div className="relative flex h-40 w-40 items-center justify-center rounded-full"
      style={{ background: `conic-gradient(${danger ? "#f43f5e" : "#0a0a0a"} ${pct * 360}deg, #e5e5e5 0deg)` }}>
      <div className="flex h-32 w-32 flex-col items-center justify-center rounded-full bg-white">
        <span className={clsx("text-4xl font-bold tabular-nums", danger ? "text-rose-600" : "text-slate-900")} aria-live="off">{formatTime(seconds)}</span>
        <span className="text-xs text-slate-500">{label}</span>
      </div>
    </div>
  );
}

/**
 * One question, strictly timed:
 * 1. the question is shown and read aloud, slowly (the text can't be selected or copied);
 * 2. thinking time counts down (the question can be repeated once);
 * 3. recording starts by itself and is submitted when the answer time ends. No re-recording.
 * All times come from the server's deadline, so reloading the page does not give extra time.
 */
function QuestionScreen({ state, stream, report, onDone, onPhase, attention }: {
  state: InterviewState;
  stream: MediaStream;
  report: (type: IntegrityEventType, detail?: string) => void;
  onDone: (s: InterviewState | "completed") => void;
  onPhase?: (p: Phase) => void;
  /** Webcam: percent of the answer spent looking at the screen. */
  attention?: () => number | null;
}) {
  const { start, stop, recording, ext } = useRecorder(stream);
  const level = useVolume(stream);
  const speech = useSpeech();
  const [phase, setPhase] = useState<Phase>("speaking");
  const [repeated, setRepeated] = useState(false);
  const [repeating, setRepeating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [blob, setBlob] = useState<Blob | null>(null);
  const deadline = useRef(Date.now() + ((state.seconds_left ?? 9999) - 4) * 1000);
  const thinkEnd = useRef(0);
  const answerEnd = useRef(0);
  const answerTotal = useRef(state.seconds_per_question);
  const thinkTotal = useRef(state.think_seconds);
  const busy = useRef(false);
  const now = useNow(phase === "thinking" || phase === "recording");
  const followUp = state.current_kind === "follow_up";

  const secondsLeftOverall = () => (deadline.current - Date.now()) / 1000;

  const submit = useCallback(async (audio: Blob) => {
    setPhase("uploading");
    setError(null);
    try {
      const res = await interviewsApi.answer(state.session_id, state.current_index, audio, `answer-q${state.current_index + 1}.${ext}`, attention?.());
      if (res.completed) onDone("completed");
      else onDone({ ...state, current_index: res.next_index!, current_question: res.next_question, current_kind: res.next_kind, total_questions: res.total_questions, seconds_left: res.seconds_left });
    } catch (err) {
      setError(errorMessage(err, "We couldn't upload your answer."));
      setPhase("error");
    }
  }, [state, ext, onDone, attention]);

  const skip = useCallback(async () => {
    setPhase("uploading");
    try {
      const res = await interviewsApi.skip(state.session_id, state.current_index);
      if (res.completed) onDone("completed");
      else onDone({ ...state, current_index: res.next_index!, current_question: res.next_question, current_kind: res.next_kind, total_questions: res.total_questions, seconds_left: res.seconds_left });
    } catch (err) {
      setError(errorMessage(err, "Something went wrong."));
      setPhase("error");
    }
  }, [state, onDone]);

  const startAnswer = useCallback(() => {
    if (busy.current) return;
    speech.cancel();
    setRepeating(false);
    const secs = Math.min(state.seconds_per_question, Math.floor(secondsLeftOverall()));
    if (secs < 3) { skip(); return; }
    answerTotal.current = secs;
    answerEnd.current = Date.now() + secs * 1000;
    if (start()) setPhase("recording");
    else { setError("The microphone stopped working."); setPhase("error"); }
  }, [speech, state.seconds_per_question, skip, start]);

  const finishAnswer = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    const audio = await stop();
    setBlob(audio);
    await submit(audio);
    busy.current = false;
  }, [stop, submit]);

  const beginThinking = useCallback(() => {
    const secs = Math.min(state.think_seconds, Math.floor(secondsLeftOverall() - state.seconds_per_question));
    if (secs <= 0) { startAnswer(); return; }
    thinkTotal.current = secs;
    thinkEnd.current = Date.now() + secs * 1000;
    setPhase("thinking");
  }, [state.think_seconds, state.seconds_per_question, startAnswer]);

  // 1. Read the question aloud as soon as it appears.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (secondsLeftOverall() < 3) { skip(); return; }
      if (speech.supported) {
        await speech.speak(state.current_question ?? "");
      } else {
        report("tts_unavailable");
        await new Promise((r) => window.setTimeout(r, Math.min(15, (state.current_question ?? "").split(" ").length / 3) * 1000));
      }
      if (!cancelled) beginThinking();
    })();
    return () => { cancelled = true; speech.cancel(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onPhaseRef = useRef(onPhase);
  onPhaseRef.current = onPhase;
  useEffect(() => onPhaseRef.current?.(phase), [phase]);

  // 2./3. Countdowns.
  useEffect(() => {
    if (phase === "thinking" && now >= thinkEnd.current) startAnswer();
    if (phase === "recording" && now >= answerEnd.current) finishAnswer();
  }, [now, phase, startAnswer, finishAnswer]);

  const repeat = async () => {
    if (repeated || !speech.supported) return;
    setRepeated(true);
    setRepeating(true);
    report("question_repeated");
    await speech.speak(state.current_question ?? "", { slower: true });
    setRepeating(false);
  };

  const thinkLeft = (thinkEnd.current - now) / 1000;
  const answerLeft = (answerEnd.current - now) / 1000;

  return (
    <Card className="p-6 sm:p-8">
      <div className="flex items-center justify-between text-sm text-slate-500">
        <span className="font-medium text-slate-900">
          Question {state.current_index + 1} of {state.total_questions}
          {followUp && <span className="ml-2 rounded-md bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">Follow-up</span>}
        </span>
        <span>{state.job_title}</span>
      </div>
      <div className="mt-3 h-1 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full bg-brand-600 transition-all" style={{ width: `${(state.current_index / state.total_questions) * 100}%` }} />
      </div>

      <div className="mt-6 min-h-[4rem]">
        {followUp && <p className="mb-2 text-sm text-slate-500">A follow-up based on your last answer:</p>}
        {/* shown and read aloud; selecting and copying it is blocked */}
        <h2 className="select-none font-display text-xl font-bold leading-snug text-slate-900 sm:text-2xl" onCopy={(e) => e.preventDefault()}>
          {state.current_question}
        </h2>
      </div>

      {phase === "uploading" ? (
        <div className="mt-6 flex flex-col items-center py-8 text-center">
          <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-slate-200 border-t-brand-600" />
          <p className="mt-4 font-medium">Saving your answer…</p>
          <p className="text-sm text-slate-500">Please wait, the next question will start by itself.</p>
        </div>
      ) : phase === "error" ? (
        <div className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" role="alert">
          <p className="font-medium">{error}</p>
          <p className="mt-1">Your recording is kept. Check your internet connection and try again.</p>
          <Button className="mt-3" onClick={() => (blob ? submit(blob) : skip())}>Try again</Button>
        </div>
      ) : (
        <div className="mt-4 flex flex-col items-center">
          {phase === "speaking" && (
            <div className="flex flex-col items-center py-6">
              <div className="flex h-16 items-end gap-1.5" aria-hidden>
                {[0, 1, 2, 3, 4].map((i) => (
                  <span key={i} className="w-2 animate-pulse rounded-full bg-brand-600" style={{ height: `${[40, 75, 100, 75, 40][i]}%`, animationDelay: `${i * 120}ms` }} />
                ))}
              </div>
              <p className="mt-4 font-medium text-slate-700">Reading the question aloud…</p>
              <p className="text-xs text-slate-500">Make sure your speakers or headphones are on.</p>
            </div>
          )}
          {phase === "thinking" && (
            <>
              <TimerRing seconds={thinkLeft} total={thinkTotal.current} label="to think" />
              <p className="mt-3 text-sm font-medium text-slate-700">Think about your answer. Recording starts automatically.</p>
              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                {speech.supported && (
                  <Button variant="secondary" disabled={repeated} loading={repeating} onClick={repeat}>
                    {repeated ? "Question repeated" : "Hear it again, slower (once)"}
                  </Button>
                )}
                <Button onClick={startAnswer}>I'm ready, start answering</Button>
              </div>
            </>
          )}
          {phase === "recording" && (
            <>
              <TimerRing seconds={answerLeft} total={answerTotal.current} label="to answer" danger={answerLeft <= 10} />
              {recording && (
                <div className="mt-4 flex items-center gap-2 text-sm font-medium text-rose-600">
                  <span className="h-2.5 w-2.5 animate-ping rounded-full bg-rose-600" /> Recording. Answer out loud now.
                </div>
              )}
              <div className="mt-3"><VolumeMeter level={level} /></div>
              <Button size="lg" className="mt-6" disabled={answerTotal.current - answerLeft < 5} onClick={finishAnswer}>
                I've finished my answer
              </Button>
              <p className="mt-2 text-xs text-slate-500">Your answer is submitted automatically when the time ends. There is no re-recording.</p>
            </>
          )}
        </div>
      )}
    </Card>
  );
}

function StrikeBanner({ strikes, max }: { strikes: number; max: number }) {
  if (strikes === 0) return null;
  return (
    <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="alert">
      <p><b>Warning {strikes} of {max}:</b> you left the interview window. {max - strikes === 1 ? "One more time and the interview ends automatically." : `After ${max} times the interview ends automatically.`}</p>
    </div>
  );
}

const OBJECT_EVENT = {
  phone: "phone_detected", book: "book_detected", screen: "screen_detected", person: "multiple_faces",
} as const satisfies Record<ObjectKind, IntegrityEventType & SnapshotReason>;

export default function Interview() {
  const { sessionId } = useParams();
  const qc = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["interview", sessionId], queryFn: () => interviewsApi.get(sessionId!), refetchOnWindowFocus: false });
  const mic = useMicrophone();
  const level = useVolume(mic.stream);
  const speech = useSpeech();
  const [state, setState] = useState<InterviewState | null>(null);
  const [completed, setCompleted] = useState(false);
  const [terminated, setTerminated] = useState(false);
  const [strikes, setStrikes] = useState(0);
  const [agreed, setAgreed] = useState(false);
  const [heardTest, setHeardTest] = useState(!speech.supported);
  const [startError, setStartError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [calibrated, setCalibrated] = useState(false);
  const requireWebcam = Boolean(data?.require_webcam);
  const cam = useCamera();
  const sampleRef = useRef<(s: FaceSample, st: FaceState) => void>();
  const tracker = useFaceTracker(cam.stream, (s, st) => sampleRef.current?.(s, st));
  // Download the face-tracking model while the candidate reads the instructions, not after the camera opens.
  useEffect(() => {
    if (!requireWebcam) return;
    // face model first (needed for the camera check), then the object model in the background
    loadFaceLandmarker().catch(() => undefined).finally(() => loadObjectDetector().catch(() => undefined));
  }, [requireWebcam]);

  const onEvents = useCallback((r: EventsResult) => {
    setStrikes(r.strikes);
    if (r.terminated) setTerminated(true);
  }, []);
  const lock = useLockdown(sessionId!, state?.current_index ?? 0, onEvents);
  const proctor = useProctor({
    enabled: requireWebcam && lock.active && cam.status === "ready" && !completed && !terminated,
    sessionId: sessionId!,
    questionIndex: state?.current_index ?? 0,
    tracker,
    report: lock.report,
  });
  sampleRef.current = proctor.onSample;
  const objects = useObjectWatch(
    cam.stream,
    requireWebcam && lock.active && cam.status === "ready" && !completed && !terminated,
    (kind) => {
      const type = OBJECT_EVENT[kind];
      lock.report(type, kind === "person" ? "second person seen on camera" : undefined);
      proctor.snapshot(type);
    },
    () => lock.report("object_detection_unavailable"),
  );

  // Turning the camera off (or unplugging it) during the interview counts like leaving the window.
  useEffect(() => {
    if (requireWebcam && lock.active && cam.status === "ended") lock.report("camera_off");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cam.status]);

  const onDone = useCallback((s: InterviewState | "completed") => {
    if (s === "completed") {
      setCompleted(true);
      qc.invalidateQueries({ queryKey: ["applications"] });
    } else setState(s);
  }, [qc]);

  useEffect(() => {
    if (completed || terminated) {
      lock.release();
      qc.invalidateQueries({ queryKey: ["applications"] });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [completed, terminated]);

  // The serverless backend can sleep while the candidate reads; wake it before they click.
  const warmedAt = useRef(0);
  const warmServer = () => {
    if (Date.now() - warmedAt.current < 60_000) return;
    warmedAt.current = Date.now();
    interviewsApi.get(sessionId!).catch(() => undefined);
  };

  const begin = async () => {
    setStartError(null);
    if (hasSecondScreen()) {
      setStartError("A second screen is connected. Disconnect it (or set Windows to show only one screen) and try again.");
      return;
    }
    setStarting(true);
    const resuming = data?.status === "in_progress";
    const ok = await lock.enterFullscreen();
    if (!ok) {
      setStarting(false);
      setStartError("The interview must run in full screen. Please allow full screen and try again (use Chrome or Edge on a computer).");
      return;
    }
    try {
      const s = await interviewsApi.start(sessionId!);
      setStrikes(s.strikes);
      if (s.terminated || !s.can_answer) { lock.release(); refetch(); return; }
      setState(s);
      lock.setActive(true);
      if (resuming) lock.report("page_reload");
      if (requireWebcam) window.setTimeout(() => proctor.snapshot("start"), 1500);
    } catch (err) {
      lock.release();
      setStartError(errorMessage(err));
    } finally {
      setStarting(false);
    }
  };

  if (isLoading) return <FullPageSpinner />;
  if (error) return <ErrorState message={errorMessage(error, "Interview not found.")} onRetry={() => refetch()} />;
  const info = data!;

  let content: React.ReactNode;
  if (terminated || info.terminated) {
    content = (
      <Card className="mx-auto max-w-xl p-8 text-center">
        <h1 className="font-display text-2xl font-extrabold tracking-tight">The interview has ended</h1>
        <p className="mt-2 text-slate-600">The interview reached {info.max_strikes} warnings, so it was closed automatically. Your answers so far were saved and the recruiter will review them.</p>
        <Link to="/applications"><Button className="mt-6">Back to my applications</Button></Link>
      </Card>
    );
  } else if (completed || info.status === "completed") {
    content = (
      <Card className="mx-auto max-w-xl p-8 text-center">
        <h1 className="font-display text-2xl font-extrabold tracking-tight">Interview complete. Thank you!</h1>
        <p className="mt-2 text-slate-600">Your answers for <b>{info.job_title}</b> have been submitted. The recruiter will review your application and contact you by email.</p>
        <Link to="/applications"><Button className="mt-6">Back to my applications</Button></Link>
      </Card>
    );
  } else if (!info.can_answer) {
    content = <ErrorState message="This interview is no longer available. The position may have been closed." />;
  } else if (lock.otherTab && !lock.active) {
    content = <ErrorState message="This interview is already open in another tab or window. Close this tab and continue there." />;
  } else if (state && mic.stream && lock.active) {
    content = (
      <>
        <div className="mb-3 flex items-center justify-between text-xs text-slate-500">
          <span className="font-medium text-slate-700">Secure interview mode</span>
          <span>Warnings: {strikes} / {state.max_strikes}</span>
        </div>
        <StrikeBanner strikes={strikes} max={state.max_strikes} />
        {requireWebcam && <ProctorPreview stream={cam.stream} state={tracker.state} warning={proctor.warning} objects={objects.visible} />}
        <QuestionScreen key={`${state.current_index}-${state.total_questions}`} state={state} stream={mic.stream} report={lock.report} onDone={onDone}
          onPhase={proctor.onPhase} attention={requireWebcam ? proctor.attention : undefined} />
      </>
    );
  } else if (starting) {
    content = (
      <div className="flex min-h-[60vh] flex-col items-center justify-center text-center" role="status">
        <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-slate-200 border-t-brand-600" />
        <p className="mt-5 text-lg font-semibold text-slate-900">Preparing your interview…</p>
        <p className="mt-1 text-sm text-slate-500">The first question starts in a moment. Stay in full screen.</p>
      </div>
    );
  } else {
    const resuming = info.status === "in_progress";
    const mins = Math.round((info.seconds_per_question / 60) * 10) / 10;
    const facts: [string, string][] = [
      ["Questions", `${info.total_questions}${info.follow_ups_planned > 0 ? ` + ${info.follow_ups_planned}` : ""}`],
      ["Time to think", `${info.think_seconds} s`],
      ["Time to answer", `${mins} min`],
      ["Warnings allowed", `${info.max_strikes - 1}`],
    ];
    const rules = [
      <>Each question is <b>shown on screen and read aloud</b>. You can hear it again <b>once</b>.</>,
      <>Recording <b>starts automatically</b> after the thinking time and is submitted when the time ends. There is no re-recording.</>,
      ...(info.follow_ups_planned > 0 ? [<>Some <b>follow-up questions</b> are based on what you say.</>] : []),
      <>The interview runs in <b>locked full screen</b>. Copy, paste, right-click, shortcuts and other tabs are blocked.</>,
      <>Leaving full screen, switching tab or app, or reloading gives a warning. After <b>{info.max_strikes} warnings</b> the interview ends.</>,
      ...(requireWebcam ? [<>Your <b>webcam stays on</b> to check you are alone, looking at the screen and not using a phone or notes. A few photos are kept for the recruiter; video is not recorded.</>] : []),
      <>Use <b>Chrome or Edge on a computer</b> with one screen, in a quiet room. The interview works on <b>one device only</b>.</>,
    ];
    const ready = mic.status === "ready" && agreed && heardTest && (!requireWebcam || calibrated);
    content = (
      <div className="grid overflow-hidden rounded-xl border border-slate-200 bg-white lg:grid-cols-[1fr_420px]">
        <section className="p-6 lg:p-7">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Voice interview</p>
          <h1 className="mt-1.5 font-display text-2xl font-extrabold tracking-tight text-slate-900">{info.job_title}</h1>
          {info.device_locked && !deviceTokens.get(info.session_id) && (
            <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
              This interview was started on another device or browser. Continue there, or ask the recruiter to allow a new device.
            </p>
          )}
          {resuming && (
            <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              You left the interview while it was running ({info.current_index} of {info.total_questions} answered). Continuing counts as one warning.
            </p>
          )}
          <dl className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 sm:grid-cols-4">
            {facts.map(([k, v]) => (
              <div key={k} className="bg-white px-3 py-2.5">
                <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{k}</dt>
                <dd className="mt-0.5 text-base font-semibold text-slate-900">{v}</dd>
              </div>
            ))}
          </dl>
          <h2 className="font-display mt-6 text-sm font-bold text-slate-900">Before you start</h2>
          <ol className="mt-2.5 space-y-2 text-sm leading-relaxed text-slate-600">
            {rules.map((r, i) => (
              <li key={i} className="flex gap-3">
                <span className="w-4 shrink-0 text-right font-medium tabular-nums text-slate-400">{i + 1}.</span>
                <span>{r}</span>
              </li>
            ))}
          </ol>
        </section>

        <section className="flex flex-col border-t border-slate-200 bg-slate-50/60 p-5 lg:border-l lg:border-t-0">
          <h2 className="font-display text-sm font-bold text-slate-900">Check your setup</h2>
          <div className="mt-3 divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
            <div className="px-3.5 py-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium">Microphone</h3>
                {mic.status === "ready" && <span className="text-xs text-slate-500">Say something. The bars should move.</span>}
              </div>
              {mic.status === "ready" ? (
                <div className="mt-2"><VolumeMeter level={level} /></div>
              ) : mic.status === "denied" || mic.status === "unsupported" || mic.status === "error" ? (
                <div className="mt-2">
                  {mic.status === "error"
                    ? <ErrorState message="We couldn't access a microphone. Check that one is connected and not used by another app." onRetry={mic.request} />
                    : <PermissionHelp status={mic.status} onRetry={mic.request} />}
                </div>
              ) : (
                <Button className="mt-2" size="sm" variant="secondary" loading={mic.status === "requesting"} onClick={mic.request}>Allow microphone</Button>
              )}
            </div>
            <div className="px-3.5 py-3">
              <h3 className="text-sm font-medium">Speakers</h3>
              {speech.supported ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button variant="secondary" size="sm" onClick={() => speech.speak("Hello. This is how your interview questions will sound.")}>Play test</Button>
                  <Button variant={heardTest ? "primary" : "secondary"} size="sm" onClick={() => setHeardTest(true)}>{heardTest ? "I can hear it ✓" : "I can hear it"}</Button>
                </div>
              ) : (
                <p className="mt-1 text-sm text-amber-700">This browser can't read questions aloud, so they will be shown as text.</p>
              )}
            </div>
            {requireWebcam && (
              <div className="px-3.5 py-3">
                <h3 className="text-sm font-medium">Camera</h3>
                <CameraCheck cam={cam} tracker={tracker} calibrated={calibrated} onCalibrated={() => setCalibrated(true)} />
              </div>
            )}
          </div>

          <label className="mt-3 flex items-start gap-2.5 text-xs leading-relaxed text-slate-600">
            <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-brand-600" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
            <span>I will answer on my own, without help from people, websites or AI tools, and I understand that leaving the interview window is recorded{requireWebcam && " and my webcam is checked"}.</span>
          </label>

          {startError && <p className="mt-3 rounded-lg bg-rose-50 p-2.5 text-sm text-rose-700" role="alert">{startError}</p>}

          <Button size="lg" className="mt-3 w-full" disabled={!ready} onClick={begin} onPointerEnter={warmServer}>
            {resuming ? "Continue in full screen" : "Enter full screen and start"}
          </Button>
          <div className="mt-2 text-center"><ReportIssue sessionId={info.session_id} /></div>
        </section>
      </div>
    );
  }

  const locked = lock.active && !completed && !terminated;
  return (
    <div ref={lock.containerRef}
      className={clsx(locked || starting ? "fixed inset-0 z-[90] select-none overflow-y-auto bg-canvas px-4 py-8" : "", "interview-lockdown")}>
      <div className={clsx("mx-auto", locked || starting ? "max-w-2xl" : "max-w-6xl")}>
        {content}
      </div>
      {locked && lock.inFullscreen && requireWebcam && cam.status !== "ready" && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/90 p-4" role="alertdialog" aria-modal="true" aria-labelledby="cam-title">
          <div className="max-w-md rounded-xl bg-white p-6 text-center shadow-xl">
            <h2 id="cam-title" className="font-display text-xl font-bold">Your camera stopped</h2>
            <p className="mt-2 text-sm text-slate-600">The interview needs your webcam. This was recorded as a warning. Turn the camera back on to continue. The timer is still running.</p>
            {cam.status === "denied" && <p className="mt-2 text-sm text-rose-700">Camera access is blocked. Allow it from the camera icon in the address bar.</p>}
            <Button size="lg" className="mt-5 w-full" loading={cam.status === "requesting"} onClick={cam.request}>Turn the camera back on</Button>
          </div>
        </div>
      )}
      {locked && !lock.inFullscreen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/90 p-4" role="alertdialog" aria-modal="true" aria-labelledby="fs-title">
          <div className="max-w-md rounded-xl bg-white p-6 text-center shadow-xl">
            <h2 id="fs-title" className="font-display text-xl font-bold">Go back to full screen</h2>
            <p className="mt-2 text-sm text-slate-600">You left the interview. This was warning <b>{strikes} of {state?.max_strikes ?? 3}</b>. The timer is still running.</p>
            <Button size="lg" className="mt-5 w-full" onClick={() => lock.enterFullscreen()}>Return to full screen</Button>
          </div>
        </div>
      )}
    </div>
  );
}
