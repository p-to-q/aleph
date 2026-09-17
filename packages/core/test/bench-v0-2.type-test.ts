import type {
  BenchItem,
  BenchItemV02,
  BenchLeakageGateResultV02,
  BenchManifestV02,
  BenchMetricClassV02,
  BenchPlatformPackageV02,
  BenchResultV02,
} from "../src/index.ts";

type Equal<Left, Right> =
  (<Value>() => Value extends Left ? 1 : 2) extends
  (<Value>() => Value extends Right ? 1 : 2)
    ? true
    : false;
type Assert<Value extends true> = Value;

type _ProtocolIsLiteral = Assert<Equal<BenchResultV02["protocolVersion"], "0.2.0">>;
type _RawOutputsAreStrings = Assert<
  Equal<BenchResultV02["itemRuns"][number]["measurements"][number]["outputs"], string[]>
>;
type _ManifestUsesDualGate = Assert<
  Equal<
    BenchManifestV02["prompts"][number]["leakageGate"],
    BenchLeakageGateResultV02
  >
>;
type _PackageIsConformanceOnly = Assert<
  Equal<BenchPlatformPackageV02["packageKind"], "scorer_conformance">
>;
type _LegacyAndV02StayDistinct = Assert<
  Equal<BenchItem extends BenchItemV02 ? true : false, false>
>;

// @ts-expect-error v0.1 metric names must not enter the v0.2 contract.
const legacyMetric: BenchMetricClassV02 = "lexical";

// @ts-expect-error all v0.2 artifacts require the protocol discriminator.
const missingProtocol: BenchItemV02 = {};

// @ts-expect-error the v0.2 gate requires the skeleton channel receipt.
const legacyLeakageShape: BenchLeakageGateResultV02 = {
  disqualified: false,
  unit: "unicode_dual_channel_v1",
  lcsRatio: 0,
  targetTrigramRecall: 0,
  verbatimSpanUnits: 0,
  thresholds: {
    lcsRatio: 0.65,
    targetTrigramRecall: 0.5,
    verbatimSpanUnits: 16,
    skeletonLcsRatio: 0.8,
    skeletonTargetTrigramRecall: 0.8,
    skeletonVerbatimSpanUnits: 32,
  },
};

void legacyMetric;
void missingProtocol;
void legacyLeakageShape;
