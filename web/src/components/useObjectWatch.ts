import type { ObjectDetector } from "@mediapipe/tasks-vision";
import { useEffect, useRef, useState } from "react";

/**
 * Looks for things that should not be in the interview: a mobile phone, a book or notes, another screen, or a
 * second person. Runs in the browser with MediaPipe Object Detector (EfficientDet-Lite0, trained on the 80 COCO
 * objects, about 4.5 MB). No video leaves the device.
 *
 * One check (the whole picture plus its two halves) runs about every 0.7 seconds. An object is only reported after it is seen in most of the last few
 * checks, so a single wrong guess does not count. Once reported, the same object is not reported again until it
 * has been gone for a few checks.
 */

export type ObjectKind = "phone" | "book" | "screen" | "person";

const MODEL_URL = "/mediapipe/efficientdet_lite0.tflite";
const WASM_URL = "/mediapipe/wasm";
const INTERVAL_MS = 700;

// COCO names -> what we report, the score needed, and how many of the last checks must see it.
const RULES: Record<ObjectKind, { names: string[]; score: number; need: number; of: number }> = {
  phone: { names: ["cell phone"], score: 0.4, need: 2, of: 3 },
  book: { names: ["book"], score: 0.45, need: 3, of: 4 },
  screen: { names: ["laptop", "tv"], score: 0.5, need: 3, of: 4 },
  person: { names: ["person"], score: 0.5, need: 2, of: 3 }, // counted: two or more people
};
const HALVES: [number, number][] = [[0, 0.6], [0.4, 1]]; // overlapping, so an object in the middle is not cut
const GONE_AFTER = 3; // checks without the object before it can be reported again

let detectorPromise: Promise<ObjectDetector> | null = null;

/** Loads the detector once per page. Call early (on the setup screen) so it is ready when the interview starts. */
export function loadObjectDetector(): Promise<ObjectDetector> {
  if (!detectorPromise) {
    detectorPromise = (async () => {
      const { ObjectDetector, FilesetResolver } = await import("@mediapipe/tasks-vision");
      const fileset = await FilesetResolver.forVisionTasks(WASM_URL);
      // CPU on purpose: the GPU delegate returned wrong boxes in testing, and one small check every 0.7 s is cheap.
      return ObjectDetector.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
        runningMode: "VIDEO",
        maxResults: 6,
        scoreThreshold: 0.25,
        categoryAllowlist: ["cell phone", "book", "laptop", "tv", "person"],
      });
    })();
    detectorPromise.catch(() => {
      detectorPromise = null;
    });
  }
  return detectorPromise;
}

type Detection = { categories: { categoryName: string; score: number }[] };

/**
 * What one check saw, before the "seen in most recent checks" rule. `full` is the whole picture; `parts` are the
 * left and right halves looked at separately, which finds small things such as a phone in a hand much better.
 * People are only counted in the whole picture, so one person in both halves is not counted twice.
 */
export function seenIn(full: Detection[], parts: Detection[][] = []): Record<ObjectKind, boolean> {
  const count = (list: Detection[], k: ObjectKind) =>
    list.filter((d) => d.categories.some((c) => RULES[k].names.includes(c.categoryName) && c.score >= RULES[k].score)).length;
  const anywhere = (k: ObjectKind) => count(full, k) > 0 || parts.some((p) => count(p, k) > 0);
  return {
    phone: anywhere("phone"),
    book: anywhere("book"),
    screen: count(full, "screen") > 0,
    person: count(full, "person") >= 2,
  };
}

/** Keeps the last few checks per object and decides when to report. Pure, so it can be tested. */
export class ObjectEpisodes {
  private history: Record<ObjectKind, boolean[]> = { phone: [], book: [], screen: [], person: [] };
  private active: Record<ObjectKind, boolean> = { phone: false, book: false, screen: false, person: false };
  private missing: Record<ObjectKind, number> = { phone: 0, book: 0, screen: 0, person: 0 };

  /** Returns the objects that just became "really there" (report these) and the ones visible now. */
  push(seen: Record<ObjectKind, boolean>): { started: ObjectKind[]; visible: ObjectKind[] } {
    const started: ObjectKind[] = [];
    const visible: ObjectKind[] = [];
    for (const k of Object.keys(RULES) as ObjectKind[]) {
      const r = RULES[k];
      const h = this.history[k];
      h.push(seen[k]);
      if (h.length > r.of) h.shift();
      const hits = h.filter(Boolean).length;
      if (seen[k]) this.missing[k] = 0;
      else this.missing[k] += 1;
      if (!this.active[k] && hits >= r.need) {
        this.active[k] = true;
        started.push(k);
      } else if (this.active[k] && this.missing[k] >= GONE_AFTER) {
        this.active[k] = false;
      }
      if (this.active[k] && seen[k]) visible.push(k);
    }
    return { started, visible };
  }
}

/**
 * Watches the camera stream while `enabled`. Calls `onFound` once per sighting episode.
 * `visible` is what is in view right now, for the on-screen warning.
 */
export function useObjectWatch(stream: MediaStream | null, enabled: boolean, onFound: (kind: ObjectKind) => void, onUnavailable?: () => void) {
  const [visible, setVisible] = useState<ObjectKind[]>([]);
  const onFoundRef = useRef(onFound);
  const onUnavailableRef = useRef(onUnavailable);
  onFoundRef.current = onFound;
  onUnavailableRef.current = onUnavailable;

  useEffect(() => {
    if (!stream || !enabled) {
      setVisible([]);
      return;
    }
    let stopped = false;
    let timer = 0;
    const episodes = new ObjectEpisodes();
    const canvas = document.createElement("canvas");
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    (async () => {
      try {
        await video.play();
        const detector = await loadObjectDetector();
        if (stopped) return;
        let lastTs = 0;
        const tick = () => {
          if (stopped) return;
          if (video.readyState >= 2 && video.videoWidth > 0) {
            const ts = Math.max(performance.now(), lastTs + 1);
            const full = detector.detectForVideo(video, ts).detections;
            const parts = HALVES.map(([x0, x1], i) => {
              const w = Math.round(video.videoWidth * (x1 - x0));
              canvas.width = w;
              canvas.height = video.videoHeight;
              canvas.getContext("2d")!.drawImage(video, video.videoWidth * x0, 0, w, video.videoHeight, 0, 0, w, video.videoHeight);
              return detector.detectForVideo(canvas, ts + i + 1).detections;
            });
            lastTs = ts + HALVES.length;
            const { started, visible: now } = episodes.push(seenIn(full, parts));
            setVisible((v) => (v.join() === now.join() ? v : now));
            started.forEach((k) => onFoundRef.current(k));
          }
          timer = window.setTimeout(tick, INTERVAL_MS);
        };
        tick();
      } catch {
        if (!stopped) onUnavailableRef.current?.();
      }
    })();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      video.srcObject = null;
    };
  }, [stream, enabled]);

  return { visible };
}
