import type { CanvasRenderingTarget2D } from "fancy-canvas";
import type {
  IChartApiBase,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  PrimitivePaneViewZOrder,
  SeriesAttachedParameter,
  SeriesType,
  Time,
  UTCTimestamp,
} from "lightweight-charts";

export interface IchimokuCloudDataPoint {
  time: UTCTimestamp;
  spanA: number;
  spanB: number;
}

class IchimokuCloudPaneRenderer implements IPrimitivePaneRenderer {
  private _primitive: IchimokuCloudPrimitive;

  constructor(primitive: IchimokuCloudPrimitive) {
    this._primitive = primitive;
  }

  draw(target: CanvasRenderingTarget2D) {
    target.useMediaCoordinateSpace((scope) => {
      const chart = this._primitive.chart;
      const series = this._primitive.series;
      const data = this._primitive.data;

      if (!chart || !series || data.length < 2) return;

      const timeScale = chart.timeScale();
      const ctx = scope.context;

      for (let i = 0; i < data.length - 1; i++) {
        const p1 = data[i];
        const p2 = data[i + 1];

        const x1 = timeScale.timeToCoordinate(p1.time as unknown as Time);
        const x2 = timeScale.timeToCoordinate(p2.time as unknown as Time);
        if (x1 == null || x2 == null) continue;

        const yA1 = series.priceToCoordinate(p1.spanA);
        const yB1 = series.priceToCoordinate(p1.spanB);
        const yA2 = series.priceToCoordinate(p2.spanA);
        const yB2 = series.priceToCoordinate(p2.spanB);
        if (yA1 == null || yB1 == null || yA2 == null || yB2 == null) continue;

        // Bullish cloud (Span A >= Span B) = soft emerald green
        // Bearish cloud (Span A < Span B) = soft coral rose
        const isBullish = (p1.spanA + p2.spanA) >= (p1.spanB + p2.spanB);
        ctx.fillStyle = isBullish
          ? "rgba(52, 211, 153, 0.22)" // Emerald with 22% opacity
          : "rgba(244, 63, 94, 0.22)";  // Rose with 22% opacity

        ctx.beginPath();
        ctx.moveTo(x1, yA1);
        ctx.lineTo(x2, yA2);
        ctx.lineTo(x2, yB2);
        ctx.lineTo(x1, yB1);
        ctx.closePath();
        ctx.fill();
      }
    });
  }
}

class IchimokuCloudPaneView implements IPrimitivePaneView {
  private _renderer: IchimokuCloudPaneRenderer;

  constructor(primitive: IchimokuCloudPrimitive) {
    this._renderer = new IchimokuCloudPaneRenderer(primitive);
  }

  zOrder(): PrimitivePaneViewZOrder {
    // "bottom" ensures the cloud is drawn beneath candlesticks and indicator lines
    return "bottom";
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

export class IchimokuCloudPrimitive implements ISeriesPrimitive<Time> {
  private _chart: IChartApiBase<Time> | null = null;
  private _series: ISeriesApi<SeriesType, Time> | null = null;
  private _requestUpdate: (() => void) | null = null;
  private _data: IchimokuCloudDataPoint[] = [];
  private _paneViews: IPrimitivePaneView[];

  constructor(data: IchimokuCloudDataPoint[] = []) {
    this._data = data;
    this._paneViews = [new IchimokuCloudPaneView(this)];
  }

  get chart(): IChartApiBase<Time> | null {
    return this._chart;
  }

  get series(): ISeriesApi<SeriesType, Time> | null {
    return this._series;
  }

  get data(): IchimokuCloudDataPoint[] {
    return this._data;
  }

  setData(data: IchimokuCloudDataPoint[]) {
    this._data = data;
    this._requestUpdate?.();
  }

  attached(param: SeriesAttachedParameter<Time, SeriesType>) {
    this._chart = param.chart;
    this._series = param.series;
    this._requestUpdate = param.requestUpdate;
    this._requestUpdate?.();
  }

  detached() {
    this._chart = null;
    this._series = null;
    this._requestUpdate = null;
  }

  updateAllViews() {}

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews;
  }
}
