/**
 * Auralis Natura — V2 automation engine (Google Apps Script)
 * Bind this to the "Auralis CRM" spreadsheet:  Extensions → Apps Script.
 *
 * Flow
 *   1) Stripe payment   -> doPost():       create client folder, copy report Doc,
 *                                           log to CRM (status Paid), send welcome email.
 *   2) Intake submitted -> onFormSubmit():  mark Intake, copy the answers into the
 *                                           client's report Doc, send "received" email.
 *   3) Sheet menu "Auralis":                deliver report (Doc -> PDF email) / send review.
 *
 * Security: the Stripe webhook auth token lives in Script Properties (WEBHOOK_TOKEN),
 * never in this file. Apps Script web apps cannot read request headers, so the webhook
 * is authenticated with a secret  ?token=...  query param on the endpoint URL.
 */

const CONFIG = {
  CLIENTS_FOLDER_ID:      '10awEfYBCt308Ap_3ksk6QTmKpoAN2KM1',
  CRM_SHEET_ID:           '1-YZW1wjQUy4b0GTcQGoqZ9Ief_MplqXYIRB5QT7U034',
  CRM_TAB:                'CRM',            // <- rename if your tab is called something else
  INTAKE_FORM_URL:        'https://docs.google.com/forms/d/e/1FAIpQLSfOsX0hj1k_oI_mltKPxZ4wC2DAJKQWJiu-ZMMgvgbWzs3GSQ/viewform?usp=header',
  BOOKING_URL:            'https://calendar.app.google/v9uRtb6BNJkiqar39',
  REVIEW_URL:             'PASTE_GOOGLE_REVIEW_LINK',      // TODO: when you have one
  REPORT_TEMPLATE_DOC_ID: 'PASTE_REPORT_TEMPLATE_DOC_ID',  // Google Doc placed in _TEMPLATE
  FROM_NAME:              'Dr. rer. nat. Desiree Gruber',
  LOGO_URL:               'https://www.auralisnatura.com/images/logo-emblem.png'
};

// CRM column positions (1-based): A..I
const COL = {TS:1, NAME:2, EMAIL:3, PKG:4, AMOUNT:5, STATUS:6, FOLDER:7, DOC:8, NOTES:9};

// Stripe amount (main units, e.g. euros) -> package name. Adjust to your prices.
function packageForAmount_(amt){
  const map = {198:'The Root Session', 398:'The Bloom', 798:'The Flourishing'};
  return map[Math.round(amt)] || 'Auralis package';
}

/* ------------------------------------------------------------------ *
 * 1) STRIPE WEBHOOK
 * ------------------------------------------------------------------ */
function doPost(e){
  try {
    if (!e || !e.parameter || e.parameter.token !== getSecret_('WEBHOOK_TOKEN'))
      return out_('unauthorized');
    const event = JSON.parse(e.postData.contents);
    if (event.type === 'checkout.session.completed') {
      const s = event.data.object;
      const cd = s.customer_details || {};
      const name  = cd.name  || s.customer_name  || '';
      const email = cd.email || s.customer_email || '';
      const amount = (s.amount_total || 0) / 100;
      const currency = (s.currency || 'eur').toUpperCase();
      onboardClient_(name, email, amount, currency, packageForAmount_(amount));
    }
    return out_('ok');
  } catch (err) {
    console.error(err);
    return out_('logged'); // 200 so Stripe does not retry-storm; check Executions for errors
  }
}

function onboardClient_(name, email, amount, currency, pkg){
  const root  = DriveApp.getFolderById(CONFIG.CLIENTS_FOLDER_ID);
  const stamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
  const folder = root.createFolder((name || email || 'Client') + ' — ' + stamp);
  let docUrl = '';
  if (CONFIG.REPORT_TEMPLATE_DOC_ID && CONFIG.REPORT_TEMPLATE_DOC_ID.indexOf('PASTE') < 0) {
    const copy = DriveApp.getFileById(CONFIG.REPORT_TEMPLATE_DOC_ID)
                         .makeCopy('Report — ' + (name || email), folder);
    docUrl = copy.getUrl();
  }
  crm_().appendRow([new Date(), name, email, pkg, currency + ' ' + amount,
                    'Paid', folder.getUrl(), docUrl, '']);
  sendTemplate_(email, 'welcome', 'en', {first: firstName_(name)});
}

