// Full-screen Matrix "digital rain" celebration — fired when a todo is completed.
// A fixed, viewport-covering <canvas> renders falling katakana/digit columns in
// phosphor green; a glowing "COMPLETE" badge pops in the center. The whole overlay
// fades in and out over DURATION_MS via the .matrix-rain envelope keyframe, then the
// component unmounts. No library — one requestAnimationFrame loop.
import { useRef, useEffect, useState } from "preact/hooks";

const GLYPHS = "アカサタナハマヤラワ0123456789ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｸ".split("");
const FONT_SIZE = 16; // CSS px per column/row cell
const DURATION_MS = 2600; // total celebration length (must match the CSS envelope)

export function Confetti({ trigger }) {
  const canvasRef = useRef(null);
  // runId holds the trigger value currently animating (0 = idle). Splitting it from
  // `trigger` lets the overlay mount first, so the canvas ref exists when we animate.
  const [runId, setRunId] = useState(0);

  useEffect(() => {
    if (trigger) setRunId(trigger);
  }, [trigger]);

  useEffect(() => {
    if (!runId) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;

    let width = 0;
    let height = 0;
    let drops = [];

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); // draw in CSS pixels
      const cols = Math.ceil(width / FONT_SIZE);
      // Stagger each column's start above the top so the rain cascades in.
      drops = Array.from({ length: cols }, () => Math.floor(Math.random() * -40));
    }
    resize();
    window.addEventListener("resize", resize);

    ctx.font = `${FONT_SIZE}px "SFMono-Regular", "Menlo", monospace`;
    ctx.textBaseline = "top";
    ctx.shadowColor = "rgba(95, 194, 133, 0.9)";
    ctx.shadowBlur = 8;

    let raf = 0;
    function frame() {
      // Translucent black wash fades prior glyphs toward black — the classic green
      // trail (a green char darkens frame by frame as the head moves on).
      ctx.shadowBlur = 0;
      ctx.fillStyle = "rgba(0, 0, 0, 0.12)";
      ctx.fillRect(0, 0, width, height);

      ctx.shadowBlur = 8;
      for (let i = 0; i < drops.length; i++) {
        const x = i * FONT_SIZE;
        const y = drops[i] * FONT_SIZE;
        const glyph = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
        // Occasional near-white head for that bright leading-edge sparkle.
        ctx.fillStyle = Math.random() > 0.92 ? "#d6ffe4" : "rgba(95, 194, 133, 0.92)";
        ctx.fillText(glyph, x, y);
        drops[i]++;
        // Once a column falls off-screen, randomly recycle it back to the top.
        if (y > height && Math.random() > 0.972) drops[i] = Math.floor(Math.random() * -20);
      }
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);

    const end = setTimeout(() => setRunId(0), DURATION_MS);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(end);
      window.removeEventListener("resize", resize);
    };
  }, [runId]);

  if (!runId) return null;

  return (
    <div class="matrix-rain" aria-hidden="true">
      <canvas ref={canvasRef} class="matrix-rain-canvas" />
      <div class="matrix-rain-badge">
        <svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
        <span>COMPLETE</span>
      </div>
    </div>
  );
}
