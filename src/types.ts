export interface NewsItem {
  title: string;
  url: string;
  time: string;
  ts: number;
  summary: string;
  source: string;
  zh: string;
}

export interface DigestPoint {
  t: string;
  url: string;
}

export interface Industry {
  key: string;
  name: string;
  accent: string;
  total: number;
  items: NewsItem[];
  points: DigestPoint[];
}

export interface NewsData {
  generated_at: string;
  recent_days: number;
  industries: Industry[];
  stats: {
    industries: number;
    total_sources: number;
  };
  has_ai: boolean;
}

export interface WechatArticle {
  title: string;
  summary: string;
  url: string;
  date: string;
  dateLabel: string;
  category: string;
  readTime: string;
  cover: string;
  order: number;
  featured: boolean;
}

export interface WechatContent {
  accountName: string;
  accountId: string;
  tagline: string;
  description: string;
  qrImage: string;
  sourceAlbum: string;
  importedAt: string;
  articles: WechatArticle[];
}

export interface RefreshStatus {
  running: boolean;
  last_finished: string | null;
  last_ok: boolean | null;
  error: string;
  interval_hours: number;
  funds_last_ok?: boolean | null;
  funds_error?: string;
}

export interface EtfTrendPoint {
  date: string;
  total_shares: string | null;
  total_shares_10k: string | null;
  index_close: string | null;
}

export interface EtfBenchmark {
  code: string;
  name: string;
  supported: boolean;
  note: string;
}

export interface EtfFundItem {
  date: string;
  fund_code: string;
  fund_name: string;
  fund_expansion_abbr: string;
  etf_type: string;
  rank: number;
  closing_price: string;
  total_shares: string;
  estimated_total_amount: string;
  source_url: string;
  fetched_at: string;
  benchmark: EtfBenchmark;
  history: EtfTrendPoint[];
}

export interface EtfComparisonIndex {
  code: string;
  name: string;
  history: Array<{
    date: string;
    close: string | null;
  }>;
}

export interface EtfDashboard {
  latest_date: string;
  range: {
    start_date: string;
    end_date: string;
    trading_days: number;
    max_trading_days: number;
  };
  comparison_indices: EtfComparisonIndex[];
  items: EtfFundItem[];
}
