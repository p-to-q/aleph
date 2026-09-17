import type {
  AlephMode,
  CandidatePoint,
  EvalResult,
  ObservationMode,
  SearchBudget,
  TargetOutput,
} from "./types.ts";

/** Versioned public contract for schemas/v0.2. Keep v0.1 types in bench.ts immutable. */
export type BenchProtocolVersionV02 = "0.2.0";
export type BenchStratumV02 = "S2";
export type BenchMetricClassV02 =
  | "exact"
  | "normalized_edit_similarity"
  | "unicode_char_ngram";
export type BenchmarkTrackV02 = "F";
export type BenchmarkSplitV02 = "public";
export type BenchLadderRungV02 = 0 | 1 | 2 | 3;
export type BenchParaphraseV02 = 0 | 1;
export type BenchArtifactStatusV02 = "ready" | "blocked";
export type BenchManifestEvidenceModeV02 = ObservationMode | "unknown";

export type BenchScoringProfileV02 = {
  scorerId: "aleph-unicode";
  scorerVersion: "0.2.0";
  schemaVersion: "0.2.0";
  normalizationProfile: "unicode_nfc_newline_v1";
  lexicalProfile: "unicode_nfc_casefold_whitespace_char3_multiset_jaccard_v1";
  leakageUnit: "unicode_dual_channel_v1";
  leakageFailClosedPolicy: "bidi_controls_and_cjk_compatibility_ideographs_v1";
  responseCaptureVersion: "raw-v1";
  unicodeDatabaseVersion: "15.1.0";
  pythonVersion: "3.13";
  maxScoringTextCharacters: 16384;
  maxNormalizedTextCharacters: 32768;
  maxQuadraticCells: 1000000;
};

export type BenchLeakageGateThresholdsV02 = {
  lcsRatio: 0.65;
  targetTrigramRecall: 0.5;
  verbatimSpanUnits: 16;
  skeletonLcsRatio: 0.8;
  skeletonTargetTrigramRecall: 0.8;
  skeletonVerbatimSpanUnits: 32;
};

export type BenchLeakageGateResultV02 = {
  disqualified: boolean;
  unit: "unicode_dual_channel_v1";
  failClosedReason: "bidi_control" | "cjk_compatibility_ideograph" | null;
  lcsRatio: number;
  targetTrigramRecall: number;
  verbatimSpanUnits: number;
  skeletonLcsRatio: number;
  skeletonTargetTrigramRecall: number;
  skeletonVerbatimSpanUnits: number;
  thresholds: BenchLeakageGateThresholdsV02;
};

export type FrozenLadderPromptV02 = {
  id: string;
  rung: BenchLadderRungV02;
  paraphrase: BenchParaphraseV02;
  label: string;
  prompt: string;
  expectedLeakage: "leaky_anchor" | "non_leaking_candidate";
};

export type BenchProvenanceParameterV02 =
  | string
  | number
  | boolean
  | string[]
  | number[];

export type BenchProvenanceV02 = {
  createdBy: string;
  generatedAt: string;
  method: string;
  seed: number;
  parameters?: Record<string, BenchProvenanceParameterV02>;
};

export type BenchItemV02 = {
  protocolVersion: BenchProtocolVersionV02;
  id: string;
  stratum: BenchStratumV02;
  language: string;
  target: TargetOutput;
  metricClass: BenchMetricClassV02;
  frozenLadder: FrozenLadderPromptV02[];
  canaryGuid: string;
  provenance: BenchProvenanceV02;
  license: string;
};

export type BenchSearchConfigV02 = {
  model: string;
  decoding: string;
  metric: BenchMetricClassV02;
  budget: SearchBudget;
  mode: AlephMode;
};

export type BenchObservationSetV02 = {
  mode: ObservationMode;
  evalSuite?: EvalResult[];
};

export type BenchAlephRunV02 = {
  id: string;
  createdAt: string;
  target: TargetOutput;
  config: BenchSearchConfigV02;
  candidates: CandidatePoint[];
  selectedCandidateId: string;
  observations: BenchObservationSetV02;
};

export type ConfidenceIntervalV02 = {
  low: number;
  high: number;
};

