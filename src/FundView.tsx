import {Alert, Button, Card, Chip, Link, Spinner} from "@heroui/react";
import {LineChart} from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components";
import {init, use, type EChartsCoreOption, type EChartsType} from "echarts/core";
import {CanvasRenderer} from "echarts/renderers";
import {useEffect, useMemo, useRef, useState} from "react";

import {fetchEtfDashboard} from "./api";
import type {EtfDashboard, EtfFundItem} from "./types";

use([
  LineChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
]);

type ChartMode = "normalized" | "absolute";

interface FundViewProps {
  onDataDate?: (date: string) => void;
}

function amountInBillions(value: string) {
  return Number(value || 0) / 100_000_000;
}

function sharesInBillions(value?: string | null) {
  return value ? Number(value) / 100_000_000 : null;
}

function compactNumber(value: number) {
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function percentageChange(first: number | null, last: number | null) {
  if (first === null || last === null || first === 0) return null;
  return ((last / first) - 1) * 100;
}

function normalize(values: Array<number | null>) {
  const base = values.find((value): value is number => value !== null && value !== 0);
  if (!base) return values;
  return values.map((value) => (value === null ? null : (value / base) * 100));
}

function TrendChart({fund, mode}: {fund: EtfFundItem; mode: ChartMode}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsType | null>(null);

  const option = useMemo<EChartsCoreOption>(() => {
    const dates = fund.history.map((point) => point.date.slice(5));
    const shares = fund.history.map((point) => sharesInBillions(point.total_shares));
    const indexValues = fund.history.map((point) =>
      point.index_close === null ? null : Number(point.index_close),
    );
    const normalized = mode === "normalized";
    const shareSeries = normalized ? normalize(shares) : shares;
    const indexSeries = normalized ? normalize(indexValues) : indexValues;
    const rawByDate = new Map(fund.history.map((point) => [point.date.slice(5), point]));

    return {
      animationDuration: 450,
      color: ["#bb8b3d", "#2f6f91"],
      grid: {top: 50, right: normalized ? 28 : 68, bottom: 58, left: 62},
      legend: {
        top: 4,
        right: 4,
        itemWidth: 18,
        itemHeight: 3,
        textStyle: {color: "#526172", fontSize: 11},
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(11,31,51,.94)",
        borderColor: "rgba(255,255,255,.12)",
        textStyle: {color: "#fff", fontSize: 12},
        formatter: (parameters: unknown) => {
          const entries = parameters as Array<{
            axisValue: string;
            color: string;
            seriesName: string;
          }>;
          const dateLabel = entries[0]?.axisValue ?? "";
          const raw = rawByDate.get(dateLabel);
          const sharesText = raw?.total_shares
            ? `${compactNumber(Number(raw.total_shares) / 100_000_000)} 亿份`
            : "暂无数据";
          const indexText = raw?.index_close
            ? compactNumber(Number(raw.index_close))
            : "暂无数据";
          return [
            `<strong>${fund.history.find((point) => point.date.slice(5) === dateLabel)?.date ?? dateLabel}</strong>`,
            `<span style="color:#d8b36a">●</span> 基金份额：${sharesText}`,
            `<span style="color:#65a6c8">●</span> ${fund.benchmark.name || "跟踪指数"}：${indexText}`,
          ].join("<br/>");
        },
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: dates,
        axisLine: {lineStyle: {color: "#cdd5dc"}},
        axisTick: {show: false},
        axisLabel: {color: "#7c8997", fontSize: 10},
      },
      yAxis: normalized
        ? {
            type: "value",
            name: "起点 = 100",
            scale: true,
            nameTextStyle: {color: "#7c8997", fontSize: 10},
            axisLabel: {color: "#7c8997", formatter: "{value}"},
            splitLine: {lineStyle: {color: "#e9edf1"}},
          }
        : [
            {
              type: "value",
              name: "份额（亿份）",
              scale: true,
              nameTextStyle: {color: "#bb8b3d", fontSize: 10},
              axisLabel: {color: "#7c8997"},
              splitLine: {lineStyle: {color: "#e9edf1"}},
            },
            {
              type: "value",
              name: "指数点位",
              scale: true,
              nameTextStyle: {color: "#2f6f91", fontSize: 10},
              axisLabel: {color: "#7c8997"},
              splitLine: {show: false},
            },
          ],
      dataZoom: [{type: "inside", filterMode: "none"}],
      series: [
        {
          name: "基金份额",
          type: "line",
          yAxisIndex: 0,
          data: shareSeries,
          connectNulls: false,
          showSymbol: shareSeries.filter((value) => value !== null).length <= 35,
          symbolSize: 5,
          lineStyle: {width: 2.5},
          areaStyle: {color: "rgba(187,139,61,.08)"},
          emphasis: {focus: "series"},
        },
        {
          name: fund.benchmark.name || "跟踪指数",
          type: "line",
          yAxisIndex: normalized ? 0 : 1,
          data: indexSeries,
          connectNulls: false,
          showSymbol: false,
          lineStyle: {width: 2},
          emphasis: {focus: "series"},
        },
      ],
    };
  }, [fund, mode]);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = init(containerRef.current);
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);

  return <div className="fund-chart" ref={containerRef} role="img" aria-label={`${fund.fund_expansion_abbr}份额与跟踪指数趋势图`} />;
}

