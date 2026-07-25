import {
  Alert,
  Button,
  Card,
  Chip,
  Link,
  Modal,
  Spinner,
} from "@heroui/react";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {useLocation, useNavigate} from "react-router-dom";

import {fetchDashboard, fetchRefreshStatus} from "./api";
import qrCode from "../docs/shengcai-youdao-qr.jpg";
import type {
  Industry,
  NewsData,
  WechatArticle,
  WechatContent,
} from "./types";

type View = "news" | "analysis";

const ROUTE_SEO: Record<View, {title: string; description: string}> = {
  news: {
    title: "产业资讯｜全球产业链最新动态与 AI 关键信号 - 生财佑道",
    description:
      "聚合全球权威信源，追踪人工智能、机器人、半导体等重点产业链动态，并提炼每日关键产业信号。",
  },
  analysis: {
    title: "产业分析｜AI、机器人与科技趋势深度研究 - 生财佑道",
    description:
      "生财佑道原创产业分析，深度解读人工智能、机器人、科技创新与商业趋势，提供长期产业研究视角。",
  },
};

const EMPTY_WECHAT: WechatContent = {
  accountName: "生财佑道",
  accountId: "",
  tagline: "关注 AI、机器人与产业智能的长期趋势",
  description: "汇集原创产业观察，以长期视角理解技术与商业趋势。",
  qrImage: "",
  sourceAlbum: "",
  importedAt: "",
  articles: [],
};

function externalUrl(value?: string) {
  return /^https?:\/\//i.test(value ?? "") ? value : undefined;
}

function assetUrl(value?: string) {
  if (!value) return undefined;
  if (/^https?:\/\//i.test(value)) return value;
  if (value.includes("shengcai-youdao-qr.jpg")) return qrCode;
  return undefined;
}

function setMeta(name: string, content: string, property = false) {
  const attribute = property ? "property" : "name";
  let element = document.head.querySelector<HTMLMetaElement>(
    `meta[${attribute}="${name}"]`,
  );
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute(attribute, name);
    document.head.appendChild(element);
  }
  element.content = content;
}

function useRouteSeo(view: View) {
  useEffect(() => {
    const seo = ROUTE_SEO[view];
    const canonicalUrl = `${window.location.origin}/${view}`;
    document.title = seo.title;
    setMeta("description", seo.description);
    setMeta("og:title", seo.title, true);
    setMeta("og:description", seo.description, true);
    setMeta("og:url", canonicalUrl, true);
    setMeta("twitter:card", "summary_large_image");

    let canonical = document.head.querySelector<HTMLLinkElement>(
      'link[rel="canonical"]',
    );
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.rel = "canonical";
      document.head.appendChild(canonical);
    }
    canonical.href = canonicalUrl;
  }, [view]);
}

function LoginModal() {
  return (
    <Modal>
      <Modal.Trigger>
        <Button className="login-btn" variant="ghost">
          <span className="avatar-dot">微</span>
          <span className="login-label">微信登录</span>
        </Button>
      </Modal.Trigger>
      <Modal.Backdrop className="login-backdrop">
        <Modal.Container placement="center" size="sm">
          <Modal.Dialog className="login-card">
            <Modal.Header className="login-top">
              <Modal.Heading id="loginTitle">微信扫码登录</Modal.Heading>
              <Modal.CloseTrigger className="close-btn" aria-label="关闭" />
            </Modal.Header>
            <Modal.Body className="wechat-login-body">
              <div className="wechat-icon">微信</div>
              <h3>使用微信扫码登录</h3>
              <p>打开微信，使用“扫一扫”完成安全登录</p>
              <div className="login-qr">
                <div className="login-qr-inner">
                  登录二维码
                  <br />
                  等待接入微信开放平台
                </div>
              </div>
              <div className="scan-status">
                <span className="pulse" />
                <span>登录服务尚未配置</span>
              </div>
              <div className="login-note">
                需要配置微信开放平台 AppID、授权回调域名及服务端会话接口后，系统才会生成真实登录二维码。
              </div>
            </Modal.Body>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
  );
}

interface HeaderProps {
  view: View;
  updateLabel: string;
  onViewChange: (view: View) => void;
}