export type BenchFrontierPointV02 = CandidatePoint & {
  itemId: string;
  model: string;
  rung: BenchLadderRungV02;
  paraphrase: BenchParaphraseV02;
  distortion: number;
  fidelity: number;
  rerunCount: number;
  fidelityVariance: number;
  fidelityStdDev: number;
  disqualified: boolean;
  leakageGate: BenchLeakageGateResultV02;
  evidenceMode: ObservationMode;
};

type BenchAdapterIdentityBaseV02 = {
  adapterId: string;
  adapterVersion: string;
  model: string;
  temperature: number;
};

export type BenchHostedAdapterIdentityV02 = BenchAdapterIdentityBaseV02 & {
  observationMode: "black_box";
  wireProtocol: string;
  requestPayloadVersion: string;
  endpointSha256: string;
  maxTokens: number;
  providerModel: string;
  deploymentId: string;
  timeoutSeconds: number;
  maxRetries: number;
  retryDelaySeconds: number;
};

export type BenchNonHostedAdapterIdentityV02 = BenchAdapterIdentityBaseV02 & {
  observationMode: Exclude<ObservationMode, "black_box">;
  wireProtocol?: string;
  requestPayloadVersion?: string;
  endpointSha256?: string;
  maxTokens?: number;
  providerModel?: string;
  deploymentId?: string;
  timeoutSeconds?: number;
  maxRetries?: number;
  retryDelaySeconds?: number;
};

export type BenchAdapterIdentityV02 =
  | BenchHostedAdapterIdentityV02
  | BenchNonHostedAdapterIdentityV02;

export type BenchResponseReceiptV02 = {
  capturedAt: string;
  source: "provider" | "cache";
};

export type BenchResponseCaptureV02 = {
  responseCount: number;
  providerResponseCount: number;
  cacheHitCount: number;
  capturedAtMin: string;
  capturedAtMax: string;
};

export type BenchPromptMeasurementV02 = {
  promptId: string;
  rung: BenchLadderRungV02;
  paraphrase: BenchParaphraseV02;
  tokens: number;
  outputs: string[];
  responseReceipts: BenchResponseReceiptV02[];
  rerunCount: number;
  fidelityMean: number | null;
  fidelityVariance: number | null;
  fidelityStdDev: number | null;
  disqualified: boolean;
  leakageGate: BenchLeakageGateResultV02;
};

type BenchModelSummaryBaseV02 = {
  model: string;
  itemCount: number;
  aurc: number;
  aurcCi95: ConfidenceIntervalV02;
  eclAtTau: number | null;
  eclAtTauCi95: ConfidenceIntervalV02 | null;
  coverageAtTau: number;
  elicitAtK: number;
  elicitAtKCi95: ConfidenceIntervalV02;
  leakageHitRate: number;
};

export type BenchModelSummaryV02 =
  | (BenchModelSummaryBaseV02 & {
      evidenceMode: "black_box";
      adapterIdentity: BenchHostedAdapterIdentityV02;
      responseCapture: BenchResponseCaptureV02;
    })
  | (BenchModelSummaryBaseV02 & {
      evidenceMode: Exclude<ObservationMode, "black_box">;
      adapterIdentity: BenchNonHostedAdapterIdentityV02;
      responseCapture: null;
    });

export type BenchItemModelRunV02 = {
  itemId: string;
  model: string;
  alephRun: BenchAlephRunV02;
  measurements: BenchPromptMeasurementV02[];
  frontier: BenchFrontierPointV02[];
  metrics: {
    aurc: number;
    eclAtTau: number | null;
    elicitAtK: boolean;
    leakageHitRate: number;
  };
};

export type BenchResultConfigV02 = {
  datasetPath: string;
  datasetId: "aleph-bench-v0.2-public-s2";
  datasetItemCount: 30;
  datasetSha256: "6f3a03400ec16405414afb94c7c639f2df07f7f0797c3b58ad1c4229e52f2041";
  datasetHashAlgorithm: "sha256-length-framed-filename-and-content-v1";
  decoding: {
    mock: "temperature=0";
    hosted: "temperature=0; max_tokens=512";
  };
  evidenceModes: ObservationMode[];
  leakageThresholds: BenchLeakageGateThresholdsV02;
  scoring: BenchScoringProfileV02;
  bootstrapSamples: 500;
  reruns: 5;
};

