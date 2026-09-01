/**
 * Gmail Lead Bridge for Gravel God Mission Control.
 *
 * Runs as the owner of the configured Gmail account. It reads only known lead
 * correspondents for the configured brands, syncs their threads, and turns
 * explicitly approved suggestions into Gmail drafts. It never sends email.
 */

const BRIDGE_TRIGGER_FUNCTION = 'runLeadBridge';
const SEARCH_OVERLAP_DAYS = 30;
const BACKFILL_DAYS = 180;
const CANDIDATE_BATCH_SIZE = 20;
const MAX_THREADS_PER_QUERY = 100;
const NORMAL_SYNC_THREADS_PER_RUN = 100;
const MAX_SYNC_THREADS_PER_RUN = 500;
const SYNC_POST_BATCH_SIZE = 20;
const MAX_MESSAGES_PER_THREAD = 50;
const MAX_MESSAGE_BODY_CHARS = 12000;
const MAX_DRAFTS_PER_RUN = 15;
const VALID_BRANDS = ['gravelgod', 'roadielabs', 'xcskilabs'];


function installLeadBridge() {
  const props = PropertiesService.getScriptProperties();
  const required = ['MISSION_CONTROL_URL', 'WEBHOOK_SECRET', 'ACCOUNT_EMAIL', 'BRANDS'];
  const missing = required.filter((key) => !props.getProperty(key));
  if (missing.length) {
    throw new Error(`Set Script Properties first: ${missing.join(', ')}`);
  }
  assertCorrectAccount_();
  bridgeBrands_();

  ScriptApp.getProjectTriggers()
    .filter((trigger) => trigger.getHandlerFunction() === BRIDGE_TRIGGER_FUNCTION)
    .forEach((trigger) => ScriptApp.deleteTrigger(trigger));

  ScriptApp.newTrigger(BRIDGE_TRIGGER_FUNCTION)
    .timeBased()
    .everyMinutes(5)
    .create();

  runLeadBridge();
}


function runLeadBridge() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    assertCorrectAccount_();
    syncKnownLeadThreads_(SEARCH_OVERLAP_DAYS, NORMAL_SYNC_THREADS_PER_RUN);
    createApprovedDrafts_();
    PropertiesService.getScriptProperties().setProperty(
      'LAST_SUCCESS_AT', new Date().toISOString(),
    );
  } finally {
    lock.releaseLock();
  }
}


/** Run manually after installation to reconcile older replies and drafts. */
function backfillLeadThreads() {
  assertCorrectAccount_();
  syncKnownLeadThreads_(BACKFILL_DAYS, MAX_SYNC_THREADS_PER_RUN);
}


function syncKnownLeadThreads_(lookbackDays, maxSyncThreads) {
  const response = missionControlGet_('/webhooks/gmail-sync/candidates');
  const candidates = (response.candidates || [])
    .map((row) => String(row.email || '').trim().toLowerCase())
    .filter(Boolean);
  if (!candidates.length) return;

  const uniqueThreads = {};
  chunk_(candidates, CANDIDATE_BATCH_SIZE).forEach((emails) => {
    const addressTerms = [];
    emails.forEach((email) => {
      addressTerms.push(`from:${quoteGmail_(email)}`);
      addressTerms.push(`to:${quoteGmail_(email)}`);
    });
    const query = [
      'in:anywhere', '-in:spam', '-in:trash',
      `newer_than:${lookbackDays || SEARCH_OVERLAP_DAYS}d`,
      `{${addressTerms.join(' ')}}`,
    ].join(' ');
    GmailApp.search(query, 0, MAX_THREADS_PER_QUERY).forEach((thread) => {
      uniqueThreads[thread.getId()] = thread;
    });
  });

  const candidateSet = {};
  candidates.forEach((email) => { candidateSet[email] = true; });
  const threads = Object.keys(uniqueThreads).slice(
    0, maxSyncThreads || NORMAL_SYNC_THREADS_PER_RUN,
  ).map((threadId) => {
    const thread = uniqueThreads[threadId];
    return {
      id: threadId,
      messages: thread.getMessages()
        .filter((message) => messageTouchesLead_(message, candidateSet))
        .slice(-MAX_MESSAGES_PER_THREAD)
        .map(messagePayload_),
    };
  }).filter((thread) => thread.messages.length);

  chunk_(threads, SYNC_POST_BATCH_SIZE).forEach((threadBatch) => {
    missionControlPost_('/webhooks/gmail-sync', {threads: threadBatch});
  });
}


