import { useCallback, useEffect, useRef } from "react";

export const speechSupported = () => typeof window !== "undefined" && "speechSynthesis" in window;

// Clear, well-known voices first: Edge's natural voices, Chrome's Google voices, then Windows and macOS ones.
const PREFERRED = [/aria.*natural/i, /jenny.*natural/i, /guy.*natural/i, /natural/i, /google us english/i,
  /google uk english female/i, /google/i, /zira/i, /samantha/i, /david/i, /daniel/i];

function pickVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("en"));
  const rank = (v: SpeechSynthesisVoice) => {
    const i = PREFERRED.findIndex((re) => re.test(v.name));
    return (i === -1 ? PREFERRED.length : i) - (/en[-_](us|gb)/i.test(v.lang) ? 0.5 : 0);
  };
  return [...voices].sort((a, b) => rank(a) - rank(b))[0] ?? null;
}

/** Slow enough to follow for people who speak English as a second language. */
const RATE = 0.85;
const SLOWER_RATE = 0.72;
const PAUSE_MS = 350;

/** Ask the browser to load its voices early, so the first question is not delayed. */
export function warmUpVoices() {
  if (speechSupported()) window.speechSynthesis.getVoices();
}

async function voicesReady(): Promise<void> {
  if (window.speechSynthesis.getVoices().length) return;
  await new Promise<void>((resolve) => {
    const done = () => resolve();
    window.speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    window.setTimeout(done, 1200);
  });
}

/**
 * Reads interview questions aloud with the browser's built-in voice (free, no API key).
 * The question is split into sentences because Chrome cuts off long utterances, and every sentence has a
 * safety timeout so a browser that never fires "end" cannot freeze the interview.
 */
export function useSpeech() {
  const cancelled = useRef(false);

  const cancel = useCallback(() => {
    cancelled.current = true;
    if (speechSupported()) window.speechSynthesis.cancel();
  }, []);

  const speak = useCallback(async (text: string, opts?: { slower?: boolean }) => {
    if (!speechSupported()) return false;
    cancelled.current = false;
    window.speechSynthesis.cancel();
    await voicesReady();
    const voice = pickVoice();
    const rate = opts?.slower ? SLOWER_RATE : RATE;
    const sentences = text.match(/[^.!?]+[.!?]*/g)?.map((s) => s.trim()).filter(Boolean) ?? [text];
    for (const [i, sentence] of sentences.entries()) {
      if (cancelled.current) return true;
      if (i > 0) await new Promise((r) => window.setTimeout(r, PAUSE_MS));
      await new Promise<void>((resolve) => {
        const u = new SpeechSynthesisUtterance(sentence);
        if (voice) u.voice = voice;
        u.lang = voice?.lang ?? "en-US";
        u.rate = rate;
        u.volume = 1;
        u.pitch = 1;
        const words = sentence.split(/\s+/).length;
        const safety = window.setTimeout(resolve, (words / (2 * rate) + 3) * 1000);
        u.onend = u.onerror = () => {
          window.clearTimeout(safety);
          resolve();
        };
        window.speechSynthesis.speak(u);
      });
    }
    return true;
  }, []);

  useEffect(() => {
    warmUpVoices();
    return cancel;
  }, [cancel]);
  return { speak, cancel, supported: speechSupported() };
}
