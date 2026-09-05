export interface BacktestMetrics {
  trades: number;
  winRate: number;
  totalReturn: number;
  averageReturn: number;
  sharpe: number;
  maxDrawdown: number;
}

export interface BacktestTrade {
  signalAt: string;
  symbol: string;
  direction: "bullish" | "bearish";
  optionBias: "call_debit_spread" | "put_debit_spread";
  conviction: number;
  underlyingProxyReturn: number;
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
  trades?: BacktestTrade[];
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
    generatedAt: "2026-09-05T11:29:33.473594+00:00",
    source: "Alpaca IEX fully adjusted 15-minute bars",
    period: "Mar 9, 2026 – Sep 4, 2026",
    bars: 3867,
    barSize: "15-minute SPY",
    methodology: "Prior-session symbol trend plus 15-minute 18 EMA cross; SPY is advisory; next-bar open, eight-bar hold, 70/30 split, 20 bps underlying-proxy friction",
    gatePassed: true,
    train: { trades: 75, winRate: 0.4933, totalReturn: 0.2312, averageReturn: 0.003, sharpe: 4.173, maxDrawdown: -0.0943 },
    holdout: { trades: 44, winRate: 0.4773, totalReturn: 0.0849, averageReturn: 0.0021, sharpe: 2.653, maxDrawdown: -0.1397 },
    parameters: [["Signal EMA", "18 intraday bars"], ["Daily trend", "18 / 50 EMA"], ["Tier shown", "55–60% exploration"], ["Risk cap", "$500"]],
    limitations: ["The 60%+ production tier remains locked after a negative holdout.", "Measures underlying direction, not historical option-spread fills.", "Live option quote width and open interest must still pass.", "Past performance does not predict future results."],
    trades: [
      { signalAt: "2026-08-20T19:45:00+00:00", symbol: "GOOGL", direction: "bearish", optionBias: "put_debit_spread", conviction: 0.5747, underlyingProxyReturn: -0.0064 },
      { signalAt: "2026-08-21T19:45:00+00:00", symbol: "META", direction: "bearish", optionBias: "put_debit_spread", conviction: 0.5613, underlyingProxyReturn: -0.0076 },
      { signalAt: "2026-08-24T19:45:00+00:00", symbol: "GOOGL", direction: "bearish", optionBias: "put_debit_spread", conviction: 0.5773, underlyingProxyReturn: 0.0035 },
      { signalAt: "2026-08-25T19:45:00+00:00", symbol: "WMT", direction: "bearish", optionBias: "put_debit_spread", conviction: 0.5564, underlyingProxyReturn: 0.0082 },
      { signalAt: "2026-08-28T13:30:00+00:00", symbol: "AMD", direction: "bearish", optionBias: "put_debit_spread", conviction: 0.5997, underlyingProxyReturn: 0.0017 },
      { signalAt: "2026-08-28T19:45:00+00:00", symbol: "LLY", direction: "bullish", optionBias: "call_debit_spread", conviction: 0.5902, underlyingProxyReturn: -0.0169 },
      { signalAt: "2026-08-31T19:15:00+00:00", symbol: "NVDA", direction: "bullish", optionBias: "call_debit_spread", conviction: 0.5508, underlyingProxyReturn: -0.0102 },
      { signalAt: "2026-09-01T18:45:00+00:00", symbol: "NFLX", direction: "bullish", optionBias: "call_debit_spread", conviction: 0.5594, underlyingProxyReturn: 0.0153 },
      { signalAt: "2026-09-02T14:45:00+00:00", symbol: "AVGO", direction: "bearish", optionBias: "put_debit_spread", conviction: 0.5698, underlyingProxyReturn: -0.0042 },
      { signalAt: "2026-09-02T19:15:00+00:00", symbol: "AVGO", direction: "bearish", optionBias: "put_debit_spread", conviction: 0.5551, underlyingProxyReturn: 0.0571 },
      { signalAt: "2026-09-03T13:30:00+00:00", symbol: "AAPL", direction: "bullish", optionBias: "call_debit_spread", conviction: 0.5897, underlyingProxyReturn: 0.0081 },
      { signalAt: "2026-09-03T19:00:00+00:00", symbol: "AMD", direction: "bearish", optionBias: "put_debit_spread", conviction: 0.5518, underlyingProxyReturn: -0.0285 },
    ],
  },
];
