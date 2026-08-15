import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type Language = "zh" | "en";
export const LANGUAGE_STORAGE_KEY = "paper-rag-workbench-language";

const enMessages = {
  "nav.overview": "Overview",
  "nav.health": "Health",
  "nav.library": "Library",
  "nav.search": "Search",
  "nav.ask": "Ask",
  "nav.discover": "Discover",
  "nav.dsh": "DSH Chat",
  "nav.aria": "Workbench navigation",
  "language.zh": "中",
  "language.en": "EN",
  "language.aria": "Interface language",
  "overview.title": "Overview",
  "overview.subtitle": "Corpus status, model readiness, and quick actions.",
  "overview.openDsh": "Open DSH Chat",
  "overview.papers": "Papers",
  "overview.chunks": "Chunks",
  "overview.model": "Model",
  "overview.credentials": "Credentials",
  "overview.configured": "Configured",
  "overview.missing": "Missing",
  "overview.loading": "Loading overview...",
  "overview.unavailable": "Overview unavailable",
  "health.title": "Health",
  "health.subtitle": "Inspect corpus readiness, retrieval fallback, model configuration, and data quality.",
  "health.indexTitle": "Index Health",
  "health.qualityIssues": "Quality Issues",
  "health.sendToDsh": "Send diagnostics to DSH",
  "health.loadingTitle": "Loading health",
  "health.loadingDetail": "Checking local indexes.",
  "health.unavailable": "Health unavailable",
  "health.chunkCount": "{count} chunks",
  "library.title": "Library",
  "library.subtitle": "Inspect indexed papers and open source sections without writing to the corpus.",
  "library.filter": "Filter papers",
  "library.loading": "Loading library...",
  "library.unavailable": "Library unavailable",
  "library.sectionUnavailable": "Section is unavailable.",
  "library.introduction": "Introduction",
  "search.title": "Search",
  "search.subtitle": "Retrieve source chunks before asking the model to synthesize.",
  "search.evidence": "Search evidence",
  "search.topK": "Top K",
  "search.submit": "Search",
  "search.loading": "Searching...",
  "search.unavailable": "Search unavailable",
  "search.resultsAria": "Search results",
  "search.sendToDsh": "Send search to DSH",
  "ask.title": "Ask",
  "ask.subtitle": "Ask grounded questions and inspect the evidence used for each answer.",
  "ask.question": "Question",
  "ask.paperIds": "Paper IDs",
  "ask.topK": "Top K",
  "ask.submit": "Ask",
  "ask.loading": "Asking...",
  "ask.unavailable": "Answer unavailable",
  "ask.copyPrompt": "Copy prompt for DSH",
  "ask.sendToDsh": "Send to DSH",
  "ask.copied": "Copied",
  "discover.title": "Discover",
  "discover.subtitle": "Find candidate papers, then explicitly approve any ingest side effects.",
  "discover.topic": "Topic",
  "discover.sources": "Sources",
  "discover.maxCandidates": "Max candidates",
  "discover.submit": "Discover",
  "discover.loading": "Discovering...",
  "discover.unavailable": "Discovery unavailable",
  "discover.ingestSelected": "Ingest selected",
  "discover.selectedCount": "{count} selected",
  "discover.receipt": "Ingest receipt",
  "discover.ingesting": "Ingesting approved candidates...",
  "answer.title": "Answer",
  "answer.noCitations": "No citations",
  "answer.citationsAria": "Citations",
  "timeline.title": "Agent Timeline",
  "timeline.running": "running",
  "approval.title": "Approve candidate ingest",
  "approval.candidateIds": "Candidate ids: {ids}",
  "approval.cancel": "Cancel",
  "approval.approve": "Approve ingest",
  "approval.effect.write": "write indexed paper and chunks",
  "approval.effect.update": "update the configured Paper RAG corpus",
  "approval.effect.record": "record ingestion metadata",
  "candidate.select": "Select",
  "candidate.candidate": "Candidate",
  "candidate.source": "Source",
  "candidate.rank": "Rank",
  "candidate.evidence": "Evidence",
  "candidate.notEvidence": "Candidate-only; not answer evidence",
  "paperDetail.sections": "Sections",
  "paperDetail.chunks": "Chunks",
  "paperDetail.unknownSection": "Unknown section",
  "chunkDetail.openPaper": "Open paper detail",
  "chunkDetail.paper": "Paper",
  "chunkDetail.section": "Section",
  "chunkDetail.page": "Page",
  "chunkDetail.unknown": "unknown",
  "chunkDetail.nearby": "Nearby chunks",
  "chunk.page": "Page {page}",
  "chunk.source": "source",
  "chunk.score": "score {score}",
  "quality.empty": "No quality samples detected.",
  "quality.kind": "Kind",
  "quality.paper": "Paper",
  "quality.chunks": "Chunks",
  "quality.preview": "Preview",
  "handoff.title": "Send to DSH",
  "handoff.close": "Close DSH handoff",
  "handoff.copy": "Copy prompt",
  "handoff.open": "Open DSH",
} as const;

export type MessageKey = keyof typeof enMessages;

