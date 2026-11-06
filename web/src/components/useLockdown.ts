import { useCallback, useEffect, useRef, useState } from "react";
import { interviewsApi } from "../api/endpoints";
import type { EventsResult, IntegrityEventType } from "../api/types";

/** Leaving the interview window. The server counts each one (merged within 3 s) as a strike. */
const STRIKES: IntegrityEventType[] = ["fullscreen_exit", "tab_hidden", "window_blur", "page_reload", "multiple_tabs", "camera_off"];

const DEVTOOLS_KEYS = (e: KeyboardEvent) =>
  e.key === "F12" ||
  ((e.ctrlKey || e.metaKey) && e.shiftKey && ["i", "j", "c"].includes(e.key.toLowerCase())) ||
  ((e.ctrlKey || e.metaKey) && e.altKey && ["i", "j", "c"].includes(e.key.toLowerCase())) ||
  ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "u");

const BLOCKED_COMBOS = new Set(["a", "c", "v", "x", "p", "s", "f", "g", "h", "j", "k", "l", "n", "o", "r", "t", "w", "d"]);

type KeyboardLock = { lock?: (keys?: string[]) => Promise<void>; unlock?: () => void };

export function hasSecondScreen(): boolean {
  return Boolean((window.screen as Screen & { isExtended?: boolean }).isExtended);
}

/**
 * Full-screen interview lockdown, as strict as a web page can be:
 * - the interview runs full screen on one element (the rest of the site is not visible or clickable);
 * - Chrome/Edge also lock Alt+Tab, the Windows key and Esc (hold Esc to leave) via the Keyboard Lock API;
 * - leaving full screen, switching tab/app, clicking outside or opening a second tab are reported as strikes;
 * - copy, paste, right-click, developer tools, printing, saving, reloading and other shortcuts are blocked and logged.
 * The server decides when the strike limit is reached and ends the interview.
 *
 * A web page cannot see other devices (e.g. a phone) or fully stop a determined user from leaving, so the
 * recruiter also gets the full log.
 */
