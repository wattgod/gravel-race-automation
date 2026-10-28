/** Read-only Substack confirmation relay. No mail send, draft, delete or modify scope. */
function installNewsletterAttribution() {
  newsletterAccount_();
  if (!PropertiesService.getScriptProperties().getProperty('NEWSLETTER_INGEST_SECRET')) throw new Error('Set NEWSLETTER_INGEST_SECRET first.');
  ScriptApp.getProjectTriggers().filter(function(t) { return t.getHandlerFunction() === 'runNewsletterAttribution'; })
    .forEach(function(t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('runNewsletterAttribution').timeBased().everyMinutes(5).create();
  runNewsletterAttribution();
}
function newsletterAccount_() {
  if (Session.getEffectiveUser().getEmail().toLowerCase() !== 'gravelgodcoaching@gmail.com') throw new Error('Wrong Google account.');
}
function newsletterBody_(part) {
  if (!part) return '';
  var text = '';
  if (/^text\/(plain|html)$/.test(part.mimeType || '') && part.body && part.body.data) {
    var data = part.body.data;
    // Advanced services can expose API `bytes` as a byte array rather than base64url.
    var bytes = Array.isArray(data) ? data : Utilities.base64DecodeWebSafe(String(data) + '='.repeat((4 - String(data).length % 4) % 4));
    text = Utilities.newBlob(bytes).getDataAsString();
    if (part.mimeType === 'text/html') text = text.replace(/<[^>]*>/g,' ').replace(/&nbsp;/g,' ');
  }
  return text + (part.parts || []).map(newsletterBody_).join('\n');
}
function runNewsletterAttribution() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    newsletterAccount_();
    var props = PropertiesService.getScriptProperties();
    var secret = props.getProperty('NEWSLETTER_INGEST_SECRET');
    if (!secret) throw new Error('Missing newsletter integration secret.');
    var startedAt = Math.floor(Date.now()/1000);
    var cursor = Number(props.getProperty('NEWSLETTER_LAST_SYNC')) || startedAt - 2*86400;
    var after = Math.max(cursor - 3600, startedAt - 7*86400);
    var query = '-in:spam -in:trash from:no-reply@substack.com subject:"subscriber to Slow, Mid, 38s!" after:' + after;
    var messages = [], token;
    for (var page=0;page<5;page++) {
      var result = Gmail.Users.Messages.list('me',{q:query,maxResults:100,pageToken:token});
      (result.messages || []).forEach(function(reference) {
        var message = Gmail.Users.Messages.get('me',reference.id,{format:'full'});
        var headers = message.payload.headers || [];
        function header(name) { var h=headers.find(function(h){return h.name.toLowerCase()===name;}); return h ? h.value : ''; }
        // Gmail search also matches other lifecycle notices; only signup subjects enter the relay.
        if (!/^New (?:free|paid) subscriber to Slow, Mid, 38s!$/.test(header('subject'))) return;
        var body = newsletterBody_(message.payload).slice(0,18000);
        var email = body.match(/\bEmail:\s*([^\s<>]+@[^\s<>]+)/i);
        // Transfer the signup address and verification evidence, not the rest of the email.
        messages.push({id:message.id,from:header('from'),subject:header('subject'),
          date:new Date(Number(message.internalDate)).toISOString(),auth_results:header('authentication-results'),
          body:email ? 'Email: '+email[1] : ''});
      });
      token=result.nextPageToken;
      if (!token) break;
    }
    if (token) throw new Error('Newsletter backlog exceeds 500 messages; cursor preserved.');
    for(var start=0;start<Math.max(1,messages.length);start+=10) {
      var response=UrlFetchApp.fetch('https://newsletter-attribution.gravelgodcoaching.workers.dev/confirm',{
        method:'post',contentType:'application/json',headers:{Authorization:'Bearer '+secret},
        payload:JSON.stringify({messages:messages.slice(start,start+10)}),muteHttpExceptions:true});
      if (response.getResponseCode() !== 200) throw new Error('Confirmation relay returned HTTP '+response.getResponseCode());
      if (JSON.parse(response.getContentText()).rejected) throw new Error('Notification format/authentication failed; cursor preserved.');
    }
    props.setProperty('NEWSLETTER_LAST_SYNC',String(startedAt));
    console.log(JSON.stringify({newsletter_sync:'ok',messages:messages.length}));
  } finally { lock.releaseLock(); }
}