const zhMessages = {
  "nav.overview": "概览",
  "nav.health": "健康检查",
  "nav.library": "论文库",
  "nav.search": "检索",
  "nav.ask": "问答",
  "nav.discover": "发现",
  "nav.dsh": "DSH 对话",
  "nav.aria": "工作台导航",
  "language.zh": "中",
  "language.en": "EN",
  "language.aria": "界面语言",
  "overview.title": "概览",
  "overview.subtitle": "查看语料库状态、模型就绪度和快捷操作。",
  "overview.openDsh": "打开 DSH 对话",
  "overview.papers": "论文",
  "overview.chunks": "分块",
  "overview.model": "模型",
  "overview.credentials": "凭据",
  "overview.configured": "已配置",
  "overview.missing": "缺失",
  "overview.loading": "正在加载概览...",
  "overview.unavailable": "概览不可用",
  "health.title": "健康检查",
  "health.subtitle": "检查语料库就绪度、检索降级、模型配置和数据质量。",
  "health.indexTitle": "索引健康",
  "health.qualityIssues": "质量问题",
  "health.sendToDsh": "发送诊断到 DSH",
  "health.loadingTitle": "正在加载健康检查",
  "health.loadingDetail": "正在检查本地索引。",
  "health.unavailable": "健康检查不可用",
  "health.chunkCount": "{count} 个分块",
  "library.title": "论文库",
  "library.subtitle": "查看已索引论文并读取原文章节，不写入语料库。",
  "library.filter": "筛选论文",
  "library.loading": "正在加载论文库...",
  "library.unavailable": "论文库不可用",
  "library.sectionUnavailable": "章节不可用。",
  "library.introduction": "引言",
  "search.title": "检索",
  "search.subtitle": "先检索原文证据，再让模型综合回答。",
  "search.evidence": "检索证据",
  "search.topK": "Top K",
  "search.submit": "检索",
  "search.loading": "检索中...",
  "search.unavailable": "检索不可用",
  "search.resultsAria": "检索结果",
  "search.sendToDsh": "发送检索到 DSH",
  "ask.title": "问答",
  "ask.subtitle": "提出基于论文的问题，并检查每个回答使用的证据。",
  "ask.question": "问题",
  "ask.paperIds": "论文 ID",
  "ask.topK": "Top K",
  "ask.submit": "提问",
  "ask.loading": "回答中...",
  "ask.unavailable": "回答不可用",
  "ask.copyPrompt": "复制 DSH 提示词",
  "ask.sendToDsh": "发送到 DSH",
  "ask.copied": "已复制",
  "discover.title": "发现",
  "discover.subtitle": "查找候选论文，并在任何入库副作用前显式批准。",
  "discover.topic": "主题",
  "discover.sources": "来源",
  "discover.maxCandidates": "候选数量上限",
  "discover.submit": "发现",
  "discover.loading": "发现中...",
  "discover.unavailable": "发现不可用",
  "discover.ingestSelected": "入库所选",
  "discover.selectedCount": "已选择 {count} 项",
  "discover.receipt": "入库回执",
  "discover.ingesting": "正在入库已批准候选...",
  "answer.title": "回答",
  "answer.noCitations": "无引用",
  "answer.citationsAria": "引用",
  "timeline.title": "执行轨迹",
  "timeline.running": "运行中",
  "approval.title": "批准候选入库",
  "approval.candidateIds": "候选 ID：{ids}",
  "approval.cancel": "取消",
  "approval.approve": "批准入库",
  "approval.effect.write": "写入索引论文和分块",
  "approval.effect.update": "更新已配置的 Paper RAG 语料库",
  "approval.effect.record": "记录入库元数据",
  "candidate.select": "选择",
  "candidate.candidate": "候选论文",
  "candidate.source": "来源",
  "candidate.rank": "排名",
  "candidate.evidence": "证据",
  "candidate.notEvidence": "候选项；不是回答证据",
  "paperDetail.sections": "章节",
  "paperDetail.chunks": "分块",
  "paperDetail.unknownSection": "未知章节",
  "chunkDetail.openPaper": "打开论文详情",
  "chunkDetail.paper": "论文",
  "chunkDetail.section": "章节",
  "chunkDetail.page": "页码",
  "chunkDetail.unknown": "未知",
  "chunkDetail.nearby": "附近分块",
  "chunk.page": "第 {page} 页",
  "chunk.source": "来源",
  "chunk.score": "得分 {score}",
  "quality.empty": "未检测到质量样本。",
  "quality.kind": "类型",
  "quality.paper": "论文",
  "quality.chunks": "分块",
  "quality.preview": "预览",
  "handoff.title": "发送到 DSH",
  "handoff.close": "关闭 DSH 交接",
  "handoff.copy": "复制提示词",
  "handoff.open": "打开 DSH",
} as const satisfies Record<MessageKey, string>;

export const messages = {
  en: enMessages,
  zh: zhMessages,
} as const;

type MessageVars = Record<string, string | number>;

type I18nValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: MessageKey, vars?: MessageVars) => string;
};

const I18nContext = createContext<I18nValue | null>(null);

export function resolveInitialLanguage(storageValue: string | null): Language {
  return storageValue === "en" || storageValue === "zh" ? storageValue : "zh";
}

export function formatMessage(template: string, vars?: MessageVars): string {
  if (!vars) return template;
  return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (match, name) => {
    const value = vars[name];
    return value === undefined ? match : String(value);
  });
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() =>
    resolveInitialLanguage(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)),
  );

  const value = useMemo<I18nValue>(() => {
    const setLanguage = (nextLanguage: Language) => {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
      setLanguageState(nextLanguage);
    };

    return {
      language,
      setLanguage,
      t: (key, vars) => formatMessage(messages[language][key], vars),
    };
  }, [language]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return value;
}