function Header({view, updateLabel, onViewChange}: HeaderProps) {
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="identity">
          <div className="brand-mark" aria-hidden="true" />
          <div>
            <div className="brand-name">生财佑道产业资讯</div>
            <div className="brand-tagline">INDUSTRY INTELLIGENCE</div>
          </div>
        </div>
        <nav className="topnav" aria-label="主导航">
          <Button
            className={view === "news" ? "active" : ""}
            variant="ghost"
            onPress={() => onViewChange("news")}
          >
            产业资讯
          </Button>
          <Button
            className={view === "analysis" ? "active" : ""}
            variant="ghost"
            onPress={() => onViewChange("analysis")}
          >
            产业分析
          </Button>
        </nav>
        <div className="top-actions">
          <span className="update-state">{updateLabel}</span>
          <Chip className="auto-refresh" color="success" variant="soft">
            每 6 小时自动更新
          </Chip>
          <LoginModal />
        </div>
      </div>
    </header>
  );
}

interface SidebarProps {
  data: NewsData;
  activeKey: string;
  onSelect: (key: string) => void;
}

function Sidebar({data, activeKey, onSelect}: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="side-intro">
        <div className="eyebrow">Sector Monitor</div>
        <h2>产业观察</h2>
        <p>追踪全球产业链领先信号</p>
      </div>
      <div className="side-rule" />
      <nav className="sector-nav" aria-label="产业赛道">
        {data.industries.map((industry) => (
          <Button
            key={industry.key}
            className={`sector-item ${activeKey === industry.key ? "active" : ""}`}
            variant="ghost"
            onPress={() => onSelect(industry.key)}
          >
            <span className="bar" style={{background: industry.accent}} />
            <span className="nm">{industry.name}</span>
            <span className="cnt">{industry.items.length}</span>
          </Button>
        ))}
      </nav>
      <Card className="side-follow">
        <img src={qrCode} alt="生财佑道公众号二维码" />
        <div className="side-follow-copy">
          <span>微信公众号</span>
          <strong>生财佑道</strong>
          <small>
            微信扫码关注
            <br />
            获取产业深度内容
          </small>
        </div>
      </Card>
      <div className="side-foot">
        <span className="source-stat">{data.stats.total_sources} 个权威源</span>
        <br />
        {data.industries.length} 个重点产业赛道
        <br />
        仅供产业研究参考，不构成投资建议
      </div>
    </aside>
  );
}

function Digest({industry}: {industry: Industry}) {
  if (!industry.points.length) return null;
  return (
    <Card className="digest">
      <Card.Header className="digest-head">
        <span
          className="symbol"
          style={{background: `${industry.accent}1f`, color: industry.accent}}
        >
          ◆
        </span>
        <h3>今日产业研判</h3>
        <span>AI 多源提炼 · {industry.points.length} 项关键信号</span>
      </Card.Header>
      <Card.Content>
        <ol className="digest-list">
          {industry.points.map((point, index) => (
            <li key={`${point.t}-${index}`}>
              <span className="index">{String(index + 1).padStart(2, "0")}</span>
              <span className="point">{point.t}</span>
              {externalUrl(point.url) && (
                <Link href={point.url} target="_blank" rel="noopener noreferrer">
                  查看原文 ↗
                </Link>
              )}
            </li>
          ))}
        </ol>
      </Card.Content>
    </Card>
  );
}

