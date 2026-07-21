import { useEffect, useRef, useState } from 'react';

interface SignaturePadProps {
  /** Existing signature data URL, if the party has already signed. */
  value: string;
  /** Called with a PNG data URL when a signature is drawn, or '' when cleared. */
  onChange: (dataUrl: string) => void;
  label: string;
}

/**
 * A dependency-free digital signature pad. The user draws with a mouse, finger,
 * or stylus on an HTML canvas; the stroke is exported as a PNG data URL so it
 * can be stored with the contract and rendered into the PDF export.
 */
export function SignaturePad({ value, onChange, label }: SignaturePadProps): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawing = useRef(false);
  const lastPoint = useRef<{ x: number; y: number } | null>(null);
  const [hasDrawn, setHasDrawn] = useState(Boolean(value));

  // Render an already-saved signature onto the canvas when the pad mounts.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#0f172a';
    if (value) {
      const img = new Image();
      img.onload = () => ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      img.src = value;
      setHasDrawn(true);
    }
    // Only run on mount / when an external value is (re)applied.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pointFor(event: React.PointerEvent<HTMLCanvasElement>): { x: number; y: number } {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * canvas.width,
      y: ((event.clientY - rect.top) / rect.height) * canvas.height,
    };
  }

  function startDraw(event: React.PointerEvent<HTMLCanvasElement>): void {
    event.preventDefault();
    canvasRef.current?.setPointerCapture(event.pointerId);
    drawing.current = true;
    lastPoint.current = pointFor(event);
  }

  function draw(event: React.PointerEvent<HTMLCanvasElement>): void {
    if (!drawing.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx || !lastPoint.current) return;
    const point = pointFor(event);
    ctx.beginPath();
    ctx.moveTo(lastPoint.current.x, lastPoint.current.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
    lastPoint.current = point;
    if (!hasDrawn) setHasDrawn(true);
  }

  function endDraw(event: React.PointerEvent<HTMLCanvasElement>): void {
    if (!drawing.current) return;
    drawing.current = false;
    lastPoint.current = null;
    const canvas = canvasRef.current;
    if (canvas && hasDrawn) onChange(canvas.toDataURL('image/png'));
  }

  function clear(): void {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawn(false);
    onChange('');
  }

  return (
    <div className='signature-pad'>
      <div className='signature-pad-head'>
        <span className='muted'>{label}</span>
        <button type='button' onClick={clear} disabled={!hasDrawn}>
          Clear
        </button>
      </div>
      <canvas
        ref={canvasRef}
        width={480}
        height={140}
        className='signature-pad-canvas'
        onPointerDown={startDraw}
        onPointerMove={draw}
        onPointerUp={endDraw}
        onPointerLeave={endDraw}
      />
      <p className='muted signature-pad-hint'>Draw your signature above.</p>
    </div>
  );
}