export default function FundView({onDataDate}: FundViewProps) {
  const [dashboard, setDashboard] = useState<EtfDashboard | null>(null);
  const [selectedCode, setSelectedCode] = useState("");
  const [mode, setMode] = useState<ChartMode>("normalized");
  const [draftStart, setDraftStart] = useState("");
  const [draftEnd, setDraftEnd] = useState("");
  const [queryRange, setQueryRange] = useState<{startDate: string; endDate: string}>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetchEtfDashboard(queryRange, controller.signal)
      .then((result) => {
        setDashboard(result);
        setDraftStart(result.range.start_date);
        setDraftEnd(result.range.end_date);
        setSelectedCode((current) =>
          result.items.some((item) => item.fund_code === current)
            ? current
            : result.items[0]?.fund_code || "",
        );
        onDataDate?.(result.latest_date);
      })
      .catch((loadError: unknown) => {
        if (!controller.signal.aborted) {
          setError(loadError instanceof Error ? loadError.message : "基金数据加载失败");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [onDataDate, queryRange]);

  const selectedFund =
    dashboard?.items.find((item) => item.fund_code === selectedCode) ??
    dashboard?.items[0];
  const totalScale = useMemo(
    () => dashboard?.items.reduce(
      (sum, item) => sum + amountInBillions(item.estimated_total_amount),
      0,
    ) ?? 0,
    [dashboard],
  );
  const trendStats = useMemo(() => {
    if (!selectedFund) return {latest: null, change: null, missing: 0};
    const values = selectedFund.history
      .map((point) => sharesInBillions(point.total_shares))
      .filter((value): value is number => value !== null);
    return {
      latest: values.at(-1) ?? null,
      change: percentageChange(values[0] ?? null, values.at(-1) ?? null),
      missing: selectedFund.history.length - values.length,
    };
  }, [selectedFund]);

  if (loading && !dashboard) {
    return (
      <main className="fund-state">
        <Spinner size="lg" color="accent" />
        <span>正在载入基金规模与指数数据…</span>
      </main>
    );
  }

  if (error && !dashboard) {
    return (
      <main className="fund-state">
        <Alert status="danger">
          <Alert.Content>
            <Alert.Title>基金数据加载失败</Alert.Title>
            <Alert.Description>{error}</Alert.Description>
          </Alert.Content>
        </Alert>
      </main>
    );
  }

  if (!dashboard?.items.length || !selectedFund) {
    return <main className="fund-state">数据库中暂无基金规模排行数据。</main>;
  }

  const applyRange = () => {
    if (!draftStart || !draftEnd) {
      setError("请选择完整的起止日期");
      return;
    }
    setQueryRange({startDate: draftStart, endDate: draftEnd});
  };

  return (
    <main className="fund-page">
      <section className="fund-hero">
        <div>
          <div className="eyebrow">ETF CAPITAL MONITOR</div>
          <h1>基金规模与指数趋势</h1>
          <p>追踪上交所规模领先 ETF 的份额变化，并与各自跟踪标的同步对照。</p>
        </div>
        <div className="fund-hero-date">
          <span>最新排名日期</span>
          <strong>{dashboard.latest_date}</strong>
          <small>规模按收盘价 × 总份额估算</small>
        </div>
      </section>

      <section className="fund-metrics" aria-label="基金规模摘要">
        <Card><span>榜单基金</span><strong>{dashboard.items.length}</strong><small>上交所 ETF</small></Card>
        <Card><span>合计估算规模</span><strong>{compactNumber(totalScale)}</strong><small>亿元</small></Card>
        <Card><span>区间交易日</span><strong>{dashboard.range.trading_days}</strong><small>最多 90 日</small></Card>
        <Card><span>规模第一</span><strong>{dashboard.items[0].fund_code}</strong><small>{dashboard.items[0].fund_expansion_abbr}</small></Card>
      </section>

      {error && (
        <Alert className="fund-inline-alert" status="warning">
          <Alert.Content><Alert.Description>{error}</Alert.Description></Alert.Content>
        </Alert>
      )}

      <section className="fund-dashboard">
        <Card className="fund-ranking">
          <Card.Header className="fund-panel-head">
            <div><span>SIZE RANKING</span><h2>规模排行</h2></div>
            <Chip size="sm" variant="soft">TOP 10</Chip>
          </Card.Header>
          <Card.Content className="fund-ranking-list">
            {dashboard.items.map((fund) => (
              <button
                type="button"
                className={`fund-rank-row ${fund.fund_code === selectedFund.fund_code ? "active" : ""}`}
                key={fund.fund_code}
                onClick={() => setSelectedCode(fund.fund_code)}
              >
                <span className={`fund-rank-number rank-${fund.rank}`}>{String(fund.rank).padStart(2, "0")}</span>
                <span className="fund-rank-main">
                  <strong>{fund.fund_expansion_abbr || fund.fund_name}</strong>
                  <small>{fund.fund_code} · {fund.etf_type || "ETF"}</small>
                </span>
                <span className="fund-rank-scale">
                  <strong>{compactNumber(amountInBillions(fund.estimated_total_amount))}</strong>
                  <small>亿元</small>
                </span>
              </button>
            ))}
          </Card.Content>
        </Card>

        <Card className="fund-trend-panel">
          <Card.Header className="fund-trend-head">
            <div>
              <span className="fund-code">{selectedFund.fund_code}</span>
              <h2>{selectedFund.fund_expansion_abbr || selectedFund.fund_name}</h2>
              <p>{selectedFund.benchmark.name || "跟踪指数尚未配置"}</p>
            </div>
            <Link href={selectedFund.source_url} target="_blank" rel="noopener noreferrer">
              上交所数据源 ↗
            </Link>
          </Card.Header>

          <div className="fund-controls">
            <label>起始日期<input type="date" value={draftStart} max={draftEnd || dashboard.latest_date} onChange={(event) => setDraftStart(event.target.value)} /></label>
            <label>结束日期<input type="date" value={draftEnd} min={draftStart} max={dashboard.latest_date} onChange={(event) => setDraftEnd(event.target.value)} /></label>
            <Button size="sm" className="fund-apply" onPress={applyRange} isPending={loading}>应用区间</Button>
            <Button
              size="sm"
              variant="ghost"
              onPress={() => {
                setError("");
                if (queryRange) {
                  setQueryRange(undefined);
                } else {
                  setDraftStart(dashboard.range.start_date);
                  setDraftEnd(dashboard.range.end_date);
                }
              }}
            >
              最近 30 日
            </Button>
            <div className="fund-mode-switch" aria-label="图表模式">
              <button className={mode === "normalized" ? "active" : ""} onClick={() => setMode("normalized")}>归一化</button>
              <button className={mode === "absolute" ? "active" : ""} onClick={() => setMode("absolute")}>绝对值</button>
            </div>
          </div>

          <div className="fund-selected-metrics">
            <div><span>最新份额</span><strong>{trendStats.latest === null ? "—" : compactNumber(trendStats.latest)}</strong><small>亿份</small></div>
            <div><span>区间份额变化</span><strong className={(trendStats.change ?? 0) >= 0 ? "up" : "down"}>{trendStats.change === null ? "—" : `${trendStats.change >= 0 ? "+" : ""}${trendStats.change.toFixed(2)}%`}</strong></div>
            <div><span>最新估算规模</span><strong>{compactNumber(amountInBillions(selectedFund.estimated_total_amount))}</strong><small>亿元</small></div>
            <div><span>数据覆盖</span><strong>{selectedFund.history.length - trendStats.missing}/{selectedFund.history.length}</strong><small>交易日</small></div>
          </div>

          {selectedFund.benchmark.supported ? (
            <TrendChart fund={selectedFund} mode={mode} />
          ) : (
            <div className="fund-chart-unavailable">
              <strong>跟踪指数暂不可用</strong>
              <p>{selectedFund.benchmark.note || "AkShare 暂无该精确指数数据。"}</p>
            </div>
          )}
          {trendStats.missing > 0 && (
            <p className="fund-gap-note">
              份额缺失的 {trendStats.missing} 个交易日保留为空白断点，不以 0 代替。
            </p>
          )}
        </Card>
      </section>
    </main>
  );
}
