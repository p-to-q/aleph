import type { AlephRun, CandidatePoint, ObservationMode, TargetOutput } from "./types.ts";

export type Stratum = "S1" | "S2" | "S3" | "S4";
export type MetricClass = "exact" | "lexical" | "semantic" | "judge" | "execution";
export type BenchmarkTrack = "F";
export type BenchArtifactStatus = "ready" | "blocked";
export type BenchManifestEvidenceMode = ObservationMode | "unknown";
export type BenchBundleEvidenceMode = ObservationMode | "none";
export type BenchBundleArtifactRole = "result" | "manifest" | "audit" | "report" | "evidence_note";
export type BenchPlatformTarget = "huggingface_dataset" | "kaggle_dataset" | "croissant";
export type BenchPlatformArtifactRole = "data" | "docs" | "evidence" | "metadata" | "schemas";
export type BenchAuditStatus = "ok" | "failed";
export type BenchAuditCheckId =
  | "schema-valid"
  | "dataset-integrity"
  | "mock-only-audit"
  | "aleph-run-contract"
  | "exact-match"
  | "seed-0-reproducible"
  | "rank-stable"
  | "leakage-gate"
  | "iia"
  | "metric-reporting"
  | "evidence-note";

export type LeakageGateThresholds = {
  lcsRatio: number;
  trigramOverlap: number;
  verbatimSpanTokens: number;
};

export type LeakageGateResult = {
  disqualified: boolean;
  lcsRatio: number;
  trigramOverlap: number;
  verbatimSpanTokens: number;
  thresholds: LeakageGateThresholds;
};

export type LadderRung = 0 | 1 | 2 | 3;

export type FrozenLadderPrompt = {
  id: string;
  rung: LadderRung;
  paraphrase: 0 | 1;
  label: string;
  prompt: string;
  expectedLeakage?: "leaky_anchor" | "non_leaking_candidate";
};

export type BenchItem = {
  id: string;
  stratum: Stratum;
  language: string;
  target: TargetOutput;
  metricClass: MetricClass;
  frozenLadder: FrozenLadderPrompt[];
  canaryGuid: string;
  provenance: {
    createdBy: string;
    generatedAt: string;
    method: string;
    seed: number;
    parameters?: Record<string, string | number | boolean | string[] | number[]>;
  };
  license: string;
};

export type BenchFrontierPoint = CandidatePoint & {
  itemId: string;
  model: string;
  rung: LadderRung;
  paraphrase: 0 | 1;
  distortion: number;
  fidelity: number;
  rerunCount: number;
  fidelityVariance: number;
  fidelityStdDev: number;
  disqualified: boolean;
  leakageGate: LeakageGateResult;
  evidenceMode: ObservationMode;
};

export type ConfidenceInterval = {
  low: number;
  high: number;
};

export type BenchModelSummary = {
  model: string;
  evidenceMode: ObservationMode;
  itemCount: number;
  aurc: number;
  aurcCi95: ConfidenceInterval;
  eclAtTau: number | null;
  eclAtTauCi95: ConfidenceInterval | null;
  coverageAtTau: number;
  elicitAtK: number;
  elicitAtKCi95: ConfidenceInterval;
  leakageHitRate: number;
};

export type BenchItemModelRun = {
  itemId: string;
  model: string;
  alephRun: AlephRun;
  measurements: BenchPromptMeasurement[];
  frontier: BenchFrontierPoint[];
  metrics: {
    aurc: number;
    eclAtTau: number | null;
    elicitAtK: boolean;
    leakageHitRate: number;
  };
};

export type BenchPromptMeasurement = {
  promptId: string;
  rung: LadderRung;
  paraphrase: 0 | 1;
  tokens: number;
  rerunCount: number;
  fidelityMean: number | null;
  fidelityVariance: number | null;
  fidelityStdDev: number | null;
  disqualified: boolean;
  leakageGate: LeakageGateResult;
};

export type BenchResult = {
  id: string;
  createdAt: string;
  track: BenchmarkTrack;
  split: string;
  seed: number;
  stratum: Stratum;
  metricClasses: MetricClass[];
  tau: number;
  k: number;
  canaryGuid: string;
  config: {
    datasetPath: string;
    decoding: string;
    evidenceModes: ObservationMode[];
    leakageThresholds: LeakageGateThresholds;
    bootstrapSamples: number;
    reruns: number;
  };
  models: BenchModelSummary[];
  itemRuns: BenchItemModelRun[];
  notes: string[];
};

export type BenchManifestModel = {
  model: string;
  evidenceMode: BenchManifestEvidenceMode;
  status: BenchArtifactStatus;
  missingEnv: string[];
  error?: string;
};

export type BenchManifestPrompt = {
  itemId: string;
  targetLabel?: string;
  promptId: string;
  rung: LadderRung;
  paraphrase: 0 | 1;
  label: string;
  tokens: number;
  leakageGate: LeakageGateResult;
  prompt: string;
};

export type BenchManifestGatedPrompt = Omit<BenchManifestPrompt, "prompt">;

export type BenchManifest = {
  id: string;
  createdAt: string;
  track: BenchmarkTrack;
  split: string;
  seed: number;
  datasetPath: string;
  itemCount: number;
  modelCount: number;
  models: BenchManifestModel[];
  configuredReruns: number;
  effectiveReruns: number;
  promptCount: number;
  nonLeakingPromptCount: number;
  gatedPromptCount: number;
  estimatedGenerations: number;
  leakageThresholds: LeakageGateThresholds;
  prompts: BenchManifestPrompt[];
  gatedPrompts: BenchManifestGatedPrompt[];
  notes: string[];
};

export type BenchAuditCheck = {
  id: BenchAuditCheckId;
  status: BenchAuditStatus;
  evidence: string;
};

export type BenchAudit = {
  status: BenchAuditStatus;
  dataDir: string;
  resultPath: string;
  evidenceNotePath: string;
  checks: BenchAuditCheck[];
};

export type BenchBundleArtifact = {
  role: BenchBundleArtifactRole;
  path: string;
  sha256: string;
  bytes: number;
  evidenceMode: BenchBundleEvidenceMode;
  schemaPath: string | null;
  note: string;
};

export type BenchBundle = {
  id: string;
  createdAt: string;
  status: BenchAuditStatus;
  evidenceMode: BenchBundleEvidenceMode;
  artifacts: BenchBundleArtifact[];
  validationCommands: string[];
  notes: string[];
};

export type BenchPlatformArtifact = {
  role: BenchPlatformArtifactRole;
  path: string;
  sha256: string;
  bytes: number;
  encodingFormat: string;
  note: string;
};

export type BenchPlatformPackage = {
  id: string;
  createdAt: string;
  packageKind: "platform_release";
  evidenceMode: BenchBundleEvidenceMode;
  root: string;
  targetPlatforms: BenchPlatformTarget[];
  kaggleDatasetId: string;
  huggingFaceDatasetId: string;
  artifacts: BenchPlatformArtifact[];
  validationCommands: string[];
  notes: string[];
};