function NewsView({data, industry}: {data: NewsData; industry: Industry}) {
  return (
    <>
      <header className="page-head">
        <div className="page-head-inner">
          <div className="breadcrumb">
            产业资讯 <span>›</span> <b>{industry.name}</b>
          </div>
          <div className="title-line">
            <h1>{industry.name}</h1>
            <Chip
              className="status-chip"
              size="sm"
              variant="soft"
              style={{background: `${industry.accent}1a`, color: industry.accent}}
            >
              持续跟踪
            </Chip>
          </div>
          <div className="head-sub">
            <span><strong>{industry.total}</strong> 个信息源</span>
            <span className="sep" />
            <span><strong>{industry.items.length}</strong> 条有效资讯</span>
            <span className="sep" />
            <span>观察窗口：最近 {data.recent_days || 120} 天</span>
            <span className="sep" />
            <span>北京时间 {data.generated_at || "—"}</span>
          </div>
        </div>
      </header>
      <div className="content">
        <Digest industry={industry} />
        <div className="section-bar">
          <h3>资讯明细</h3>
          <p>按发布时间倒序排列</p>
          <span className="legend">点击标题查看原始信源</span>
        </div>
        {industry.items.length ? (
          <div className="news-list">
            {industry.items.map((item, index) => {
              const translated = item.zh?.trim();
              const title = translated || item.title;
              const secondary = translated ? item.title : item.summary;
              const url = externalUrl(item.url);
              return (
                <Card className="news-row" key={`${item.url}-${index}`}>
                  <span className="signal" style={{background: industry.accent}} />
                  <div className="news-body">
                    {url ? (
                      <Link
                        className="news-title"
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {title}
                      </Link>
                    ) : (
                      <span className="news-title">{title}</span>
                    )}
                    {secondary && <div className="news-en">{secondary}</div>}
                  </div>
                  <Chip
                    className="source"
                    size="sm"
                    variant="soft"
                    style={{background: `${industry.accent}1a`, color: industry.accent}}
                  >
                    {item.source}
                  </Chip>
                  <time className="time">{item.time || "—"}</time>
                </Card>
              );
            })}
          </div>
        ) : (
          <div className="empty">该行业暂未抓到有效资讯</div>
        )}
      </div>
    </>
  );
}

function ArticleLead({article}: {article: WechatArticle}) {
  const cover = assetUrl(article.cover);
  if (cover) {
    return (
      <span className="article-cover">
        <img src={cover} alt="" loading="lazy" referrerPolicy="no-referrer" />
      </span>
    );
  }
  const match = article.date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const relative = article.dateLabel || "";
  const day = match ? match[3] : relative === "昨天" ? "昨" : relative.match(/^\d+/)?.[0] || "文";
  const month = match ? `${match[1]}.${match[2]}` : relative === "昨天" ? "天" : relative.replace(/^\d+/, "") || "NEW";
  return (
    <span className="article-date">
      <b>{day}</b>
      <span>{month}</span>
    </span>
  );
}