/* ------------------------------------------------------------------ *
 * 2) INTAKE FORM SUBMISSION (installable trigger — run setupTriggers once)
 * ------------------------------------------------------------------ */
function onFormSubmit_(e){
  const nv = (e && e.namedValues) || {};
  const email = pickValue_(nv, ['Email Address','Email','email']);
  const lang  = detectLang_(pickValue_(nv, ['Location & preferred language','Language','language']));
  const sh = crm_();
  const row = findRowByEmail_(email);
  if (row) {
    sh.getRange(row, COL.STATUS).setValue('Intake');
    const notes = String(sh.getRange(row, COL.NOTES).getValue() || '');
    if (notes.indexOf('lang=') < 0) sh.getRange(row, COL.NOTES).setValue((notes + ' lang=' + lang).trim());
    appendIntakeToDoc_(sh.getRange(row, COL.DOC).getValue(), nv);
    sendTemplate_(email, 'intake', lang, {first: firstName_(sh.getRange(row, COL.NAME).getValue())});
  } else {
    // No matching paid client yet — record it so nothing is lost.
    sh.appendRow([new Date(), '', email, '', '', 'Intake (no match)', '', '', 'lang=' + lang]);
  }
}

function appendIntakeToDoc_(docUrl, nv){
  const id = idFromUrl_(docUrl); if (!id) return;
  const body = DocumentApp.openById(id).getBody();
  body.appendPageBreak();
  body.appendParagraph('Intake answers').setHeading(DocumentApp.ParagraphHeading.HEADING1);
  Object.keys(nv).forEach(function(k){
    if (/timestamp/i.test(k)) return;
    body.appendParagraph(k).setHeading(DocumentApp.ParagraphHeading.HEADING3);
    body.appendParagraph((nv[k] || []).join(', '));
  });
}

/* ------------------------------------------------------------------ *
 * 3) SHEET MENU ACTIONS
 * ------------------------------------------------------------------ */
function onOpen(){
  SpreadsheetApp.getUi().createMenu('Auralis')
    .addItem('Deliver report for selected row', 'deliverReport_')
    .addItem('Send review request for selected row', 'sendReviewRequest_')
    .addSeparator()
    .addItem('Set up triggers', 'setupTriggers')
    .addToUi();
}

function deliverReport_(){
  const sh = crm_(); const row = sh.getActiveCell().getRow();
  if (row < 2) return ui_('Select a client row first.');
  const name = sh.getRange(row, COL.NAME).getValue();
  const email = sh.getRange(row, COL.EMAIL).getValue();
  const lang = langFromNotes_(sh.getRange(row, COL.NOTES).getValue());
  const id = idFromUrl_(sh.getRange(row, COL.DOC).getValue());
  if (!id) return ui_('No report Doc is linked on this row.');
  const pdf = DriveApp.getFileById(id).getAs('application/pdf')
                      .setName('Auralis Report — ' + name + '.pdf');
  sendTemplate_(email, 'report', lang, {first: firstName_(name)}, [pdf]);
  sh.getRange(row, COL.STATUS).setValue('Delivered');
  ui_('Report delivered to ' + email);
}

function sendReviewRequest_(){
  const sh = crm_(); const row = sh.getActiveCell().getRow();
  if (row < 2) return ui_('Select a client row first.');
  const name = sh.getRange(row, COL.NAME).getValue();
  const email = sh.getRange(row, COL.EMAIL).getValue();
  const lang = langFromNotes_(sh.getRange(row, COL.NOTES).getValue());
  sendTemplate_(email, 'review', lang, {first: firstName_(name)});
  sh.getRange(row, COL.STATUS).setValue('Reviewed');
  ui_('Review request sent to ' + email);
}