function createApprovedDrafts_() {
  const response = missionControlGet_('/webhooks/gmail-sync/drafts/ready');
  const drafts = (response.drafts || []).slice(0, MAX_DRAFTS_PER_RUN);
  drafts.forEach((item) => {
    let receipt;
    try {
      const inbound = GmailApp.getMessageById(item.inbound_message_id);
      if (!inbound) throw new Error('Inbound Gmail message not found');
      const thread = inbound.getThread();
      const existingDraft = thread.getMessages().find((message) => message.isDraft());
      if (existingDraft) {
        receipt = {
          status: 'draft_conflict',
          gmail_draft_message_id: existingDraft.getId(),
        };
      } else {
        const body = String(item.draft_text || '').trim();
        if (!body) throw new Error('Approved suggestion has an empty draft');
        const draft = inbound.createDraftReply(body, {htmlBody: plainTextToHtml_(body)});
        receipt = {
          status: 'gmail_drafted',
          gmail_draft_id: draft.getId(),
          gmail_draft_message_id: draft.getMessageId(),
        };
      }
    } catch (error) {
      console.error(`Draft ${item.suggestion_id} failed: ${error.message}`);
      return;
    }
    missionControlPost_(
      `/webhooks/gmail-sync/drafts/${encodeURIComponent(item.suggestion_id)}/receipt`,
      receipt,
    );
  });
}


function messagePayload_(message) {
  return {
    id: message.getId(),
    from: message.getFrom(),
    to: splitAddresses_(message.getTo()),
    cc: splitAddresses_(message.getCc()),
    reply_to: message.getReplyTo(),
    subject: message.getSubject(),
    date: message.getDate().toISOString(),
    body: String(message.getPlainBody() || '').slice(0, MAX_MESSAGE_BODY_CHARS),
    is_draft: message.isDraft(),
    is_trash: message.isInTrash(),
  };
}


function assertCorrectAccount_() {
  const props = PropertiesService.getScriptProperties();
  const expected = String(props.getProperty('ACCOUNT_EMAIL') || '').trim().toLowerCase();
  const actual = String(Session.getEffectiveUser().getEmail() || '').trim().toLowerCase();
  if (!expected || actual !== expected) {
    throw new Error(`Gmail Lead Bridge account mismatch: expected ${expected}, got ${actual || '(unknown)'}`);
  }
}


function messageTouchesLead_(message, candidateSet) {
  const addresses = [message.getFrom(), message.getTo(), message.getCc()]
    .join(',')
    .toLowerCase();
  return Object.keys(candidateSet).some((email) => addresses.indexOf(email) !== -1);
}


function splitAddresses_(raw) {
  if (!raw) return [];
  return String(raw).split(',').map((value) => value.trim()).filter(Boolean);
}


function missionControlGet_(path) {
  return missionControlRequest_(path, 'get');
}


function missionControlPost_(path, payload) {
  return missionControlRequest_(path, 'post', payload);
}


function missionControlRequest_(path, method, payload) {
  const props = PropertiesService.getScriptProperties();
  const base = String(props.getProperty('MISSION_CONTROL_URL') || '').replace(/\/$/, '');
  const secret = props.getProperty('WEBHOOK_SECRET');
  const options = {
    method,
    muteHttpExceptions: true,
    headers: {
      Authorization: `Bearer ${secret}`,
      'X-Lead-Bridge-Account': bridgeAccount_(),
      'X-Lead-Bridge-Brands': bridgeBrands_().join(','),
    },
  };
  if (payload !== undefined) {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(payload);
  }
  const response = UrlFetchApp.fetch(`${base}${path}`, options);
  const code = response.getResponseCode();
  const text = response.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error(`Mission Control ${method.toUpperCase()} ${path}: ${code} ${text}`);
  }
  return text ? JSON.parse(text) : {};
}


function bridgeAccount_() {
  return String(
    PropertiesService.getScriptProperties().getProperty('ACCOUNT_EMAIL') || '',
  ).trim().toLowerCase();
}


function bridgeBrands_() {
  const raw = String(
    PropertiesService.getScriptProperties().getProperty('BRANDS') || '',
  );
  const brands = raw.split(',')
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  const invalid = brands.filter((brand) => VALID_BRANDS.indexOf(brand) === -1);
  if (!brands.length || invalid.length) {
    throw new Error(
      `BRANDS must contain only ${VALID_BRANDS.join(', ')}; got ${raw || '(empty)'}`,
    );
  }
  return [...new Set(brands)];
}


function quoteGmail_(value) {
  return `"${String(value).replace(/"/g, '')}"`;
}


function plainTextToHtml_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>');
}


function chunk_(values, size) {
  const chunks = [];
  for (let index = 0; index < values.length; index += size) {
    chunks.push(values.slice(index, index + size));
  }
  return chunks;
}
