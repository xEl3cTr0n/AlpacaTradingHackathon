export interface BacktestMetrics {
  trades: number;
  winRate: number;
  totalReturn: number;
  averageReturn: number;
  sharpe: number;
  maxDrawdown: number;
}

export interface BacktestReport {
  id: string;
  name: string;
  instrument: string;
  generatedAt: string;
  source: string;
  period: string;
  bars: number;
  barSize: string;
  methodology: string;
  gatePassed: boolean;
  train: BacktestMetrics;
  holdout: BacktestMetrics;
  parameters: Array<[string, string]>;
  limitations: string[];
}

export const backtestReports: BacktestReport[] = [
  {
    id: "swing",
    name: "SPY swing breakout",
    instrument: "SPY signal → XSP defined-risk debit spread",
    generatedAt: "2026-09-02T10:45:00+00:00",
    source: "Alpaca IEX fully adjusted daily bars",
    period: "Sep 7, 2021 – Sep 1, 2026",
    bars: 1252,
    barSize: "daily",
    methodology: "70/30 chronological train/holdout, non-overlapping trades, 15 bps proxy friction",
    gatePassed: true,
    train: { trades: 27, winRate: 0.6296, totalReturn: 0.1158, averageReturn: 0.0043, sharpe: 1.026, maxDrawdown: -0.0707 },
    holdout: { trades: 15, winRate: 0.6667, totalReturn: 0.0528, averageReturn: 0.0035, sharpe: 1.298, maxDrawdown: -0.0308 },
    parameters: [["Breakout", "10 sessions"], ["Holding period", "10 sessions"], ["Council threshold", "52%"], ["Max volatility percentile", "70%"]],
    limitations: ["Measures signal direction, not historical option-spread fills.", "SPY proxies XSP because index-level history is unavailable.", "Past performance does not predict future results."],
  },
  {
    id: "scanner",
    name: "Large-cap 18 EMA scanner",
    instrument: "24-name liquid equity-options universe",
    generatedAt: "2026-09-02T10:56:18.191275+00:00",
    source: "Alpaca IEX fully adjusted daily bars",
    period: "Sep 7, 2021 – Sep 1, 2026",
    bars: 1252,
    barSize: "daily",
    methodology: "18 EMA price cross, next-session open, one top-ranked candidate, 70/30 split, 20 bps friction",
    gatePassed: true,
    train: { trades: 33, winRate: 0.5758, totalReturn: 0.3415, averageReturn: 0.0101, sharpe: 1.897, maxDrawdown: -0.1501 },
    holdout: { trades: 33, winRate: 0.6667, totalReturn: 0.1167, averageReturn: 0.0051, sharpe: 0.824, maxDrawdown: -0.2696 },
    parameters: [["Signal EMA", "18 sessions"], ["Trend EMA", "50 sessions"], ["Minimum conviction", "60%"], ["Holding period", "3 sessions"]],
    limitations: ["Measures underlying direction, not historical option-spread fills.", "Dollar volume is only a first-stage liquidity proxy.", "Moving averages can whipsaw in range-bound markets.", "Past performance does not predict future results."],
  },
  {
    id: "intraday-scanner",
    name: "Intraday 18 EMA scanner",
    instrument: "15-minute trigger → defined-risk large-cap option spread",
    generatedAt: "2026-09-04T10:57:02.810932+00:00",
    source: "Alpaca IEX fully adjusted 15-minute bars",
    period: "May 7, 2026 – Sep 3, 2026",
    bars: 2481,
    barSize: "15-minute SPY",
    methodology: "Prior-session daily trend plus 15-minute 18 EMA cross, next-bar open, eight-bar hold, 70/30 split, 20 bps underlying-proxy friction",
    gatePassed: true,
    train: { trades: 27, winRate: 0.4444, totalReturn: -0.041, averageReturn: -0.0013, sharpe: -1.76, maxDrawdown: -0.0591 },
    holdout: { trades: 22, winRate: 0.5909, totalReturn: 0.0408, averageReturn: 0.0019, sharpe: 6.433, maxDrawdown: -0.027 },
    parameters: [["Signal EMA", "18 intraday bars"], ["Daily trend", "18 / 50 EMA"], ["Tier shown", "55–60% exploration"], ["Risk cap", "$500"]],
    limitations: ["The 60%+ production tier remains locked after a negative holdout.", "Measures underlying direction, not historical option-spread fills.", "Live option quote width and open interest must still pass.", "Past performance does not predict future results."],
  },
];
