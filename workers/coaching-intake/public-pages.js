// Fixed public URLs only: callers cannot select a host, path, or redirect target.
const SITES = ['https://gravelgodcycling.com', 'https://roadielabs.com', 'https://xcskilabs.com'];
const PATHS = ['/coaching/', '/coaching/apply/', '/coaching/welcome/'];
const MAX_BYTES = 2_000_000;
const WORKER_CONTRACT = ['coaching_intake_submission_id', 'coaching-intake'];
const XC_CONTRACT = ['action="https://formsubmit.co/',
  'name="_next" value="https://xcskilabs.com/coaching/apply/?submitted=true"',
  'name="email"', 'id="submitBtn"'];

async function probePage(site, path, fetcher) {
  const url = site + path;
  try {
    const response = await fetcher(url, {
      redirect: 'manual', signal: AbortSignal.timeout(20_000), cache: 'no-store',
      headers: { 'Accept': 'text/html', 'Cache-Control': 'no-cache' },
    });
    if (response.status !== 200) {
      await response.body?.cancel();
      return { url, ok: false, status: response.status, error: 'http_status' };
    }
    const reader = response.body?.getReader();
    if (!reader) return { url, ok: false, status: 200, error: 'empty_body' };
    const chunks = [];
    let size = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > MAX_BYTES) {
          await reader.cancel();
          return { url, ok: false, status: 200, error: 'body_too_large' };
        }
        chunks.push(value);
      }
    } finally {
      reader.releaseLock();
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    const body = new TextDecoder().decode(bytes);
    let error;
    if (size < 500) error = 'short_body';
    else if (!response.headers.get('content-type')?.toLowerCase().includes('text/html')) error = 'not_html';
    else if (/sgcaptcha|<title>[^<]*(?:captcha|access denied)/i.test(body)) error = 'challenge';
    else if (path === '/coaching/apply/' &&
        !WORKER_CONTRACT.every(token => body.includes(token)) &&
        !(site === 'https://xcskilabs.com' && XC_CONTRACT.every(token => body.includes(token)))) {
      error = 'intake_contract_missing';
    }
    return { url, ok: !error, status: 200, bytes: size, ...(error ? { error } : {}) };
  } catch (_) {
    // Network errors may contain provider details. Emit a fixed diagnostic only.
    return { url, ok: false, error: 'fetch_failed' };
  }
}

export async function probePublicPages(fetcher = fetch) {
  const pages = [];
  // Three concurrent requests maximum; each batch is bounded to 20 seconds.
  for (const site of SITES) {
    pages.push(...await Promise.all(PATHS.map(path => probePage(site, path, fetcher))));
  }
  return {
    schema: 'coaching_public_pages/v1', generated_at: new Date().toISOString(),
    status: pages.every(page => page.ok) ? 'ok' : 'failed', pages,
  };
}
