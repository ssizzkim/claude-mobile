/**
 * Demo dataset for K-POP Comeback Radar.
 * All numbers are fictional placeholders for demo/testing — not real chart data.
 * The app ships in "demo mode" only: no external API keys, no network calls.
 */
const RADAR_DATA = {
  artists: [
    {
      id: "boynextdoor",
      name: "BOYNEXTDOOR",
      emoji: "🏠",
      type: "group",
      members: 6,
      genre: "팝 (Pop)",
      catalogAlbums: 11,
      latestRelease: { title: "Demo Single Vol.4", date: "2026-06-12", kind: "Single" },
      latestVideo: { title: "Official Demo MV", channel: "Demo Ent.", date: "2026-06-12", views: "2.4M" },
      score: 41,
      status: { label: "관심도 관찰 중", tier: "watch" },
      signals: { recency: 62, youtube: 38, catalog: 55, news: 21, sentiment: 47 },
      history: [
        { date: "2026-01", score: 18 },
        { date: "2026-02", score: 22 },
        { date: "2026-03", score: 29 },
        { date: "2026-04", score: 33 },
        { date: "2026-05", score: 36 },
        { date: "2026-06", score: 41 }
      ],
      timeline: [
        { date: "2026-06-12", label: "Demo Single Vol.4 발매", tag: "now" },
        { date: "2026-03-02", label: "컴백 티저 공개" },
        { date: "2025-11-18", label: "Demo Single Vol.3 발매" }
      ]
    },
    {
      id: "riverline",
      name: "RIVERLINE",
      emoji: "🌊",
      type: "group",
      members: 5,
      genre: "댄스 팝 (Dance Pop)",
      catalogAlbums: 6,
      latestRelease: { title: "Demo EP: Tideway", date: "2026-07-01", kind: "EP" },
      latestVideo: { title: "Tideway Concept Film", channel: "Demo Ent.", date: "2026-07-01", views: "980K" },
      score: 68,
      status: { label: "컴백 신호 강함", tier: "hot" },
      signals: { recency: 91, youtube: 74, catalog: 40, news: 63, sentiment: 72 },
      history: [
        { date: "2026-02", score: 24 },
        { date: "2026-03", score: 31 },
        { date: "2026-04", score: 40 },
        { date: "2026-05", score: 52 },
        { date: "2026-06", score: 61 },
        { date: "2026-07", score: 68 }
      ],
      timeline: [
        { date: "2026-07-01", label: "Tideway EP 발매", tag: "now" },
        { date: "2026-05-20", label: "프리 싱글 공개" },
        { date: "2026-01-09", label: "Demo Album Vol.1 발매" }
      ]
    },
    {
      id: "solayoung",
      name: "SOLA (솔로)",
      emoji: "✨",
      type: "solo",
      members: 1,
      genre: "R&B / 솔로",
      catalogAlbums: 3,
      latestRelease: { title: "Demo Single: Afterglow", date: "2026-05-22", kind: "Single" },
      latestVideo: { title: "Afterglow Live Session", channel: "Demo Ent.", date: "2026-05-24", views: "410K" },
      score: 29,
      status: { label: "저조 구간, 관찰 중", tier: "cold" },
      signals: { recency: 47, youtube: 22, catalog: 18, news: 14, sentiment: 33 },
      history: [
        { date: "2026-01", score: 12 },
        { date: "2026-02", score: 15 },
        { date: "2026-03", score: 19 },
        { date: "2026-04", score: 24 },
        { date: "2026-05", score: 29 },
        { date: "2026-06", score: 27 }
      ],
      timeline: [
        { date: "2026-05-22", label: "Afterglow 발매", tag: "now" },
        { date: "2025-12-03", label: "피처링 트랙 공개" }
      ]
    }
  ],

  signalLabels: {
    recency: "발매 최신성",
    youtube: "YouTube 반응",
    catalog: "Apple 카탈로그",
    news: "뉴스 버즈",
    sentiment: "AI 감성 지수"
  },

  apiConnections: [
    { key: "apple", label: "Apple Music (iTunes Search)", note: "키 불필요", status: "good" },
    { key: "youtube", label: "YouTube Data API", note: "demo key", status: "good" },
    { key: "mediastack", label: "Mediastack (글로벌 뉴스)", note: "demo key", status: "good" },
    { key: "naver", label: "Naver News API", note: "demo key", status: "good" },
    { key: "solar", label: "Upstage Solar (AI 채팅)", note: "데모 응답", status: "warning" }
  ]
};
