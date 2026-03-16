import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const PHASES = [
  { threshold: 0, label: 'Initializing Monte Carlo engine...' },
  { threshold: 5000, label: 'Loading KenPom efficiency ratings...' },
  { threshold: 10000, label: 'Calibrating upset probability model...' },
  { threshold: 18000, label: 'Running XGBoost predictions...' },
  { threshold: 25000, label: 'Simulating bracket outcomes...' },
  { threshold: 35000, label: 'Computing pool equity scores...' },
  { threshold: 42000, label: 'Analyzing chalk vs contrarian value...' },
  { threshold: 47000, label: 'Aggregating results...' },
  { threshold: 49000, label: 'Finalizing recommendations...' },
];

function useCountUp(target, durationMs) {
  const [count, setCount] = useState(0);
  const startTime = useRef(null);
  const frameRef = useRef(null);

  useEffect(() => {
    startTime.current = null;
    setCount(0);

    const animate = (ts) => {
      if (!startTime.current) startTime.current = ts;
      const elapsed = ts - startTime.current;
      const progress = Math.min(elapsed / durationMs, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(eased * target));
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };

    frameRef.current = requestAnimationFrame(animate);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [target, durationMs]);

  return count;
}

export default function SimLoading() {
  const count = useCountUp(50000, 4200);
  const [phaseIndex, setPhaseIndex] = useState(0);

  useEffect(() => {
    let idx = 0;
    for (let i = PHASES.length - 1; i >= 0; i--) {
      if (count >= PHASES[i].threshold) {
        idx = i;
        break;
      }
    }
    setPhaseIndex(idx);
  }, [count]);

  const pct = count / 50000;
  const barWidth = `${Math.round(pct * 100)}%`;

  return (
    <motion.section
      className="min-h-screen flex flex-col items-center justify-center px-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4 }}
      style={{ backgroundColor: '#0a0e1a' }}
    >
      {/* Grid overlay */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(rgba(245,166,35,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(245,166,35,0.02) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative z-10 w-full max-w-xl text-center">
        {/* Pulse ring */}
        <div className="relative flex items-center justify-center mb-12">
          <motion.div
            className="absolute rounded-full"
            style={{
              width: 140,
              height: 140,
              border: '1px solid rgba(245,166,35,0.3)',
            }}
            animate={{ scale: [1, 1.15, 1], opacity: [0.6, 0.1, 0.6] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          />
          <motion.div
            className="absolute rounded-full"
            style={{
              width: 110,
              height: 110,
              border: '1px solid rgba(245,166,35,0.5)',
            }}
            animate={{ scale: [1, 1.1, 1], opacity: [0.8, 0.2, 0.8] }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: 'easeInOut',
              delay: 0.3,
            }}
          />
          <div
            className="relative flex flex-col items-center justify-center rounded-full"
            style={{
              width: 90,
              height: 90,
              backgroundColor: 'rgba(245,166,35,0.1)',
              border: '2px solid rgba(245,166,35,0.4)',
            }}
          >
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
              <motion.path
                d="M18 4 L18 18 L28 28"
                stroke="#f5a623"
                strokeWidth="2.5"
                strokeLinecap="round"
                animate={{ opacity: [1, 0.4, 1] }}
                transition={{ duration: 1.2, repeat: Infinity }}
              />
              <circle
                cx="18"
                cy="18"
                r="14"
                stroke="rgba(245,166,35,0.2)"
                strokeWidth="1.5"
              />
            </svg>
          </div>
        </div>

        {/* Counter */}
        <div className="mb-2">
          <motion.span
            className="font-mono font-black tabular-nums"
            style={{
              fontSize: 'clamp(3rem, 10vw, 5.5rem)',
              color: '#f5a623',
              textShadow: '0 0 40px rgba(245,166,35,0.5)',
            }}
          >
            {count.toLocaleString()}
          </motion.span>
        </div>
        <p className="font-mono text-sm tracking-[0.3em] text-slate-400 uppercase mb-10">
          simulations complete
        </p>

        {/* Phase label */}
        <div className="h-6 mb-8 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.p
              key={phaseIndex}
              className="font-mono text-sm text-slate-400"
              initial={{ y: 12, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -12, opacity: 0 }}
              transition={{ duration: 0.25 }}
            >
              {PHASES[phaseIndex].label}
            </motion.p>
          </AnimatePresence>
        </div>

        {/* Progress bar container */}
        <div
          className="relative w-full rounded-full overflow-hidden"
          style={{
            height: 6,
            backgroundColor: 'rgba(255,255,255,0.06)',
          }}
        >
          <motion.div
            className="absolute left-0 top-0 h-full rounded-full"
            style={{
              width: barWidth,
              background:
                'linear-gradient(90deg, rgba(245,166,35,0.7) 0%, #f5a623 100%)',
              boxShadow: '0 0 12px rgba(245,166,35,0.7)',
            }}
            transition={{ duration: 0.1, ease: 'linear' }}
          />
          {/* Shimmer */}
          <motion.div
            className="absolute top-0 h-full w-16 rounded-full"
            style={{
              background:
                'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
              left: `calc(${barWidth} - 4rem)`,
            }}
            animate={{ opacity: [0, 1, 0] }}
            transition={{ duration: 0.8, repeat: Infinity, ease: 'easeInOut' }}
          />
        </div>

        <p className="font-mono text-xs text-slate-600 mt-4 tracking-widest">
          {Math.round(pct * 100)}% — TARGET: 50,000
        </p>

        {/* Data stream dots */}
        <div className="flex justify-center gap-1.5 mt-10">
          {Array.from({ length: 8 }, (_, i) => (
            <motion.div
              key={i}
              className="rounded-full"
              style={{
                width: 4,
                height: 4,
                backgroundColor: '#f5a623',
              }}
              animate={{ opacity: [0.1, 0.9, 0.1] }}
              transition={{
                duration: 1.2,
                repeat: Infinity,
                delay: i * 0.15,
              }}
            />
          ))}
        </div>
      </div>
    </motion.section>
  );
}
