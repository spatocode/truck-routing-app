import { useEffect, useRef, useState } from "react";
import { searchPlaces } from "./api";
import type { Place } from "./types";

interface Props {
  label: string;
  value: string;
  onChange: (value: string, place?: Place) => void;
}

export default function PlaceField({ label, value, onChange }: Props) {
  const [matches, setMatches] = useState<Place[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [touched, setTouched] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!touched) return;
    window.clearTimeout(timer.current);
    if (value.trim().length < 2) {
      setMatches([]);
      setOpen(false);
      return;
    }
    timer.current = window.setTimeout(async () => {
      try {
        const results = await searchPlaces(value);
        setMatches(results);
        setOpen(results.length > 0);
        setActive(0);
      } catch {
        setMatches([]);
      }
    }, 220);
    return () => window.clearTimeout(timer.current);
  }, [value, touched]);

  return (
    <label className="suggest">
      {label}
      <input
        value={value}
        autoComplete="off"
        onChange={(event) => {
          setTouched(true);
          onChange(event.target.value);
        }}
        onFocus={() => {
          setTouched(true);
          setOpen(matches.length > 0);
        }}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onKeyDown={(event) => {
          if (!open || matches.length === 0) return;
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setActive((index) => (index + 1) % matches.length);
          }
          if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive((index) => (index - 1 + matches.length) % matches.length);
          }
          if (event.key === "Enter") {
            event.preventDefault();
            onChange(matches[active].label, matches[active]);
            setOpen(false);
          }
          if (event.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {open && (
        <div className="suggest-list">
          {matches.map((place, index) => (
            <button
              type="button"
              key={`${place.label}-${place.lat}`}
              className={index === active ? "active" : ""}
              onMouseDown={(event) => {
                event.preventDefault();
                onChange(place.label, place);
                setOpen(false);
              }}
            >
              {place.label}
            </button>
          ))}
        </div>
      )}
    </label>
  );
}