export type BenchResultV02 = {
  protocolVersion: BenchProtocolVersionV02;
  evaluationScope: "canonical" | "smoke";
  requestedItemLimit: number | null;
  evaluatedItemCount: number;
  id: string;
  createdAt: string;
  track: BenchmarkTrackV02;
  split: BenchmarkSplitV02;
  seed: number;
  stratum: BenchStratumV02;
  metricClasses: ["normalized_edit_similarity"];
  tau: 0.95;
  k: 16;
  canaryGuid: string;
  config: BenchResultConfigV02;
  models: BenchModelSummaryV02[];
  itemRuns: BenchItemModelRunV02[];
  notes: string[];
};

type BenchManifestModelBaseV02 = {
  model: string;
  missingEnv: string[];
  effectiveReruns: number;
  error?: string;
};

export type BenchManifestModelV02 =
  | (BenchManifestModelBaseV02 & {
      evidenceMode: "black_box";
      status: "ready";
      adapterIdentity: BenchHostedAdapterIdentityV02;
    })
  | (BenchManifestModelBaseV02 & {
      evidenceMode: "black_box";
      status: "blocked";
      adapterIdentity: BenchHostedAdapterIdentityV02 | null;
    })
  | (BenchManifestModelBaseV02 & {
      evidenceMode: Exclude<BenchManifestEvidenceModeV02, "black_box">;
      status: "ready";
      adapterIdentity: BenchNonHostedAdapterIdentityV02;
    })
  | (BenchManifestModelBaseV02 & {
      evidenceMode: Exclude<BenchManifestEvidenceModeV02, "black_box">;
      status: "blocked";
      adapterIdentity: BenchNonHostedAdapterIdentityV02 | null;
    });

export type BenchManifestPromptBaseV02 = {
  itemId: string;
  targetLabel: string | null;
  promptId: string;
  rung: BenchLadderRungV02;
  paraphrase: BenchParaphraseV02;
  label: string;
  tokens: number;
  leakageGate: BenchLeakageGateResultV02;
};

export type BenchManifestPromptV02 = BenchManifestPromptBaseV02 & {
  prompt: string;
};

export type BenchManifestGatedPromptV02 = BenchManifestPromptBaseV02;

export type BenchManifestV02 = {
  protocolVersion: BenchProtocolVersionV02;
  id: string;
  createdAt: string;
  track: BenchmarkTrackV02;
  split: BenchmarkSplitV02;
  seed: number;
  datasetPath: string;
  datasetId: "aleph-bench-v0.2-public-s2";
  datasetItemCount: 30;
  datasetSha256: "6f3a03400ec16405414afb94c7c639f2df07f7f0797c3b58ad1c4229e52f2041";
  datasetHashAlgorithm: "sha256-length-framed-filename-and-content-v1";
  itemCount: number;
  modelCount: number;
  models: BenchManifestModelV02[];
  configuredReruns: 5;
  promptCount: number;
  nonLeakingPromptCount: number;
  gatedPromptCount: number;
  estimatedGenerations: number;
  hostedMaxRetries: number;
  hostedRetryDelaySeconds: number;
  estimatedMaxHttpAttempts: number;
  leakageThresholds: BenchLeakageGateThresholdsV02;
  scoring: BenchScoringProfileV02;
  prompts: BenchManifestPromptV02[];
  gatedPrompts: BenchManifestGatedPromptV02[];
  notes: string[];
};

export type BenchPlatformArtifactRoleV02 =
  | "conformance"
  | "data"
  | "docs"
  | "kaggle"
  | "schemas";

export type BenchPlatformArtifactV02 = {
  role: BenchPlatformArtifactRoleV02;
  path: string;
  sha256: string;
  bytes: number;
  encodingFormat: string;
};

export type BenchPlatformPackageV02 = {
  protocolVersion: BenchProtocolVersionV02;
  packageVersion: "0.2.0";
  id: "aleph-bench-v0.2-scorer-conformance";
  createdAt: string;
  datasetId: "aleph-bench-v0.2-public-s2";
  datasetItemCount: 30;
  datasetSha256: "6f3a03400ec16405414afb94c7c639f2df07f7f0797c3b58ad1c4229e52f2041";
  datasetHashAlgorithm: "sha256-length-framed-filename-and-content-v1";
  packageKind: "scorer_conformance";
  evidenceMode: "none";
  targetPlatforms: ["kaggle_community_benchmark"];
  scoringProfile: BenchScoringProfileV02;
  artifacts: BenchPlatformArtifactV02[];
  validationCommands: string[];
  notes: string[];
};
