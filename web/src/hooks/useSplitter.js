import { useEffect, useRef, useState } from "preact/hooks";

export function useSplitter() {
  const [width, setWidth] = useState(380);
  const drag = useRef(null);

  useEffect(() => {
    const splitter = document.getElementById("splitter");
    if (!splitter) return;
    const onDown = (e) => {
      drag.current = { startX: e.clientX, startW: width };
      splitter.classList.add("splitter--active");
      document.body.style.cursor = "ew-resize";
      document.body.style.userSelect = "none";
      e.preventDefault();
    };
    const onMove = (e) => {
      if (!drag.current) return;
      const next = drag.current.startW + (e.clientX - drag.current.startX);
      setWidth(Math.max(260, Math.min(window.innerWidth - 360, next)));
    };
    const onUp = () => {
      if (!drag.current) return;
      drag.current = null;
      splitter.classList.remove("splitter--active");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    splitter.addEventListener("mousedown", onDown);
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      splitter.removeEventListener("mousedown", onDown);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [width]);

  return width;
}
