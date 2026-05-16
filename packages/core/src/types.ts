export type AlephMode = "unrestricted" | "non_leaking";
export type ObservationMode = "fixture" | "mock" | "black_box" | "white_box" | "simulated";

export type TargetOutput = {
  text: string;
  label?: string;
};

export type SearchBudget = {
  candidates: number;
  maxPromptTokens: number;
  repeatedSamples: number;
  timeLimitSeconds?: number;
};

export type SearchConfig = {
  model: string;
  decoding: string;
  metric: string;
  budget: SearchBudget;
  mode: AlephMode;
};

export type CandidatePoint = {
  id: string;
  label: string;
  prompt: string;
  output: string;
  tokens: number;
  fit: number;
  stability: number;
  compression: number;
  leakage: number;
  nll?: number;
  frontierRank?: number;
  note?: string;
};

export type TokenLossPoint = {
  token: string;
  loss: number;
  rank?: number;
  topAlternatives?: string[];
};

export type WaveformPoint = {
  index: number;
  value: number;
  token?: string;
};

export type AttributionPoint = {
  promptToken: string;
  score: number;
  deltaLossIfRemoved?: number;
  supports?: string[];
};

export type LossCurvePoint = {
  step: number;
  loss: number;
  candidateId?: string;
};

export type ExposureVector = {
  name: string;
  level: "high" | "mid" | "low" | "new_exposure" | "reduced";
  value: number;
  note?: string;
};

export type EvalResult = {
  name: string;
  passed: boolean;
  score?: number;
  note?: string;
};

export type ObservationSet = {
  mode: ObservationMode;
  tokenLoss?: TokenLossPoint[];
  waveform?: WaveformPoint[];
  attribution?: AttributionPoint[];
  lossCurve?: LossCurvePoint[];
  exposureVectors?: ExposureVector[];
  evalSuite?: EvalResult[];
};

export type AlephRun = {
  id: string;
  createdAt: string;
  target: TargetOutput;
  config: SearchConfig;
  candidates: CandidatePoint[];
  selectedCandidateId: string;
  observations: ObservationSet;
};
