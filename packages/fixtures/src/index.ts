import fixtureManifest from "./manifest.json";
import nonLeakingRun from "./non-leaking-run.json";
import sampleRun from "./sample-run.json";
import gettysburgRun from "./gettysburg-run.json";

export { sampleRun, nonLeakingRun, gettysburgRun };
export { fixtureManifest };
export const fixtureRuns = [sampleRun, nonLeakingRun, gettysburgRun];
export default sampleRun;
