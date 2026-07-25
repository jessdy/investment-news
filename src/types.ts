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
}