function AnalysisView({wechat}: {wechat: WechatContent}) {
  const account = wechat.accountName || "生财佑道";
  const articles = useMemo(
    () =>
      [...wechat.articles]
        .filter((article) => article.title && externalUrl(article.url))
        .sort((a, b) => b.order - a.order || b.date.localeCompare(a.date)),
    [wechat.articles],
  );
  const copyAccount = async () => {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(account);
    } else {
      window.prompt("复制公众号名称", account);
    }
  };

  return (
    <div className="analysis-wrap">
      <section className="analysis-hero">
        <div>
          <div className="eyebrow">Original Insights</div>
          <h1>产业深度 · 原创分析</h1>
          <p>{wechat.description || EMPTY_WECHAT.description}</p>
        </div>
        <div className="analysis-brand">
          微信公众号
          <b>{account}</b>
          {wechat.tagline}
        </div>
      </section>
      <div className="article-layout">
        <Card className="article-panel">
          <Card.Header className="article-panel-head">
            <h3>最新文章</h3>
            <span>公众号原创内容</span>
            <em>共 {articles.length} 篇</em>
          </Card.Header>
          {articles.length ? (
            <Card.Content className="article-list">
              {articles.map((article, index) => (
                <Link
                  className="article-card"
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  key={`${article.url}-${index}`}
                >
                  <ArticleLead article={article} />
                  <span className="article-main">
                    <span className="article-meta">
                      <Chip size="sm" variant="soft" className="article-category">
                        {article.category || "产业观察"}
                      </Chip>
                      <span>{article.readTime || "深度阅读"}</span>
                      {article.featured && <span>· 编辑推荐</span>}
                    </span>
                    <span className="article-title">{article.title}</span>
                    <span className="article-summary">
                      {article.summary || "点击进入微信公众号阅读完整文章"}
                    </span>
                  </span>
                  <span className="article-arrow">›</span>
                </Link>
              ))}
            </Card.Content>
          ) : (
            <Card.Content className="article-empty">
              <div className="empty-mark">文</div>
              <h3>公众号文章正在整理</h3>
              <p>文章列表已经独立配置完成，添加公众号原文后会自动展示。</p>
            </Card.Content>
          )}
        </Card>
        <Card className="follow-card">
          <div className="follow-cover">
            <div className="follow-logo">财</div>
            <h3>{account}</h3>
            <p>微信公众号 · 产业深度内容</p>
          </div>
          <Card.Content className="follow-body">
            <div className="qr-placeholder">
              <img src={assetUrl(wechat.qrImage) || qrCode} alt={`${account}公众号二维码`} />
            </div>
            <strong>关注公众号，获取持续更新</strong>
            <p>{wechat.tagline || EMPTY_WECHAT.tagline}</p>
            <Button className="copy-account" variant="secondary" onPress={copyAccount}>
              复制公众号名称
            </Button>
            <div className="follow-guide">
              <div><b>01</b>打开微信，点击顶部搜索</div>
              <div><b>02</b>搜索“{account}”并进入公众号</div>
              <div><b>03</b>点击关注，及时获取深度文章</div>
            </div>
          </Card.Content>
        </Card>
      </div>
    </div>
  );
}

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState<NewsData | null>(null);
  const [wechat, setWechat] = useState<WechatContent>(EMPTY_WECHAT);
  const [activeKey, setActiveKey] = useState("");
  const [error, setError] = useState("");
  const [updateLabel, setUpdateLabel] = useState("数据准备中");
  const observedRefresh = useRef(sessionStorage.getItem("refresh-finished") || "");
  const view: View = location.pathname === "/analysis" ? "analysis" : "news";
  useRouteSeo(view);

  const loadDashboard = useCallback(async (signal?: AbortSignal) => {
    const [newsData, wechatData] = await fetchDashboard(signal);
    setData(newsData);
    setWechat(wechatData);
    setActiveKey((current) => current || newsData.industries[0]?.key || "");
    setUpdateLabel(`更新于 ${newsData.generated_at || "—"}`);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadDashboard(controller.signal).catch((loadError: unknown) => {
      if (!controller.signal.aborted) {
        setError(loadError instanceof Error ? loadError.message : "数据库数据加载失败");
      }
    });
    return () => controller.abort();
  }, [loadDashboard]);

  useEffect(() => {
    if (!data) return;
    let disposed = false;
    const checkStatus = async () => {
      try {
        const status = await fetchRefreshStatus();
        if (disposed) return;
        if (status.running) setUpdateLabel("后台正在更新数据…");
        else if (status.last_ok === false) setUpdateLabel("上次自动更新失败");
        else setUpdateLabel(`更新于 ${data.generated_at || "—"}`);
        if (status.last_finished && status.last_finished !== observedRefresh.current) {
          observedRefresh.current = status.last_finished;
          sessionStorage.setItem("refresh-finished", status.last_finished);
          if (status.last_ok) window.location.reload();
        }
      } catch {
        // 状态接口不可用时保留最近一次更新时间。
      }
    };
    void checkStatus();
    const timer = window.setInterval(checkStatus, 60_000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [data]);

  const activeIndustry =
    data?.industries.find((industry) => industry.key === activeKey) ??
    data?.industries[0];

  if (error) {
    return (
      <main className="state-page">
        <Alert status="danger">
          <Alert.Content>
            <Alert.Title>产业数据加载失败</Alert.Title>
            <Alert.Description>{error}，请稍后重试。</Alert.Description>
          </Alert.Content>
        </Alert>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="state-page loading-state">
        <Spinner size="lg" color="accent" />
        <span>正在载入产业数据…</span>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <Header
        view={view}
        updateLabel={updateLabel}
        onViewChange={(nextView) => navigate(`/${nextView}`)}
      />
      <div className={`workspace ${view === "analysis" ? "analysis-mode" : ""}`}>
        {view === "news" && (
          <Sidebar
            data={data}
            activeKey={activeIndustry?.key || ""}
            onSelect={setActiveKey}
          />
        )}
        <main className="main">
          {view === "news" && activeIndustry ? (
            <NewsView data={data} industry={activeIndustry} />
          ) : (
            <AnalysisView wechat={wechat} />
          )}
        </main>
      </div>
    </div>
  );
}
