import autocannon from "autocannon";

const url = process.env.SENTINEL_LOAD_URL ?? "http://127.0.0.1:8000/api/v1/health";
const duration = Number(process.env.SENTINEL_LOAD_SECONDS ?? 10);
const connections = Number(process.env.SENTINEL_LOAD_CONNECTIONS ?? 10);
const maxP99Ms = Number(process.env.SENTINEL_LOAD_MAX_P99_MS ?? 5000);

const result = await new Promise((resolve, reject) => {
  autocannon({ url, duration, connections, pipelining: 1 }, (error, summary) => {
    if (error) reject(error);
    else resolve(summary);
  });
});

const p99 = result.latency.p99;
const requestsPerSecond = result.requests.average;
console.log(JSON.stringify({ url, duration, connections, maxP99Ms, requestsPerSecond, latencyMs: result.latency, errors: result.errors, timeouts: result.timeouts }, null, 2));
if (result.errors > 0 || result.timeouts > 0 || p99 > maxP99Ms) {
  process.exitCode = 1;
}
