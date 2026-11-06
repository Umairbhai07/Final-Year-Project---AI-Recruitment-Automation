import { useEffect, useRef } from "react";

/**
 * <audio> that also works for recordings saved without a duration (older WebM files from Chrome):
 * it seeks to the end once so the browser works out the real length, then jumps back to the start.
 */
export function AudioPlayer({ src, autoPlay, className }: { src: string; autoPlay?: boolean; className?: string }) {
  const ref = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    const a = ref.current;
    if (!a) return;
    const onMeta = () => {
      if (a.duration !== Infinity && !Number.isNaN(a.duration)) {
        if (autoPlay) a.play().catch(() => {});
        return;
      }
      const onTime = () => {
        a.removeEventListener("timeupdate", onTime);
        a.currentTime = 0;
        if (autoPlay) a.play().catch(() => {});
      };
      a.addEventListener("timeupdate", onTime);
      a.currentTime = 1e101;
    };
    a.addEventListener("loadedmetadata", onMeta);
    return () => a.removeEventListener("loadedmetadata", onMeta);
  }, [src, autoPlay]);
  return <audio ref={ref} src={src} controls preload="metadata" className={className} />;
}