export function useLockdown(sessionId: string, questionIndex: number, onResult: (r: EventsResult) => void) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [active, setActive] = useState(false);
  const [inFullscreen, setInFullscreen] = useState(false);
  const queue = useRef<{ type: IntegrityEventType; question_index: number; detail?: string; value?: number }[]>([]);
  const flushing = useRef(false);
  const timer = useRef<number | null>(null);
  const qIndex = useRef(questionIndex);
  const onResultRef = useRef(onResult);
  const lastStrikeAt = useRef(0);
  const ignoreBlurUntil = useRef(0);
  qIndex.current = questionIndex;
  onResultRef.current = onResult;

  const flush = useCallback(async () => {
    if (flushing.current || queue.current.length === 0) return;
    flushing.current = true;
    const batch = queue.current.splice(0, 20);
    try {
      onResultRef.current(await interviewsApi.events(sessionId, batch));
    } catch {
      queue.current.unshift(...batch); // offline for a moment: try again with the next event
    } finally {
      flushing.current = false;
      if (queue.current.length) timer.current = window.setTimeout(flush, 1500);
    }
  }, [sessionId]);

  const report = useCallback(
    (type: IntegrityEventType, detail?: string, value?: number) => {
      const strike = STRIKES.includes(type);
      if (strike) {
        const now = Date.now();
        if (now - lastStrikeAt.current < 3000) return; // one exit fires several browser events
        lastStrikeAt.current = now;
      }
      queue.current.push({ type, question_index: qIndex.current, detail, value });
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(flush, strike ? 0 : 800);
    },
    [flush],
  );

  const enterFullscreen = useCallback(async () => {
    const el = containerRef.current;
    if (!el?.requestFullscreen) return false;
    ignoreBlurUntil.current = Date.now() + 1500;
    try {
      await el.requestFullscreen({ navigationUI: "hide" });
    } catch {
      return false;
    }
    // Not awaited: the lock can take a moment and the interview should appear at once.
    const kb = (navigator as Navigator & { keyboard?: KeyboardLock }).keyboard;
    if (kb?.lock) kb.lock().catch(() => report("keyboard_lock_unavailable"));
    else report("keyboard_lock_unavailable");
    return true;
  }, [report]);

  const release = useCallback(() => {
    setActive(false);
    (navigator as Navigator & { keyboard?: KeyboardLock }).keyboard?.unlock?.();
    if (document.fullscreenElement) document.exitFullscreen().catch(() => undefined);
  }, []);

  useEffect(() => {
    const onFs = () => {
      const fs = Boolean(document.fullscreenElement);
      setInFullscreen(fs);
      if (!fs && active) report("fullscreen_exit");
    };
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, [active, report]);

  useEffect(() => {
    if (!active) return;
    const block = (type: IntegrityEventType) => (e: Event) => {
      e.preventDefault();
      report(type);
    };
    const onCopy = block("copy_attempt");
    const onPaste = block("paste_attempt");
    const onMenu = block("context_menu");
    const onVisibility = () => document.hidden && report("tab_hidden");
    const onBlur = () => {
      if (Date.now() < ignoreBlurUntil.current) return;
      report("window_blur");
    };
    const onKey = (e: KeyboardEvent) => {
      if (DEVTOOLS_KEYS(e)) {
        e.preventDefault();
        report("devtools_key", e.key);
        return;
      }
      if (e.key === "PrintScreen") {
        report("screenshot_key");
        return;
      }
      const combo = (e.ctrlKey || e.metaKey) && BLOCKED_COMBOS.has(e.key.toLowerCase());
      const fnKey = ["F1", "F3", "F5", "F6", "F7", "F11"].includes(e.key);
      const nav = e.altKey && ["ArrowLeft", "ArrowRight", "Home", "Tab", "F4"].includes(e.key);
      if (combo || fnKey || nav || e.key === "ContextMenu" || e.key === "Meta" || e.key === "OS") {
        e.preventDefault();
        report("blocked_key", `${e.ctrlKey ? "Ctrl+" : ""}${e.metaKey ? "Cmd+" : ""}${e.altKey ? "Alt+" : ""}${e.key}`);
      }
    };
    const onUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    const onDrop = (e: DragEvent) => {
      e.preventDefault();
      report("paste_attempt", "drag and drop");
    };
    const onDragOver = (e: DragEvent) => e.preventDefault();
    const screenObj = window.screen as unknown as Partial<EventTarget>;
    const onScreenChange = () => hasSecondScreen() && report("second_screen");

    document.addEventListener("copy", onCopy);
    document.addEventListener("cut", onCopy);
    document.addEventListener("paste", onPaste);
    document.addEventListener("contextmenu", onMenu);
    document.addEventListener("visibilitychange", onVisibility);
    document.addEventListener("dragover", onDragOver);
    document.addEventListener("drop", onDrop);
    window.addEventListener("blur", onBlur);
    window.addEventListener("keydown", onKey, true);
    window.addEventListener("beforeunload", onUnload);
    screenObj.addEventListener?.("change", onScreenChange);
    return () => {
      document.removeEventListener("copy", onCopy);
      document.removeEventListener("cut", onCopy);
      document.removeEventListener("paste", onPaste);
      document.removeEventListener("contextmenu", onMenu);
      document.removeEventListener("visibilitychange", onVisibility);
      document.removeEventListener("dragover", onDragOver);
      document.removeEventListener("drop", onDrop);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("keydown", onKey, true);
      window.removeEventListener("beforeunload", onUnload);
      screenObj.removeEventListener?.("change", onScreenChange);
    };
  }, [active, report]);

  // Only one tab may run the interview. A second tab finds out, refuses to start, and the first tab reports it.
  const [otherTab, setOtherTab] = useState(false);
  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    const ch = new BroadcastChannel(`interview-${sessionId}`);
    ch.onmessage = (m) => {
      if (m.data === "hello" && active) {
        ch.postMessage("busy");
        report("multiple_tabs");
      }
      if (m.data === "busy") setOtherTab(true);
    };
    ch.postMessage("hello");
    return () => ch.close();
  }, [sessionId, active, report]);

  useEffect(() => () => {
    if (timer.current) window.clearTimeout(timer.current);
  }, []);

  return { containerRef, active, setActive, inFullscreen, enterFullscreen, release, report, otherTab, flush };
}
