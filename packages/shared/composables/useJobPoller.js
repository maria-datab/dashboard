/**
 * Generic async-job poller.
 *
 * @param {object} options
 * @param {() => Promise<{ jobId: string }>} options.startFn   - POST the job, returns { jobId }
 * @param {(jobId: string) => Promise<object>} options.pollFn  - GET one status snapshot
 * @param {(snapshot: object) => void} [options.onSnapshot]    - called after each poll
 * @param {number} [options.intervalMs]                        - default 1200
 * @param {() => boolean} [options.shouldAbort]                - return true to stop early
 * @returns {Promise<object>} final snapshot when status === 'completed'
 * @throws if status === 'failed' or shouldAbort triggered
 */
export async function runJobPoll({
  startFn,
  pollFn,
  onSnapshot,
  intervalMs = 1200,
  shouldAbort,
}) {
  const start = await startFn()
  const jobId = start.jobId

  while (true) {
    if (shouldAbort?.()) throw new Error('aborted')

    const snapshot = await pollFn(jobId)
    onSnapshot?.(snapshot)

    if (snapshot.status === 'completed') return snapshot
    if (snapshot.status === 'failed') throw new Error(snapshot.error || 'Job failed')

    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
}
