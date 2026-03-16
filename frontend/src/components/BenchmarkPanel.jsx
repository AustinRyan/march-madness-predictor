import { useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { useModelBenchmark } from '../hooks/useApi';

const MODEL_COLORS = {
  'This Model': '#f5a623',
  Chalk: '#64748b',
  'KenPom-only': '#22d3ee',
  Vegas: '#8b5cf6',
};

function metricColor(modelName) {
  return MODEL_COLORS[modelName] ?? '#94a3b8';
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div
      className="rounded-lg p-3 font-mono text-xs space-y-1"
      style={{
        backgroundColor: '#0f1629',
        border: '1px solid rgba(255,255,255,0.1)',
        boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
      }}
    >
      <p className="font-bold text-white mb-2">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex justify-between gap-6">
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span className="text-white font-bold">{entry.value?.toFixed(4)}</span>
        </div>
      ))}
    </div>
  );
}

function MetricChart({ title, dataKey, data, higherIsBetter, yDomain }) {
  const models = data.map((d) => d.model);

  const chartData = [
    {
      metric: title,
      ...Object.fromEntries(data.map((d) => [d.model, d[dataKey]])),
    },
  ];

  // For grouped view: one bar per model
  const barData = data.map((d) => ({
    model: d.model,
    value: d[dataKey],
  }));

  const best = higherIsBetter
    ? Math.max(...barData.map((d) => d.value ?? -Infinity))
    : Math.min(...barData.map((d) => d.value ?? Infinity));

  return (
    <div
      className="rounded-xl p-5"
      style={{
        backgroundColor: '#151d38',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-mono font-bold text-sm text-white tracking-widest uppercase">
          {title}
        </h3>
        <span className="font-mono text-xs text-slate-500">
          {higherIsBetter ? '↑ higher = better' : '↓ lower = better'}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart
          data={barData}
          layout="vertical"
          margin={{ top: 0, right: 30, bottom: 0, left: 80 }}
          barCategoryGap="30%"
        >
          <CartesianGrid
            horizontal={false}
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.04)"
          />
          <XAxis
            type="number"
            domain={yDomain ?? ['auto', 'auto']}
            tick={{ fill: '#64748b', fontFamily: 'monospace', fontSize: 10 }}
            tickLine={{ stroke: '#334155' }}
            axisLine={{ stroke: '#334155' }}
            tickFormatter={(v) => v.toFixed(3)}
          />
          <YAxis
            type="category"
            dataKey="model"
            tick={{ fill: '#94a3b8', fontFamily: 'monospace', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={76}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0];
              const isBest = d.payload.value === best;
              return (
                <div
                  className="rounded-lg px-3 py-2 font-mono text-xs"
                  style={{
                    backgroundColor: '#0f1629',
                    border: '1px solid rgba(255,255,255,0.1)',
                  }}
                >
                  <span style={{ color: metricColor(d.payload.model) }}>
                    {d.payload.model}
                  </span>
                  <span className="text-white font-bold ml-3">
                    {d.payload.value?.toFixed(4)}
                  </span>
                  {isBest && (
                    <span className="ml-2 text-emerald-400">★ best</span>
                  )}
                </div>
              );
            }}
            cursor={{ fill: 'rgba(255,255,255,0.02)' }}
          />
          <Bar dataKey="value" radius={[0, 3, 3, 0]}>
            {barData.map((entry, index) => {
              const isBest = entry.value === best;
              const color = isBest ? '#f5a623' : metricColor(entry.model);
              return (
                <Cell
                  key={`cell-${index}`}
                  fill={color}
                  fillOpacity={isBest ? 0.9 : 0.45}
                />
              );
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ModelLegend() {
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2 mb-6">
      {Object.entries(MODEL_COLORS).map(([model, color]) => (
        <div key={model} className="flex items-center gap-2">
          <div
            className="w-3 h-2 rounded-sm"
            style={{ backgroundColor: color, opacity: 0.8 }}
          />
          <span className="font-mono text-xs text-slate-400">{model}</span>
        </div>
      ))}
    </div>
  );
}

function SummaryTable({ data }) {
  if (!data || data.length === 0) return null;
  const metrics = ['accuracy', 'log_loss', 'brier_score'];
  const metaMap = {
    accuracy: { label: 'Accuracy', higherIsBetter: true },
    log_loss: { label: 'Log Loss', higherIsBetter: false },
    brier_score: { label: 'Brier Score', higherIsBetter: false },
  };

  return (
    <div
      className="rounded-xl overflow-hidden mb-8"
      style={{
        backgroundColor: '#151d38',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      <table className="w-full border-collapse">
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            <th className="px-5 py-3 text-left font-mono text-xs tracking-widest text-slate-600 uppercase">
              Model
            </th>
            {metrics.map((m) => (
              <th
                key={m}
                className="px-5 py-3 text-right font-mono text-xs tracking-widest text-slate-600 uppercase"
              >
                {metaMap[m].label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => {
            const isThisModel = row.model === 'This Model';
            return (
              <tr
                key={i}
                style={{
                  borderBottom:
                    i < data.length - 1
                      ? '1px solid rgba(255,255,255,0.03)'
                      : 'none',
                  backgroundColor: isThisModel
                    ? 'rgba(245,166,35,0.04)'
                    : 'transparent',
                }}
              >
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: metricColor(row.model) }}
                    />
                    <span
                      className={`font-mono text-sm ${
                        isThisModel ? 'font-bold' : ''
                      }`}
                      style={{ color: isThisModel ? '#f5a623' : '#e2e8f0' }}
                    >
                      {row.model}
                    </span>
                  </div>
                </td>
                {metrics.map((m) => {
                  const val = row[m];
                  const { higherIsBetter } = metaMap[m];
                  const allVals = data.map((d) => d[m]).filter((v) => v != null);
                  const best = higherIsBetter
                    ? Math.max(...allVals)
                    : Math.min(...allVals);
                  const isBest = val === best;
                  return (
                    <td
                      key={m}
                      className="px-5 py-3 text-right font-mono text-sm tabular-nums"
                      style={{
                        color: isBest ? '#10b981' : '#94a3b8',
                        fontWeight: isBest ? 700 : 400,
                      }}
                    >
                      {val != null ? val.toFixed(4) : '—'}
                      {isBest && (
                        <span className="ml-1 text-xs text-emerald-400">★</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function BenchmarkPanel() {
  const { benchmark, loading, error, fetchBenchmark } = useModelBenchmark();

  useEffect(() => {
    fetchBenchmark();
  }, [fetchBenchmark]);

  return (
    <section className="px-4 py-8 max-w-5xl mx-auto">
      {/* Section header */}
      <div className="flex items-center gap-4 mb-6">
        <div
          className="h-8 w-1 rounded-full"
          style={{ backgroundColor: '#8b5cf6' }}
        />
        <h2 className="font-mono font-black text-2xl text-white tracking-tight">
          MODEL BENCHMARK
        </h2>
      </div>

      <p className="font-mono text-xs text-slate-500 mb-6">
        Head-to-head comparison against baseline strategies. Gold bars indicate best performance.
        ★ marks best in each metric.
      </p>

      {loading && (
        <div className="flex items-center justify-center py-16 gap-3">
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: '#f5a623', animation: 'pulse 1s infinite' }}
          />
          <span className="font-mono text-sm text-slate-400">
            Loading benchmark data...
          </span>
        </div>
      )}

      {error && (
        <div
          className="rounded-lg px-5 py-4 font-mono text-sm mb-6"
          style={{
            backgroundColor: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            color: '#fca5a5',
          }}
        >
          <span className="font-bold">Error: </span>
          {error}
        </div>
      )}

      {benchmark && benchmark.length > 0 && (
        <>
          <ModelLegend />
          <SummaryTable data={benchmark} />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <MetricChart
              title="Accuracy"
              dataKey="accuracy"
              data={benchmark}
              higherIsBetter
              yDomain={[0, 1]}
            />
            <MetricChart
              title="Log Loss"
              dataKey="log_loss"
              data={benchmark}
              higherIsBetter={false}
            />
            <MetricChart
              title="Brier Score"
              dataKey="brier_score"
              data={benchmark}
              higherIsBetter={false}
              yDomain={[0, 0.3]}
            />
          </div>
        </>
      )}

      {!loading && !error && (!benchmark || benchmark.length === 0) && (
        <div
          className="rounded-xl p-10 text-center"
          style={{
            backgroundColor: '#151d38',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <p className="font-mono text-slate-500 text-sm">
            No benchmark data returned from /api/model-benchmark.
          </p>
          <button
            onClick={fetchBenchmark}
            className="mt-4 font-mono text-xs px-4 py-2 rounded-lg transition-colors"
            style={{
              color: '#f5a623',
              backgroundColor: 'rgba(245,166,35,0.1)',
              border: '1px solid rgba(245,166,35,0.25)',
            }}
          >
            RETRY
          </button>
        </div>
      )}
    </section>
  );
}
