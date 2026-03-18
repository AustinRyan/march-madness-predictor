import { useState, useCallback } from 'react';
import axios from 'axios';

export function useSimulation() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const runSimulation = useCallback(async ({ risk, pool_size, year }) => {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const response = await axios.post('/api/run-simulation', {
        risk,
        pool_size,
        year,
      });
      setData(response.data);
    } catch (err) {
      const message =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'Simulation failed. Check that the backend is running.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, runSimulation };
}

export function useUpsetAlerts() {
  const [alerts, setAlerts] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchAlerts = useCallback(async (customPicks) => {
    setLoading(true);
    setError(null);
    try {
      // If custom picks provided (e.g. after override), POST them so alerts
      // reflect the current bracket state. Otherwise GET default alerts.
      const response = customPicks
        ? await axios.post('/api/upset-alerts', { picks: customPicks })
        : await axios.get('/api/upset-alerts');
      // API returns {total_games, high_alerts, round_summary, alerts: [...]}
      const raw = response.data.alerts || response.data || [];
      const FLAG_KEYS = [
        'rank_within_15', 'tempo_mismatch_8', 'favorite_fading',
        'dog_coach_above_avg', 'dog_luck_negative', 'style_clash_3pt',
        'hist_upset_rate_30', 'elo_close', 'fav_soft_losses',
        'vegas_close_line', 'vegas_upset_likely',
      ];
      const cleaned = raw.map((a) => ({
        ...a,
        triggered_flags: FLAG_KEYS.filter((k) => a[k] === true),
        seed_favorite: a.higher_seed,
        seed_underdog: a.lower_seed,
        historical_rate: a.hist_upset_rate,
      }));
      setAlerts({
        items: cleaned,
        roundSummary: response.data.round_summary || {},
        totalGames: response.data.total_games || cleaned.length,
        highAlerts: response.data.high_alerts || 0,
      });
    } catch (err) {
      const message =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'Failed to fetch upset alerts.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  return { alerts, loading, error, fetchAlerts };
}

export function useOverride() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const applyOverride = useCallback(async ({ round, team_a, team_b, new_winner, region, current_picks }) => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post('/api/override-pick', {
        round,
        team_a,
        team_b,
        new_winner,
        region,
        current_picks,
      });
      return response.data;
    } catch (err) {
      const message =
        err.response?.data?.detail ||
        err.message ||
        'Override failed.';
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { applyOverride, loading, error };
}

export function useModelBenchmark() {
  const [benchmark, setBenchmark] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchBenchmark = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get('/api/model-benchmark');
      setBenchmark(response.data);
    } catch (err) {
      const message =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'Failed to fetch benchmark data.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  return { benchmark, loading, error, fetchBenchmark };
}