function setupTriggers(){
  ScriptApp.getProjectTriggers().forEach(function(t){
    if (t.getHandlerFunction() === 'onFormSubmit_') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('onFormSubmit_')
    .forSpreadsheet(SpreadsheetApp.openById(CONFIG.CRM_SHEET_ID))
    .onFormSubmit().create();
  ui_('Triggers set up. The intake form must send responses to THIS spreadsheet.');
}

/* ------------------------------------------------------------------ *
 * EMAIL TEMPLATES (EN / DE / ES)
 * ------------------------------------------------------------------ */
const TEMPLATES = {
  welcome: {
    en: {subject:'Welcome to Auralis Natura, {{first}}',
         body:'<p>Hi {{first}}, thank you for choosing Auralis Natura. Two quick steps so we can begin:</p>'
            +'<p>1) Complete your secure intake: <a href="{{intake}}">intake form</a><br>'
            +'2) Book your session(s): <a href="{{booking}}">booking page</a></p>'
            +'<p>Once I have read your intake I will prepare your personalised report, and we will walk through it together on a call.</p>'},
    de: {subject:'Willkommen bei Auralis Natura, {{first}}',
         body:'<p>Hallo {{first}}, danke, dass du dich für Auralis Natura entschieden hast. Zwei kurze Schritte zum Start:</p>'
            +'<p>1) Fülle deinen sicheren Aufnahmebogen aus: <a href="{{intake}}">Aufnahmebogen</a><br>'
            +'2) Buche deine Sitzung(en): <a href="{{booking}}">Buchungsseite</a></p>'
            +'<p>Sobald ich deinen Bogen gelesen habe, erstelle ich deinen persönlichen Report, den wir gemeinsam im Gespräch durchgehen.</p>'},
    es: {subject:'Bienvenida a Auralis Natura, {{first}}',
         body:'<p>Hola {{first}}, gracias por elegir Auralis Natura. Dos pasos rápidos para empezar:</p>'
            +'<p>1) Completa tu cuestionario seguro: <a href="{{intake}}">cuestionario</a><br>'
            +'2) Reserva tu(s) sesión(es): <a href="{{booking}}">página de reservas</a></p>'
            +'<p>En cuanto lea tu cuestionario prepararé tu informe personalizado y lo veremos juntas en una llamada.</p>'}
  },
  intake: {
    en: {subject:'Got it — thank you, {{first}}',
         body:'<p>Thank you, {{first}} — I have received your intake and will prepare your report before our session. If anything urgent comes up, please see your doctor (112 in an emergency).</p>'},
    de: {subject:'Angekommen — danke, {{first}}',
         body:'<p>Danke, {{first}} — dein Aufnahmebogen ist da; ich bereite deinen Report vor unserer Sitzung vor. Bei etwas Dringendem wende dich bitte an deine Ärztin/deinen Arzt (im Notfall 112).</p>'},
    es: {subject:'Recibido — gracias, {{first}}',
         body:'<p>Gracias, {{first}} — he recibido tu cuestionario y prepararé tu informe antes de la sesión. Si surge algo urgente, acude a tu médico (112 en emergencias).</p>'}
  },
  report: {
    en: {subject:'Your Auralis report is ready, {{first}}',
         body:'<p>Hi {{first}}, your personalised report is attached. Have a read, and let us walk through it together — <a href="{{booking}}">book or confirm here</a>. This is educational guidance to complement, never replace, your medical care.</p>'},
    de: {subject:'Dein Auralis-Report ist da, {{first}}',
         body:'<p>Hallo {{first}}, dein persönlicher Report ist angehängt. Lies ihn in Ruhe; danach gehen wir ihn gemeinsam durch — <a href="{{booking}}">hier buchen/bestätigen</a>. Dies ist bildende Begleitung als Ergänzung, niemals als Ersatz für medizinische Versorgung.</p>'},
    es: {subject:'Tu informe Auralis está listo, {{first}}',
         body:'<p>Hola {{first}}, tu informe personalizado va adjunto. Léelo con calma y lo vemos juntas — <a href="{{booking}}">reserva o confirma aquí</a>. Es orientación educativa que complementa, nunca sustituye, tu atención médica.</p>'}
  },
  review: {
    en: {subject:'How are you feeling, {{first}}?',
         body:'<p>Hi {{first}}, I hope your first steps are settling in. If Auralis has helped, a short review would mean a lot: <a href="{{review}}">leave a review</a>. Thank you!</p>'},
    de: {subject:'Wie geht es dir, {{first}}?',
         body:'<p>Hallo {{first}}, ich hoffe, deine ersten Schritte etablieren sich. Wenn Auralis dir geholfen hat, würde mich eine kurze Bewertung sehr freuen: <a href="{{review}}">Bewertung abgeben</a>. Danke!</p>'},
    es: {subject:'¿Cómo te sientes, {{first}}?',
         body:'<p>Hola {{first}}, espero que tus primeros pasos vayan bien. Si Auralis te ha ayudado, una reseña breve significaría mucho: <a href="{{review}}">dejar una reseña</a>. ¡Gracias!</p>'}
  }
};

function sendTemplate_(to, type, lang, vars, attachments){
  if (!to) return;
  const t = TEMPLATES[type] && (TEMPLATES[type][lang] || TEMPLATES[type].en);
  if (!t) return;
  const subject = fill_(t.subject, vars);
  const html = fill_(t.body, vars) + signatureHtml_();
  const opts = {htmlBody: html, name: CONFIG.FROM_NAME};
  if (attachments && attachments.length) opts.attachments = attachments;
  GmailApp.sendEmail(to, subject, html.replace(/<[^>]+>/g, ''), opts);
}

function fill_(s, vars){
  vars = vars || {};
  return String(s)
    .replace(/{{first}}/g,  vars.first || '')
    .replace(/{{intake}}/g, CONFIG.INTAKE_FORM_URL)
    .replace(/{{booking}}/g, CONFIG.BOOKING_URL)
    .replace(/{{review}}/g,  CONFIG.REVIEW_URL);
}

function signatureHtml_(){
  return '<br><table cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;color:#2A2822;">'
   + '<tr><td style="padding-right:14px;border-right:2px solid #D8C8AA;vertical-align:middle;">'
   + '<img src="' + CONFIG.LOGO_URL + '" width="58" height="58" style="display:block;" alt="Auralis Natura"></td>'
   + '<td style="padding-left:14px;line-height:1.5;">'
   + '<div style="font-size:15px;font-weight:bold;color:#4A3A29;">' + CONFIG.FROM_NAME + '</div>'
   + '<div style="font-size:12px;color:#6B5238;letter-spacing:1px;text-transform:uppercase;">Auralis Natura · Holistic Health</div>'
   + '<div style="font-size:12px;color:#5A5544;margin-top:3px;">office@auralisnatura.com · +34 662 10 3136</div>'
   + '<div style="font-size:10px;color:#9C8460;margin-top:5px;font-style:italic;">Holistic-health coaching &amp; education — not medical care.</div>'
   + '</td></tr></table>';
}

/* ------------------------------------------------------------------ *
 * HELPERS
 * ------------------------------------------------------------------ */
function crm_(){ return SpreadsheetApp.openById(CONFIG.CRM_SHEET_ID).getSheetByName(CONFIG.CRM_TAB); }
function getSecret_(k){ return PropertiesService.getScriptProperties().getProperty(k) || ''; }
function out_(msg){ return ContentService.createTextOutput(msg); }
function firstName_(n){ return String(n || '').trim().split(/\s+/)[0] || ''; }
function idFromUrl_(u){ const m = String(u || '').match(/[-\w]{25,}/); return m ? m[0] : ''; }
function detectLang_(s){ s = String(s || '').toLowerCase();
  if (/espa|spanish|\bes\b/.test(s)) return 'es';
  if (/deuts|german|\bde\b/.test(s)) return 'de';
  return 'en'; }
function langFromNotes_(s){ const m = String(s || '').match(/lang=(\w\w)/); return m ? m[1] : 'en'; }
function pickValue_(nv, keys){
  for (const want of keys)
    for (const k of Object.keys(nv))
      if (k.toLowerCase().indexOf(want.toLowerCase()) >= 0 && nv[k] && nv[k][0]) return nv[k][0];
  return '';
}
function findRowByEmail_(email){
  if (!email) return null;
  const sh = crm_(); const last = sh.getLastRow();
  email = String(email).toLowerCase();
  for (let r = last; r >= 2; r--)
    if (String(sh.getRange(r, COL.EMAIL).getValue()).toLowerCase() === email) return r;
  return null;
}
function ui_(msg){ try { SpreadsheetApp.getUi().alert(msg); } catch (e) { console.log(msg); } }
