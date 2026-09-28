import { useEffect, useRef, useState } from "react";
import { advanceTime } from "./playback";

export function usePlayback(duration: number, visible: boolean) {
  const [time, setTime] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(5);
  const [motion, setMotion] = useState(0);
  const [reduceMotion, setReduceMotion] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const clock = useRef({ time: 0, motion: 0 });
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduceMotion(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (!visible) setPlaying(false);
  }, [visible]);
  useEffect(() => {
    if (!playing || !visible || duration <= 0) return;
    let handle = 0;
    let previous = performance.now();
    const pauseHidden = () => {
      if (document.hidden) setPlaying(false);
    };
    document.addEventListener("visibilitychange", pauseHidden);
    const tick = (now: number) => {
      // Background tabs pause replay instead of skipping to the end on return.
      if (document.hidden) {
        previous = now;
        handle = requestAnimationFrame(tick);
        return;
      }
      const elapsed = (now - previous) / 1000;
      if (elapsed >= 1 / 30) {
        previous = now;
        clock.current.time = advanceTime(
          clock.current.time,
          elapsed,
          speed,
          duration,
        );
        clock.current.motion += elapsed;
        setTime(clock.current.time);
        setMotion(clock.current.motion);
        if (clock.current.time >= duration) {
          setPlaying(false);
          return;
        }
      }
      handle = requestAnimationFrame(tick);
    };
    handle = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(handle);
      document.removeEventListener("visibilitychange", pauseHidden);
    };
  }, [playing, speed, duration, visible]);

  function seek(next: number) {
    const bounded = Math.max(0, Math.min(duration, next));
    clock.current.time = bounded;
    setTime(bounded);
    setPlaying(false);
  }
  function reset() {
    clock.current = { time: 0, motion: 0 };
    setTime(null);
    setMotion(0);
    setPlaying(false);
  }
  function start(nextSpeed = speed) {
    clock.current = { time: 0, motion: 0 };
    setTime(0);
    setMotion(0);
    setSpeed(nextSpeed);
    setPlaying(true);
  }
  function toggle() {
    if (playing) setPlaying(false);
    else if (time === null || time >= duration) start();
    else setPlaying(duration > 0);
  }
  return {
    time,
    playing,
    speed,
    motion: reduceMotion ? 0 : motion,
    reduceMotion,
    setSpeed,
    seek,
    reset,
    start,
    toggle,
    pause: () => setPlaying(false),
  };
}
