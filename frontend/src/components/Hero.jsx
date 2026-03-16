import { useState } from 'react';

const RISK_LABELS = {
  0.0: 'PURE CHALK',
  0.1: 'VERY SAFE',
  0.2: 'CONSERVATIVE',
  0.3: 'MODERATE–',
  0.4: 'MODERATE',
  0.5: 'BALANCED',
  0.6: 'AGGRESSIVE',
  0.7: 'HIGH RISK',
  0.8: 'VERY HIGH',
  0.9: 'EXTREME',
  1.0: 'MAX CHAOS',
};

export default function Hero({ onRunSimulation, loading }) {
  const [risk, setRisk] = useState(0.5);
  const [poolSize, setPoolSize] = useState(1000000);
  const [poolSizeRaw, setPoolSizeRaw] = useState('1000000');

  const handlePoolSizeChange = (e) => {
    const raw = e.target.value.replace(/[^0-9]/g, '');
    setPoolSizeRaw(raw);
    const parsed = parseInt(raw, 10);
    if (!isNaN(parsed) && parsed > 0) {
      setPoolSize(parsed);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (loading) return;
    onRunSimulation({ risk, pool_size: poolSize, year: 2026 });
  };

  const riskLabel = RISK_LABELS[parseFloat(risk.toFixed(1))] ?? 'BALANCED';
  const riskPercent = Math.round(risk * 100);

  return (
    <section className="min-h-screen flex flex-col items-center justify-center px-6 py-20 relative overflow-hidden">
      {/* Background grid overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(rgba(245,166,35,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(245,166,35,0.03) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      {/* Glow blob */}
      <div
        className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full pointer-events-none"
        style={{
          background:
            'radial-gradient(circle, rgba(245,166,35,0.06) 0%, transparent 70%)',
        }}
      />

      <div className="relative z-10 w-full max-w-2xl">
        {/* Year badge */}
        <div className="flex justify-center mb-6">
          <span
            className="font-mono text-xs tracking-[0.3em] px-4 py-1.5 rounded-full border"
            style={{
              color: '#f5a623',
              borderColor: 'rgba(245,166,35,0.3)',
              backgroundColor: 'rgba(245,166,35,0.06)',
            }}
          >
            2026 TOURNAMENT — AI ANALYSIS ENGINE
          </span>
        </div>

        {/* Main title */}
        <h1
          className="text-center font-mono font-black leading-none tracking-tight mb-3"
          style={{ fontSize: 'clamp(2.4rem, 7vw, 4.5rem)', color: '#ffffff' }}
        >
          MARCH MADNESS
        </h1>
        <h2
          className="text-center font-mono font-black leading-none tracking-tight mb-10"
          style={{
            fontSize: 'clamp(1.6rem, 5vw, 3rem)',
            color: '#f5a623',
            textShadow: '0 0 40px rgba(245,166,35,0.4)',
          }}
        >
          AI BRACKET PREDICTOR
        </h2>

        {/* Stats row */}
        <div
          className="grid grid-cols-3 gap-px mb-10 rounded-lg overflow-hidden"
          style={{ backgroundColor: 'rgba(245,166,35,0.1)' }}
        >
          {[
            { label: 'SIMULATIONS', value: '50,000' },
            { label: 'ML MODEL', value: 'XGBoost' },
            { label: 'DATA POINTS', value: '20+ YRS' },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="flex flex-col items-center py-4"
              style={{ backgroundColor: '#0f1629' }}
            >
              <span
                className="font-mono font-bold text-lg"
                style={{ color: '#f5a623' }}
              >
                {value}
              </span>
              <span className="font-mono text-xs tracking-widest text-slate-500 mt-1">
                {label}
              </span>
            </div>
          ))}
        </div>

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="rounded-xl p-8 space-y-8"
          style={{
            backgroundColor: '#151d38',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          {/* Risk slider */}
          <div>
            <div className="flex justify-between items-baseline mb-3">
              <label className="font-mono text-sm tracking-widest text-slate-400 uppercase">
                Upset Risk Tolerance
              </label>
              <div className="flex items-center gap-3">
                <span
                  className="font-mono text-xs px-2 py-0.5 rounded"
                  style={{
                    color: '#f5a623',
                    backgroundColor: 'rgba(245,166,35,0.12)',
                  }}
                >
                  {riskLabel}
                </span>
                <span className="font-mono font-bold text-white">
                  {riskPercent}%
                </span>
              </div>
            </div>

            {/* Tick marks */}
            <div className="relative mb-1">
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={risk}
                onChange={(e) => setRisk(parseFloat(e.target.value))}
                className="w-full h-2 rounded-full appearance-none cursor-pointer"
                style={{
                  background: `linear-gradient(to right, #f5a623 0%, #f5a623 ${riskPercent}%, #253258 ${riskPercent}%, #253258 100%)`,
                  outline: 'none',
                }}
              />
            </div>
            <div className="flex justify-between mt-1">
              <span className="font-mono text-xs text-slate-600">0</span>
              <span className="font-mono text-xs text-slate-600">0.5</span>
              <span className="font-mono text-xs text-slate-600">1.0</span>
            </div>
          </div>

          {/* Pool size */}
          <div>
            <label className="font-mono text-sm tracking-widest text-slate-400 uppercase block mb-3">
              Pool Size (participants)
            </label>
            <div className="relative">
              <span
                className="absolute left-4 top-1/2 -translate-y-1/2 font-mono text-slate-500 text-sm select-none"
              >
                #
              </span>
              <input
                type="text"
                inputMode="numeric"
                value={poolSizeRaw}
                onChange={handlePoolSizeChange}
                className="w-full rounded-lg pl-8 pr-4 py-3 font-mono text-white text-sm focus:outline-none transition-colors"
                style={{
                  backgroundColor: '#0f1629',
                  border: '1px solid rgba(255,255,255,0.08)',
                }}
                onFocus={(e) =>
                  (e.target.style.borderColor = 'rgba(245,166,35,0.5)')
                }
                onBlur={(e) =>
                  (e.target.style.borderColor = 'rgba(255,255,255,0.08)')
                }
                placeholder="1000000"
              />
            </div>
            <p className="font-mono text-xs text-slate-600 mt-2">
              Larger pools reward higher-variance pick strategies
            </p>
          </div>

          {/* Year indicator */}
          <div
            className="flex items-center justify-between rounded-lg px-4 py-3"
            style={{
              backgroundColor: '#0f1629',
              border: '1px solid rgba(255,255,255,0.05)',
            }}
          >
            <span className="font-mono text-xs tracking-widest text-slate-500 uppercase">
              Tournament Year
            </span>
            <span className="font-mono font-bold text-white">2026</span>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-4 rounded-xl font-mono font-black text-lg tracking-[0.2em] uppercase transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: loading ? 'rgba(245,166,35,0.5)' : '#f5a623',
              color: '#0a0e1a',
              boxShadow: loading
                ? 'none'
                : '0 0 30px rgba(245,166,35,0.35), 0 4px 20px rgba(245,166,35,0.25)',
            }}
            onMouseEnter={(e) => {
              if (!loading) {
                e.target.style.boxShadow =
                  '0 0 50px rgba(245,166,35,0.55), 0 4px 30px rgba(245,166,35,0.4)';
                e.target.style.transform = 'translateY(-1px)';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading) {
                e.target.style.boxShadow =
                  '0 0 30px rgba(245,166,35,0.35), 0 4px 20px rgba(245,166,35,0.25)';
                e.target.style.transform = 'translateY(0)';
              }
            }}
          >
            {loading ? 'RUNNING...' : 'RUN SIMULATION'}
          </button>
        </form>

        {/* Footer note */}
        <p className="text-center font-mono text-xs text-slate-600 mt-6">
          Monte Carlo · XGBoost · KenPom · Vegas Lines · Historical Seed Data
        </p>
      </div>

      <style>{`
        input[type='range']::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #f5a623;
          cursor: pointer;
          box-shadow: 0 0 10px rgba(245,166,35,0.6);
          border: 2px solid #0a0e1a;
        }
        input[type='range']::-moz-range-thumb {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #f5a623;
          cursor: pointer;
          box-shadow: 0 0 10px rgba(245,166,35,0.6);
          border: 2px solid #0a0e1a;
        }
      `}</style>
    </section>
  );
}
