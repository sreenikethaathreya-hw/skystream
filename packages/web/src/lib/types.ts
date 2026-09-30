import type { Flag, Impact, SegmentContext, Thresholds } from "./mathTypes";

export type Role = "rep" | "lead" | "admin";

export interface DemoUser {
  id: string;
  name: string;
  role: Role;
  title: string;
}

export interface AiStatus {
  mode: string;
  jevConfigured: boolean;
  jevModel: string;
  geminiConfigured: boolean;
  geminiModel: string;
}

export type DataMode = "demo" | "real";

export interface AppConfig {
  dataMode: DataMode;
  firebase: { apiKey: string; authDomain: string; projectId: string } | null;
}

export interface Meta {
  dataMode: DataMode;
  me: DemoUser;
  users: DemoUser[];
  clock: { year: number; month: number } | null;
  ai: AiStatus & { externalAiAllowed: boolean };
  thresholds: Thresholds;
  currency: string;
}

export interface ScopeOption {
  countryCode: string;
  countryName: string;
  species: string | null;
  megaSegmentId: string;
  megaSegmentDesc: string;
  segments: number;
}

export interface Scope {
  countryCode: string;
  megaSegmentId: string;
}

export interface MonthEntry {
  id: string;
  month: number;
  value: number;
  low: number;
  high: number;
  status: string;
  userId: string;
}

export interface SegmentCube {
  id: number;
  label: string;
  description: string;
  color: string | null;
  profile: string;
  editable: boolean;
  ownerNames: string[];
  planBasis: string;
  lastYearBasis: string;
  planComment: string | null;
  marketNotes: Record<string, string | null>;
  context: SegmentContext;
  latestEntries: MonthEntry[];
}

export interface CompetitorRow {
  name: string;
  sharePct: number;
  trend: string | null;
}

export interface Cube {
  countryCode: string;
  countryName: string;
  megaSegmentId: string;
  megaSegmentDesc: string;
  species: string | null;
  currency: string;
  year: number;
  clockMonth: number;
  yearClosed: boolean;
  thresholds: Thresholds;
  competitors: CompetitorRow[];
  varieties: string[];
  segments: SegmentCube[];
}

export interface DecisionAnswer {
  type: "choice" | "score" | "noul";
  choice?: string | null;
  confidence?: number | null;
  probabilities?: Record<string, number> | null;
  score?: number | null;
  noul?: number | null;
}

export interface StructuredClaim {
  driver: string;
  direction: string;
  magnitude: number | null;
  magnitudeLabel: string | null;
  competitor: string | null;
  variety: string | null;
  evidenceSource: string | null;
  verifiable: number | null;
  consistentWithNotes: number | null;
  specificity: number | null;
  specificityLabel: string | null;
  addressesFlags: number | null;
  summary: string;
  provider: string;
  model: string | null;
  lowConfidenceFields: string[];
  decisions: Record<string, DecisionAnswer>;
  latencyMs: number;
  mismatches: Flag[];
}

export interface AnalyzeResult {
  impact: Impact;
  flags: Flag[];
  claim: StructuredClaim | null;
}

export interface ResolutionDetail {
  actual: number;
  plan: number;
  inRange: boolean;
  errorPct: number | null;
  supportedProbability: number;
  numericSupport: boolean;
  provider: string;
  evidence: string;
}

export interface ClaimOut {
  driver: string;
  direction: string;
  magnitude: number | null;
  competitor: string | null;
  variety: string | null;
  evidenceSource: string | null;
  verifiable: number | null;
  consistentWithNotes: number | null;
  specificity: number | null;
  addressesFlags: number | null;
  summary: string | null;
  provider: string;
  signal: string;
  checkYear: number;
  checkMonth: number;
  resolution: "pending" | "confirmed" | "contradicted" | "inconclusive";
  resolutionDetail: ResolutionDetail | null;
  decisions: Record<string, DecisionAnswer>;
}

export interface TriageDecision {
  choice: "approve" | "discuss" | "challenge";
  confidence: number;
  probabilities: Record<string, number>;
  provider: string;
}

export interface Entry {
  id: string;
  userId: string;
  userName: string;
  countryCode: string;
  segmentId: number;
  segmentLabel: string;
  year: number;
  month: number;
  value: number;
  low: number;
  high: number;
  price: number | null;
  justification: string | null;
  impact: Impact | null;
  flags: Flag[];
  status: string;
  source: "live" | "history";
  triage: TriageDecision | null;
  reviewedBy: string | null;
  createdAt: string;
  claim: ClaimOut | null;
}

export interface EntryPayload {
  countryCode: string;
  segmentId: number;
  month: number;
  value: number;
  low: number;
  high: number;
  price?: number | null;
  justification?: string | null;
}

export interface TrackRecord {
  user: DemoUser;
  entriesResolved: number;
  biasPct: number | null;
  claimHitRate: number | null;
  rangeCoverage: number | null;
  confirmed: number;
  contradicted: number;
  weak: boolean;
}

export interface ResolvedClaim {
  entryId: string;
  segmentLabel: string;
  userName: string;
  resolution: string;
  actual: number;
  value: number;
  inRange: boolean;
  supportedProbability: number;
  provider: string;
}

export interface AdvanceResult {
  fromMonth: number;
  toMonth: number;
  resolved: ResolvedClaim[];
  confirmed: number;
  contradicted: number;
  inconclusive: number;
}

export interface QueueItem {
  entry: Entry;
  reasons: string[];
}

export interface Queue {
  exceptions: QueueItem[];
  routine: Entry[];
}

export interface Rtb {
  segmentId: number;
  text: string;
  provider: string;
  citedEntryIds: string[];
}

export type DataQuality = Record<string, Record<string, unknown>>;

export interface UploadKind {
  kind: string;
  label: string;
  source: string;
  required: boolean;
  template: boolean;
  lastCommittedAt: string | null;
}

export interface UploadReport {
  kind: string;
  rowsRead?: number;
  accepted?: number;
  rejected?: number;
  rejects?: { row: number; reason: string }[];
  rejectsTruncated?: boolean;
  warnings?: { message: string; count: number }[];
  info?: Record<string, unknown>;
  countries?: string[];
  error?: string;
}

export interface UploadBatch {
  id: string;
  kind: string;
  filename: string;
  uploadedBy: string;
  status: "previewed" | "committed" | "discarded" | "superseded" | "failed";
  rowsRead: number;
  accepted: number;
  rejected: number;
  warnings: number;
  report: UploadReport;
  commitSummary: Record<string, unknown> | null;
  createdAt: string;
  committedAt: string | null;
}

export interface UserScope {
  countryCode: string;
  scopeType: "mega" | "micro";
  scopeId: string;
}

export interface AdminUser {
  email: string;
  name: string;
  role: Role | "admin";
  active: boolean;
  lastSeenAt: string | null;
  scopes: UserScope[];
}

export interface AppSettings {
  currentYear: number;
  thresholds: Thresholds;
  jevConfidenceThreshold: number;
  jevScoreConfidenceThreshold: number;
  growerHaCap: number;
  externalAiAllowed: boolean;
  currency: string;
}
