/* ============================================================
   Auralis Natura — Customer App
   Vanilla JS, no build step. Native features come from window.Capacitor.Plugins
   at runtime (present only in the app); on the web everything falls back safely,
   so the exact same bundle runs in a browser for testing.
   ============================================================ */
(function () {
  "use strict";
  var CFG = window.AN_CONFIG || {};
  var Cap = window.Capacitor;
  var P = (Cap && Cap.Plugins) || {};
  var isNative = !!(Cap && Cap.isNativePlatform && Cap.isNativePlatform());
  var params = new URLSearchParams(location.search);
  // ?api= override is a browser test convenience only — never honoured in the native
  // build, so a malicious deep link can't redirect authed calls to steal the token.
  var API = (((!isNative && params.get("api")) || CFG.API_BASE) || "").replace(/\/$/, "");

  var $ = function (s, r) { return (r || document).querySelector(s); };
  function el(html) { var t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstChild; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  /* ---------- storage (Preferences native · localStorage web) ---------- */
  var Store = {
    get: function (k) {
      if (P.Preferences) return P.Preferences.get({ key: k }).then(function (r) { return r.value; });
      try { return Promise.resolve(localStorage.getItem(k)); } catch (e) { return Promise.resolve(null); }
    },
    set: function (k, v) {
      if (P.Preferences) return P.Preferences.set({ key: k, value: v });
      try { localStorage.setItem(k, v); } catch (e) {} return Promise.resolve();
    },
    remove: function (k) {
      if (P.Preferences) return P.Preferences.remove({ key: k });
      try { localStorage.removeItem(k); } catch (e) {} return Promise.resolve();
    }
  };

  /* ---------- native bridges (safe no-ops on web) ---------- */
  function haptic(style) { try { if (P.Haptics) P.Haptics.impact({ style: style || "Light" }); } catch (e) {} }
  function hapticSuccess() { try { if (P.Haptics) P.Haptics.notification({ type: "SUCCESS" }); else haptic("Medium"); } catch (e) {} }
  function hideSplash() { try { if (P.SplashScreen) P.SplashScreen.hide(); } catch (e) {} }
  function styleStatusBar() { try { if (P.StatusBar) P.StatusBar.setStyle({ style: "LIGHT" }); } catch (e) {} }
  function openExternal(url) {
    if (!url) return;
    if (/^(mailto:|tel:)/i.test(url)) { window.location.href = url; return; }  // Browser plugin only does http(s)
    if (!/^https:\/\//i.test(url)) return;                                     // refuse non-https (blocks javascript: etc.)
    if (P.Browser) P.Browser.open({ url: url, presentationStyle: "popover", toolbarColor: "#3D2719" });
    else window.open(url, "_blank", "noopener");
  }
  function biometricAvailable() {
    if (!P.NativeBiometric) return Promise.resolve(false);
    return P.NativeBiometric.isAvailable().then(function (r) { return !!(r && r.isAvailable); }).catch(function () { return false; });
  }
  function biometricVerify() {
    if (!P.NativeBiometric) return Promise.reject();
    return P.NativeBiometric.verifyIdentity({ reason: t("bio_reason"), title: "Auralis Natura", subtitle: "", description: "" });
  }
  function biometricSave(cid, pw) { if (P.NativeBiometric) return P.NativeBiometric.setCredentials({ username: cid, password: pw, server: "auralisnatura.com" }).catch(function () {}); return Promise.resolve(); }
  function biometricLoad() { if (P.NativeBiometric) return P.NativeBiometric.getCredentials({ server: "auralisnatura.com" }).catch(function () { return null; }); return Promise.resolve(null); }
  function biometricClear() { if (P.NativeBiometric) return P.NativeBiometric.deleteCredentials({ server: "auralisnatura.com" }).catch(function () {}); return Promise.resolve(); }
  function registerPush() {
    var FM = P.FirebaseMessaging; if (!FM) return Promise.resolve(false);
    return FM.requestPermissions().then(function () { return FM.getToken(); }).then(function (r) {
      if (r && r.token) return api("/api/app/push-token", { method: "POST", body: { token: r.token, platform: Cap.getPlatform ? Cap.getPlatform() : "native" } }).then(function () { return true; });
      return false;
    }).catch(function () { return false; });
  }
  function maybeRegisterPush() { Store.get("an_push").then(function (v) { if (v === "1") registerPush(); }); }

  /* ---------- i18n ---------- */
  var T = {
    de: {
      lang: "de", welcome_back: "Willkommen zurück", login_sub: "Melde dich an, um deinen Fragebogen und Bericht zu sehen.",
      client_id: "Kunden-ID", password: "Passwort", sign_in: "Anmelden", use_faceid: "Mit Face ID anmelden", use_password: "Passwort verwenden",
      login_foot: "DSGVO-konform · verschlüsselt", bio_reason: "Anmeldung bei Auralis Natura",
      hello: "Hallo", home_sub: "Schön, dass du da bist.",
      tab_home: "Start", tab_book: "Termin", tab_report: "Bericht", tab_shop: "Programme", tab_profile: "Profil",
      next_appt: "Nächster Termin", no_appt: "Kein Termin gebucht", book_now: "Termin buchen",
      your_path: "Dein Weg", report_ready: "Dein Bericht ist bereit", open_report: "Bericht öffnen", report_pending: "Dein Bericht wird vorbereitet",
      intake_todo: "Fragebogen ausfüllen", intake_sub: "Fülle deinen Aufnahmebogen aus — ca. 10 Minuten.",
      st_access: "Zugang erhalten", st_access_s: "Portal freigeschaltet", st_intake: "Fragebogen ausgefüllt", st_intake_s: "verschlüsselt gespeichert",
      st_prep: "Desiree bereitet vor", st_prep_s: "persönlich geprüft", st_report: "Bericht bereit", st_report_s: "du wirst benachrichtigt",
      book_title: "Termin buchen", pick_day: "Wähle einen Tag", pick_time: "Wähle eine Uhrzeit", no_slots: "Zurzeit keine Zeiten frei.",
      your_name: "Name", email: "E-Mail", note_opt: "Nachricht (optional)", confirm_book: "Termin bestätigen", booked_ok: "Termin bestätigt ✓ — Bestätigung per E-Mail.",
      consent_gdpr: "Ich stimme der Verarbeitung meiner Angaben gemäß DSGVO zu.",
      report_title: "Dein Bericht", report_none: "Sobald dein persönlicher Bericht fertig ist, findest du ihn hier.", download_pdf: "PDF öffnen",
      shop_title: "Programme", shop_sub: "Wähle das Programm, das zu dir passt.", buy: "Jetzt buchen", enquire: "Kostenloses Kennenlernen",
      shop_trust: "Sichere Zahlung über Stripe. Nach der Zahlung meldet sich Desiree persönlich bei dir.",
      profile_title: "Profil", language: "Sprache", logout: "Abmelden", contact: "Kontakt", contact_us: "Schreib uns",
      loading: "Lädt …", offline: "Offline — zeige gespeicherte Daten.", err_generic: "Etwas ist schiefgelaufen. Bitte erneut versuchen.",
      err_login: "Kunden-ID oder Passwort stimmt nicht.", saved: "Gespeichert", required: "Bitte ausfüllen.", most_chosen: "Unsere Empfehlung"
    },
    en: {
      lang: "en", welcome_back: "Welcome back", login_sub: "Sign in to see your questionnaire and report.",
      client_id: "Client ID", password: "Password", sign_in: "Sign in", use_faceid: "Sign in with Face ID", use_password: "Use password",
      login_foot: "GDPR-compliant · encrypted", bio_reason: "Sign in to Auralis Natura",
      hello: "Hello", home_sub: "Good to see you.",
      tab_home: "Home", tab_book: "Booking", tab_report: "Report", tab_shop: "Programmes", tab_profile: "Profile",
      next_appt: "Next appointment", no_appt: "No appointment booked", book_now: "Book a call",
      your_path: "Your journey", report_ready: "Your report is ready", open_report: "Open report", report_pending: "Your report is being prepared",
      intake_todo: "Complete your questionnaire", intake_sub: "Fill in your intake — about 10 minutes.",
      st_access: "Access granted", st_access_s: "portal unlocked", st_intake: "Questionnaire done", st_intake_s: "encrypted & saved",
      st_prep: "Desiree is preparing", st_prep_s: "personally reviewed", st_report: "Report ready", st_report_s: "you'll be notified",
      book_title: "Book a call", pick_day: "Choose a day", pick_time: "Choose a time", no_slots: "No times available right now.",
      your_name: "Name", email: "Email", note_opt: "Message (optional)", confirm_book: "Confirm booking", booked_ok: "Booked ✓ — confirmation by email.",
      consent_gdpr: "I consent to processing my data under the GDPR.",
      report_title: "Your report", report_none: "As soon as your personal report is ready, you'll find it here.", download_pdf: "Open PDF",
      shop_title: "Programmes", shop_sub: "Choose the programme that fits you.", buy: "Book now", enquire: "Free intro call",
      shop_trust: "Secure payment via Stripe. After payment, Desiree will personally get in touch.",
      profile_title: "Profile", language: "Language", logout: "Sign out", contact: "Contact", contact_us: "Write to us",
      loading: "Loading …", offline: "Offline — showing saved data.", err_generic: "Something went wrong. Please try again.",
      err_login: "Client ID or password is incorrect.", saved: "Saved", required: "Please complete this.", most_chosen: "Our recommendation"
    },
    es: {
      lang: "es", welcome_back: "Bienvenida de nuevo", login_sub: "Inicia sesión para ver tu cuestionario e informe.",
      client_id: "ID de cliente", password: "Contraseña", sign_in: "Entrar", use_faceid: "Entrar con Face ID", use_password: "Usar contraseña",
      login_foot: "Conforme al RGPD · cifrado", bio_reason: "Iniciar sesión en Auralis Natura",
      hello: "Hola", home_sub: "Qué bueno verte.",
      tab_home: "Inicio", tab_book: "Cita", tab_report: "Informe", tab_shop: "Programas", tab_profile: "Perfil",
      next_appt: "Próxima cita", no_appt: "Sin cita reservada", book_now: "Reservar llamada",
      your_path: "Tu camino", report_ready: "Tu informe está listo", open_report: "Abrir informe", report_pending: "Tu informe se está preparando",
      intake_todo: "Completa tu cuestionario", intake_sub: "Rellena tu cuestionario — unos 10 minutos.",
      st_access: "Acceso concedido", st_access_s: "portal activado", st_intake: "Cuestionario hecho", st_intake_s: "cifrado y guardado",
      st_prep: "Desiree está preparando", st_prep_s: "revisado personalmente", st_report: "Informe listo", st_report_s: "te avisaremos",
      book_title: "Reservar llamada", pick_day: "Elige un día", pick_time: "Elige una hora", no_slots: "No hay horas disponibles ahora.",
      your_name: "Nombre", email: "Correo", note_opt: "Mensaje (opcional)", confirm_book: "Confirmar cita", booked_ok: "Reservado ✓ — confirmación por correo.",
      consent_gdpr: "Doy mi consentimiento para tratar mis datos según el RGPD.",
      report_title: "Tu informe", report_none: "En cuanto tu informe personal esté listo, lo verás aquí.", download_pdf: "Abrir PDF",
      shop_title: "Programas", shop_sub: "Elige el programa que encaja contigo.", buy: "Reservar ahora", enquire: "Llamada gratuita",
      shop_trust: "Pago seguro con Stripe. Tras el pago, Desiree se pondrá en contacto contigo.",
      profile_title: "Perfil", language: "Idioma", logout: "Salir", contact: "Contacto", contact_us: "Escríbenos",
      loading: "Cargando …", offline: "Sin conexión — mostrando datos guardados.", err_generic: "Algo salió mal. Inténtalo de nuevo.",
      err_login: "ID de cliente o contraseña incorrectos.", saved: "Guardado", required: "Por favor complétalo.", most_chosen: "Nuestra recomendación"
    }
  };
  var EXTRA = {
    de: { book_sub: "Wähle eine Zeit für dein Gespräch", report_inside: "Was dich erwartet", enable_reminders: "Erinnerungen aktivieren", reminders_on: "Erinnerungen aktiviert ✓", privacy: "Datenschutz & AGB", flourish_note: "Beginnt mit einem kostenlosen Kennenlern-Gespräch.",
      balance: "Balance", wellbeing_title: "Dein Wohlbefinden", priorities_title: "Deine Prioritäten", habits_title: "Heute", notifications: "Benachrichtigungen", delete_data: "Meine Daten löschen", delete_confirm: "Wirklich löschen? Tippen zum Bestätigen", delete_sent: "Anfrage gesendet — Desiree meldet sich.",
      sc_high: "Ausgewogen", sc_mid: "Auf gutem Weg", sc_low: "Aufbauphase", sc_min: "Sanft beginnen", first_step: "Erster Schritt", morn: "Vormittag", aft: "Nachmittag" },
    en: { book_sub: "Pick a time for your call", report_inside: "What's inside", enable_reminders: "Enable reminders", reminders_on: "Reminders enabled ✓", privacy: "Privacy & Terms", flourish_note: "Starts with a free intro call.",
      balance: "Balance", wellbeing_title: "Your wellbeing", priorities_title: "Your priorities", habits_title: "Today", notifications: "Notifications", delete_data: "Delete my data", delete_confirm: "Really delete? Tap to confirm", delete_sent: "Request sent — Desiree will be in touch.",
      sc_high: "Balanced", sc_mid: "On a good path", sc_low: "Building up", sc_min: "Start gently", first_step: "First step", morn: "Morning", aft: "Afternoon" },
    es: { book_sub: "Elige una hora para tu llamada", report_inside: "Qué encontrarás", enable_reminders: "Activar recordatorios", reminders_on: "Recordatorios activados ✓", privacy: "Privacidad y términos", flourish_note: "Empieza con una llamada gratuita.",
      balance: "Balance", wellbeing_title: "Tu bienestar", priorities_title: "Tus prioridades", habits_title: "Hoy", notifications: "Notificaciones", delete_data: "Eliminar mis datos", delete_confirm: "¿Eliminar de verdad? Toca para confirmar", delete_sent: "Solicitud enviada — Desiree te contactará.",
      sc_high: "Equilibrada", sc_mid: "Buen camino", sc_low: "En construcción", sc_min: "Empieza con calma", first_step: "Primer paso", morn: "Mañana", aft: "Tarde" }
  };
  Object.keys(EXTRA).forEach(function (l) { for (var k in EXTRA[l]) T[l][k] = EXTRA[l][k]; });
  // what's included per programme (matches the website's service ladder)
  var FEATS = {
    root: { de: ["Tiefengespräch mit Desiree", "Dein ganzheitlicher, professioneller Bericht", "Wochenplan & Habits"],
            en: ["Deep-dive session with Desiree", "Your holistic, professional report", "Weekly plan & habits"],
            es: ["Sesión profunda con Desiree", "Tu informe integral y profesional", "Plan semanal y hábitos"] },
    bloom: { de: ["Alles aus Klarheit", "4 Wochen persönliche Begleitung", "Yoga- & Meditations-Impulse"],
             en: ["Everything in Clarity", "4 weeks of personal guidance", "Yoga & meditation impulses"],
             es: ["Todo lo de Claridad", "4 semanas de acompañamiento", "Impulsos de yoga y meditación"] },
    flourish: { de: ["Alles aus Wandel", "12 Wochen intensive Begleitung", "Fortlaufende Anpassung deines Plans"],
                en: ["Everything in Change", "12 weeks of close guidance", "Ongoing plan refinement"],
                es: ["Todo lo de Cambio", "12 semanas de acompañamiento", "Ajuste continuo de tu plan"] }
  };
  var REPORT_CH = {
    de: ["Dein Ausgangspunkt", "Was wir sehen", "Die Wissenschaft, einfach", "Dein Plan", "Wann du ärztlichen Rat suchst", "Deine nächsten Schritte"],
    en: ["Your starting point", "What we're seeing", "The science, simply", "Your plan", "When to see a doctor", "Your next steps"],
    es: ["Tu punto de partida", "Lo que observamos", "La ciencia, en simple", "Tu plan", "Cuándo consultar al médico", "Tus próximos pasos"]
  };
  var LANG = "de";
  function t(k) { return (T[LANG] && T[LANG][k]) || T.de[k] || k; }
  function applyLang() { try { document.documentElement.lang = LANG; } catch (e) {} }

  /* ---------- API client ---------- */
  function api(path, opts) {
    opts = opts || {};
    var headers = { "Content-Type": "application/json" };
    if (opts.auth !== false && SESSION.token) headers["Authorization"] = "Bearer " + SESSION.token;
    var ctrl = new AbortController();
    var timer = setTimeout(function () { ctrl.abort(); }, opts.timeout || 15000);
    return fetch(API + path, {
      method: opts.method || "GET", headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined, signal: ctrl.signal
    }).then(function (r) {
      clearTimeout(timer);
      return r.text().then(function (txt) {
        var data; try { data = txt ? JSON.parse(txt) : {}; } catch (e) { data = { raw: txt }; }
        if (!r.ok) { var err = new Error(data.error || ("HTTP " + r.status)); err.status = r.status; err.data = data; throw err; }
        return data;
      });
    }).catch(function (e) { clearTimeout(timer); throw e; });
  }

  /* ---------- session ---------- */
  var SESSION = { token: null, cid: null, name: "", me: null };
  var OFFERS = CFG.OFFERS || [];

  /* ---------- toast ---------- */
  var toastT;
  function toast(msg, ms) {
    var box = $("#toast"); box.innerHTML = msg; box.classList.add("show");
    clearTimeout(toastT); toastT = setTimeout(function () { box.classList.remove("show"); }, ms || 2600);
  }

  /* ---------- chrome ---------- */
  var host;
  function mount(node, tab) {
    host.innerHTML = ""; host.appendChild(node); host.scrollTop = 0;
    var bar = $("#tabbar");
    if (tab) {
      bar.hidden = false;
      var tabs = bar.querySelectorAll(".tb"), ix = 0;
      [].forEach.call(tabs, function (b, i) { var on = b.dataset.tab === tab; b.classList.toggle("on", on); if (on) ix = i; });
      var ind = bar.querySelector(".tab-ind");
      if (ind) ind.style.left = "calc(" + ((ix + 0.5) * (100 / tabs.length)).toFixed(2) + "% - 13px)";
    } else { bar.hidden = true; }
  }
  function topbar(title, action) {
    return '<header class="topbar"><div class="tb-left"><img src="assets/seal.png" alt=""><span class="tb-title">' + esc(title) + '</span></div>' +
      (action || "") + '</header>';
  }

  /* ============================================================
     VIEWS
     ============================================================ */

  /* ---- LOGIN ---- */
  function viewLogin(prefillBio) {
    var node = el(
      '<section class="login">' +
      '<div class="brand"><img src="assets/seal.png" alt=""><div class="wm">Auralis Natura</div>' +
      '<div class="kick" style="text-align:center;margin-top:3px">Client Portal</div><span class="grule center"></span></div>' +
      '<h1>' + t("welcome_back") + '</h1><p class="sub">' + t("login_sub") + '</p>' +
      '<div class="langrow" id="lgLang"></div>' +
      '<label for="cid">' + t("client_id") + '</label><input id="cid" type="text" autocapitalize="characters" autocomplete="username" placeholder="AN-0001" inputmode="text">' +
      '<label for="pw">' + t("password") + '</label><input id="pw" type="password" autocomplete="current-password">' +
      '<div class="err" id="lgErr"></div>' +
      '<button class="btn" id="lgGo"><span class="sheen"></span>' + t("sign_in") + '</button>' +
      '<div id="lgBioWrap" class="hidden" style="margin-top:10px"><button class="btn ghost" id="lgBio">' + t("use_faceid") + '</button></div>' +
      '<div class="foot">' + t("login_foot") + '</div>' +
      '</section>'
    );
    mount(node, null);
    renderLangRow($("#lgLang", node), function () { mount(viewLogin(prefillBio), null); });

    var go = $("#lgGo", node), errBox = $("#lgErr", node);
    function doLogin(cid, pw, viaBio) {
      errBox.textContent = ""; go.disabled = true; go.innerHTML = '<span class="spin"></span>';
      api("/api/login", { auth: false, method: "POST", body: { client_id: cid, password: pw } })
        .then(function (r) { return onLoggedIn(r, cid, pw, viaBio); })
        .catch(function (e) {
          go.disabled = false; go.innerHTML = t("sign_in"); haptic("Heavy");
          errBox.textContent = (e && e.status === 401) ? t("err_login") : t("err_generic");
        });
    }
    go.addEventListener("click", function () {
      var cid = $("#cid", node).value.trim().toUpperCase(), pw = $("#pw", node).value;
      if (!cid || !pw) { errBox.textContent = t("required"); return; }
      doLogin(cid, pw, false);
    });

    // biometric option if credentials were saved
    biometricAvailable().then(function (ok) {
      if (!ok) return;
      biometricLoad().then(function (cred) {
        if (cred && cred.username && cred.password) {
          $("#lgBioWrap", node).classList.remove("hidden");
          $("#lgBio", node).addEventListener("click", function () {
            biometricVerify().then(function () { doLogin(cred.username, cred.password, true); }).catch(function () {});
          });
          if (prefillBio) $("#lgBio", node).click();
        }
      });
    });
    return node;
  }

  function onLoggedIn(r, cid, pw, viaBio) {
    SESSION.token = r.token; SESSION.cid = r.client_id || cid; SESSION.name = r.name || "";
    if (r.language && T[r.language]) LANG = r.language;
    return Promise.all([
      Store.set("an_token", SESSION.token), Store.set("an_cid", SESSION.cid),
      Store.set("an_name", SESSION.name), Store.set("an_lang", LANG),
      (!viaBio && pw) ? biometricSave(cid, pw) : Promise.resolve()
    ]).then(function () {
      haptic("Medium"); applyLang(); loadOffers();
      maybeRegisterPush();           // only if the user previously enabled reminders
      goTab("home");                 // paints, then refreshes + re-renders (see goTab)
    });
  }

  /* ---- HOME ---- */
  function viewHome() {
    var node = el('<section class="view has-topbar">' + topbar("Auralis Natura") + '<div class="wrap" id="homeBody"></div></section>');
    mount(node, "home");
    var body = $("#homeBody", node);
    body.innerHTML =
      '<div class="hero-greet"><h1>' + t("hello") + (SESSION.name ? " " + esc(SESSION.name.split(" ")[0]) : "") + '</h1>' +
      '<div class="sub">' + t("home_sub") + '</div></div><div id="homeCards"><div class="card"><div class="skel" style="width:60%"></div><div class="skel"></div></div></div>';
    hydrateHome($("#homeCards", node));
    return node;
  }
  /* shared inline icon set (1.6px stroke, matches the tab bar family) */
  var ICO = {
    bell: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M6 10a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>',
    mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="5" width="18" height="14"/><path d="m3 7 9 6 9-6"/></svg>',
    shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M12 3l7 3v6c0 5-3.5 7.5-7 9-3.5-1.5-7-4-7-9V6z"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></svg>',
    exit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M9 4H5v16h4M14 8l4 4-4 4M8 12h10"/></svg>',
    chev: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="m9 5 7 7-7 7"/></svg>'
  };
  function plRow(id, ico, label, tone) {
    return '<button class="pl-row' + (tone ? " pl-" + tone : "") + '" id="' + id + '">' +
      '<span class="pl-ico">' + ico + '</span><span class="pl-lab">' + esc(label) + '</span><span class="pl-chev">' + ICO.chev + '</span></button>';
  }
  // gentle, non-diagnostic read of the 4 scales (guardrail §2: educational, warm)
  function insight(scales) {
    var arr = Object.keys(scales).map(function (k) { return { k: k, g: (k === "stress" ? 6 - scales[k] : scales[k]) }; });
    arr.sort(function (a, b) { return b.g - a.g; });
    var top = arr.slice(0, 2).map(function (x) { return AN_VIZ.label(x.k, LANG); });
    var low = AN_VIZ.label(arr[arr.length - 1].k, LANG);
    return { de: top.join(" und ") + " führen heute — " + low + " ist der Punkt, auf den wir sanft schauen.",
             en: top.join(" and ") + " are leading today — " + low + " is the one to gently watch.",
             es: top.join(" y ") + " van por delante — " + low + " es lo que observamos con calma." }[LANG] || "";
  }
  function hydrateHome(cont) {
    var me = SESSION.me || {};
    var stage = me.stage || "invited";
    var order = ["lead", "call", "won", "invited", "intake", "prep", "draft", "review", "sent", "done"];
    function ix(s) { return order.indexOf(s); }
    var hasIntake = !!me.has_intake, reportReady = !!me.report_ready;
    var wb = me.wellbeing || {}, scales = wb.scales || {}, score = wb.score;
    var hasScales = Object.keys(scales).length >= 3;
    var html = "";

    // 1 · HERO — the Bloom specimen plate (4 scales + centre Balance + insight)
    if (hasScales && score != null) {
      html += '<div class="hero-plate"><div class="fig">Fig. 01 — ' + t("balance") + '</div>' +
        AN_VIZ.bloom(scales, score, LANG) +
        '<div class="hero-insight">' + esc(insight(scales)) + '</div></div>';
    }

    // 2 · primary status card (report ready / intake to do / in preparation)
    if (reportReady) {
      html += '<div class="card ready"><div class="ck">' + t("report_title") + '</div><div class="cv">' + t("report_ready") + '</div>' +
        '<div style="margin-top:10px"><button class="btn gold" data-go="open-report"><span class="sheen"></span>' + t("open_report") + '</button></div></div>';
    } else if (!hasIntake && ix(stage) >= ix("invited")) {
      html += '<div class="card accent"><div class="ck">' + t("intake_todo") + '</div><div class="muted" style="margin-top:4px">' + t("intake_sub") + '</div>' +
        '<div style="margin-top:10px"><button class="btn" data-go="intake"><span class="sheen"></span>' + t("intake_todo") + '</button></div></div>';
    } else if (hasIntake) {
      html += '<div class="card accent"><div class="ck">' + t("report_title") + '</div><div class="cv">' + t("report_pending") + '</div>' +
        '<div class="muted" style="margin-top:4px">' + t("st_prep_s") + '</div></div>';
    }

    // 3 · wellbeing detail — Ampel bars (the numbers behind the bloom)
    if (hasScales) {
      html += '<div class="sec-h"><h2>' + t("wellbeing_title") + '</h2></div>' +
        '<div class="card">' + AN_VIZ.bars(scales, LANG) + '</div>';
    }

    // 4 · priorities from the report
    if (me.priorities && me.priorities.length) {
      html += '<div class="sec-h"><h2>' + t("priorities_title") + '</h2></div>' +
        me.priorities.map(function (p, i) {
          return '<div class="card prio"><span class="prio-n num">0' + (i + 1) + '</span><div><div class="prio-t">' + esc(p.title) + '</div>' +
            (p.first_step ? '<div class="prio-s"><span class="kick">' + t("first_step") + '</span> ' + esc(p.first_step) + '</div>' : "") + '</div></div>';
        }).join("");
    }

    // 5 · habits (tappable daily streak)
    if (me.habits && me.habits.length) {
      html += '<div class="sec-h"><h2>' + t("habits_title") + '</h2></div><div class="card">' + AN_VIZ.habits(me.habits) + '</div>';
    }

    // 6 · journey tracker
    var steps = [
      { done: true, now: false, tt: t("st_access"), s: t("st_access_s") },
      { done: hasIntake, now: !hasIntake, tt: t("st_intake"), s: t("st_intake_s") },
      { done: ix(stage) >= ix("review"), now: hasIntake && ix(stage) < ix("review") && !reportReady, tt: t("st_prep"), s: t("st_prep_s") },
      { done: reportReady, now: false, tt: t("st_report"), s: t("st_report_s") }
    ];
    html += '<div class="sec-h"><h2>' + t("your_path") + '</h2></div><div class="card"><div class="trk">' +
      steps.map(function (st) {
        return '<div class="st ' + (st.done ? "done" : st.now ? "now" : "") + '"><div class="dot">' + (st.done ? "✓" : "") + '</div>' +
          '<div class="tt">' + esc(st.tt) + '<span>' + esc(st.s) + '</span></div></div>';
      }).join("") + '</div></div>';

    // 7 · booking CTA
    html += '<div class="sec-h"><h2>' + t("next_appt") + '</h2></div>' +
      '<div class="card tap" data-go="book"><div class="cv">' + t("book_title") + '</div>' +
      '<div class="muted" style="margin-top:2px">' + t("book_sub") + ' →</div></div>';

    cont.innerHTML = html;
    [].forEach.call(cont.querySelectorAll("[data-go]"), function (b) {
      b.addEventListener("click", function () { var g = b.dataset.go; if (g === "open-report") openReport(); else goTab(g); });
    });
    wireHabits(cont);
    AN_VIZ.play(cont);
    if (hasScales && score != null) setTimeout(function () { haptic("Light"); }, 820);  // the "your bloom landed" settle
  }
  // daily habit toggle, persisted per calendar day
  function wireHabits(root) {
    var day = new Date().toISOString().slice(0, 10), key = "an_habits_" + day;
    Store.get(key).then(function (v) {
      var done = {}; try { done = v ? JSON.parse(v) : {}; } catch (e) {}
      [].forEach.call(root.querySelectorAll(".viz-habit"), function (b) {
        var i = b.dataset.h; if (done[i]) b.classList.add("done");
        b.addEventListener("click", function () {
          b.classList.toggle("done"); done[i] = b.classList.contains("done"); haptic();
          Store.set(key, JSON.stringify(done));
        });
      });
    });
  }

  /* ---- BOOKING ---- */
  function viewBook() {
    var node = el('<section class="view has-topbar">' + topbar(t("book_title")) + '<div class="wrap" id="bkBody"><div class="center-pad"><span class="spin"></span> ' + t("loading") + '</div></div></section>');
    mount(node, "book");
    var body = $("#bkBody", node);
    var state = { slot: null, dayIx: 0, days: [] };
    api("/api/booking/slots", { auth: false }).then(function (r) {
      state.days = r.days || [];
      if (!state.days.length) { body.innerHTML = '<div class="center-pad">' + t("no_slots") + '</div>'; return; }
      renderBook(body, state);
    }).catch(function () { body.innerHTML = '<div class="center-pad">' + t("no_slots") + '</div>'; });
    return node;
  }
  function renderBook(body, state) {
    var day = state.days[state.dayIx];
    body.innerHTML =
      '<label>' + t("pick_day") + '</label><div class="chips" id="bkDays">' +
      state.days.map(function (d, i) { return '<button class="chip ' + (i === state.dayIx ? "on" : "") + '" data-d="' + i + '">' + esc(d.label) + '</button>'; }).join("") + '</div>' +
      '<label>' + t("pick_time") + '</label>' +
      (function () {
        var am = day.slots.filter(function (s) { return +s.local.slice(0, 2) < 12; });
        var pm = day.slots.filter(function (s) { return +s.local.slice(0, 2) >= 12; });
        function grp(list, lab) {
          if (!list.length) return "";
          return '<div class="figtag" style="margin:10px 0 6px">' + lab + '</div><div class="chips bk-slots">' +
            list.map(function (s) { return '<button class="chip num" data-s="' + esc(s.utc) + '">' + esc(s.local) + '</button>'; }).join("") + '</div>';
        }
        return '<div id="bkSlots">' + grp(am, t("morn")) + grp(pm, t("aft")) + '</div>';
      })() +
      '<div id="bkForm" class="hidden"><label>' + t("your_name") + '</label><input id="bkName" type="text" value="' + esc(SESSION.name) + '">' +
      '<label>' + t("email") + '</label><input id="bkMail" type="email" inputmode="email">' +
      '<label>' + t("note_opt") + '</label><textarea id="bkNote"></textarea>' +
      '<label class="chk"><input type="checkbox" id="bkC"> <span>' + t("consent_gdpr") + '</span></label>' +
      '<div class="err" id="bkErr"></div>' +
      '<button class="btn" id="bkGo"><span class="sheen"></span>' + t("confirm_book") + '</button></div>';
    [].forEach.call(body.querySelectorAll("#bkDays .chip"), function (b) {
      b.addEventListener("click", function () { state.dayIx = +b.dataset.d; state.slot = null; renderBook(body, state); });
    });
    [].forEach.call(body.querySelectorAll("#bkSlots .chip"), function (b) {
      b.addEventListener("click", function () {
        [].forEach.call(body.querySelectorAll("#bkSlots .chip"), function (x) { x.classList.remove("on"); });
        b.classList.add("on"); state.slot = b.dataset.s; $("#bkForm", body).classList.remove("hidden"); haptic();
      });
    });
    var go = $("#bkGo", body);
    if (go) go.addEventListener("click", function () {
      var err = $("#bkErr", body);
      var name = $("#bkName", body).value.trim(), mail = $("#bkMail", body).value.trim(), note = $("#bkNote", body).value.trim();
      if (!state.slot || !name || !mail) { err.textContent = t("required"); return; }
      if (!$("#bkC", body).checked) { err.textContent = t("consent_gdpr"); return; }
      go.disabled = true; go.innerHTML = '<span class="spin"></span>';
      api("/api/booking/book", { auth: false, method: "POST", body: {
        slot: state.slot, name: name, email: mail, language: LANG, note: note,
        consent: { gdpr: true, health_data: true }
      } }).then(function () { hapticSuccess(); toast(t("booked_ok")); goTab("home"); })
        .catch(function () { go.disabled = false; go.innerHTML = t("confirm_book"); err.textContent = t("err_generic"); });
    });
  }

  /* ---- INTAKE (deep questionnaire) ---- */
  function viewIntake() {
    var scales = ["energy", "sleep", "stress", "digestion"];
    var slabel = { energy: { de: "Energie", en: "Energy", es: "Energía" }, sleep: { de: "Schlaf", en: "Sleep", es: "Sueño" }, stress: { de: "Stress", en: "Stress", es: "Estrés" }, digestion: { de: "Verdauung", en: "Digestion", es: "Digestión" } };
    var node = el('<section class="view has-topbar">' + topbar(t("intake_todo")) + '<div class="wrap" id="inBody"></div></section>');
    mount(node, "home");
    var body = $("#inBody", node);
    var picks = { energy: 3, sleep: 3, stress: 3, digestion: 3 };
    body.innerHTML =
      '<p class="muted" style="margin:8px 0 2px">' + t("intake_sub") + '</p>' +
      '<label>Ziel / Goal</label><textarea id="inGoal"></textarea>' +
      '<label>Warum jetzt? / Why now?</label><textarea id="inWhy"></textarea>' +
      scales.map(function (k) {
        return '<label>' + esc(slabel[k][LANG] || slabel[k].de) + ' (1–5)</label><div class="scale" data-k="' + k + '">' +
          [1, 2, 3, 4, 5].map(function (n) { return '<button data-n="' + n + '" class="' + (n === 3 ? "on" : "") + '">' + n + '</button>'; }).join("") + '</div>';
      }).join("") +
      '<label class="chk"><input type="checkbox" id="inC1"> <span>Coaching &amp; Bildung, keine medizinische Versorgung.</span></label>' +
      '<label class="chk"><input type="checkbox" id="inC2"> <span>' + t("consent_gdpr") + '</span></label>' +
      '<div class="err" id="inErr"></div>' +
      '<button class="btn" id="inGo"><span class="sheen"></span>' + t("intake_todo") + '</button>';
    [].forEach.call(body.querySelectorAll(".scale"), function (sc) {
      sc.addEventListener("click", function (e) {
        var b = e.target.closest("button"); if (!b) return;
        [].forEach.call(sc.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
        b.classList.add("on"); picks[sc.dataset.k] = +b.dataset.n; haptic();
      });
    });
    $("#inGo", body).addEventListener("click", function () {
      var err = $("#inErr", body);
      if (!$("#inC1", body).checked || !$("#inC2", body).checked) { err.textContent = t("consent_gdpr"); return; }
      var go = $("#inGo", body); go.disabled = true; go.innerHTML = '<span class="spin"></span>';
      api("/api/intake", { method: "POST", body: {
        goal: $("#inGoal", body).value.trim(), why_now: $("#inWhy", body).value.trim(),
        b: picks, language: LANG, red_flags: ["none"],
        consent: { coaching_not_medical: true, gdpr_health_data: true }
      } }).then(function () { haptic("Medium"); toast(t("saved")); return refreshMe(); }).then(function () { goTab("home"); })
        .catch(function () { go.disabled = false; go.innerHTML = t("intake_todo"); err.textContent = t("err_generic"); });
    });
    return node;
  }

  /* ---- REPORT ---- */
  function viewReport() {
    var node = el('<section class="view has-topbar">' + topbar(t("report_title")) + '<div class="wrap" id="rpBody"></div></section>');
    mount(node, "report");
    var body = $("#rpBody", node);
    var ready = SESSION.me && SESSION.me.report_ready;
    if (ready) {
      var chapters = REPORT_CH[LANG] || REPORT_CH.de;
      var wb = (SESSION.me && SESSION.me.wellbeing) || {};
      var mini = (wb.scales && Object.keys(wb.scales).length >= 3) ? AN_VIZ.bloom(wb.scales, wb.score, LANG, { compact: true }) : '<img src="assets/seal.png" alt="" style="width:56px;height:56px;margin:0 auto 8px">';
      body.innerHTML = '<div class="rpage"><div class="figtag">Fig. 02 — ' + t("report_title") + '</div>' +
        mini +
        '<h2>' + esc(SESSION.name || "") + '</h2><span class="grule center"></span>' +
        '<p class="muted" style="margin-top:10px">' + t("report_ready") + '</p>' +
        '<div class="spark" style="justify-content:center;margin-top:10px"><i></i><i></i><i></i></div></div>' +
        '<button class="btn gold" id="rpDl"><span class="sheen"></span>' + t("download_pdf") + '</button>' +
        '<div class="sec-h"><h2>' + t("report_inside") + '</h2></div><div class="card" style="padding-top:6px;padding-bottom:6px">' +
        chapters.map(function (c, i) { return '<div class="rch" style="display:flex;gap:12px;align-items:center;padding:12px 0' + (i ? ';border-top:1px solid var(--line)' : '') + '"><span class="num" style="color:var(--gold);font-family:var(--fd);font-size:1.15rem">0' + (i + 1) + '</span><span style="font-family:var(--fd);font-size:1.02rem;color:var(--forest)">' + esc(c) + '</span></div>'; }).join("") + '</div>';
      $("#rpDl", body).addEventListener("click", openReport);
      AN_VIZ.play(body);
    } else {
      body.innerHTML = '<div class="center-pad"><img src="assets/seal.png" alt="" style="width:60px;opacity:.5;margin:0 auto 14px"><p>' + t("report_none") + '</p></div>';
    }
    return node;
  }
  function openReport() {
    // mint a short-lived (90s) report-only token so the 24h session bearer never
    // travels in a URL / browser history / access logs
    api("/api/my/report-token", { method: "POST" }).then(function (r) {
      openExternal(API + "/api/my/report?token=" + encodeURIComponent(r.token));
    }).catch(function (e) { if (e && e.status === 401) forceLogin(); else toast(t("err_generic")); });
  }

  /* ---- SHOP ---- */
  function loadOffers() {
    // lang rides along: the server picks the payment link AND the localised
    // programme name per language — without it every reader got German.
    api("/api/app/offers?lang=" + LANG, { auth: false })
      .then(function (r) { if (r && r.offers && r.offers.length) OFFERS = r.offers; })
      .catch(function () {});
  }

  function viewShop() {
    loadOffers();
    var node = el('<section class="view has-topbar">' + topbar(t("shop_title")) + '<div class="wrap" id="shBody"></div></section>');
    mount(node, "shop");
    var body = $("#shBody", node);
    body.innerHTML = '<p class="muted" style="margin:8px 0 2px">' + t("shop_sub") + '</p>' +
      OFFERS.map(function (o, i) {
        var feat = o.key === "bloom";
        var canBuy = /^https:\/\//i.test(o.buy_url || "");
        var price = Number(o.price) || 0;
        var fl = (FEATS[o.key] || {})[LANG] || (FEATS[o.key] || {}).de || [];
        return '<div class="card ' + (feat ? "pkg-feat" : "") + '"><div class="pkg">' +
          // specimen number only — root/bloom/flourish are internal keys, not customer vocabulary
          '<span class="figtag">Fig. 0' + (i + 1) + '</span>' +
          (feat ? '<span class="badge">' + t("most_chosen") + '</span>' : "") +
          '<div class="pn">' + esc(o.name) + '</div><div class="pt">' + esc(o.tagline || "") + '</div>' +
          (fl.length ? '<ul class="pfeats">' + fl.map(function (f) { return '<li>' + esc(f) + '</li>'; }).join("") + '</ul>' : "") +
          '<div class="pp num">' + (price ? "€" + price + " <small>" + ({de:"einmalig",en:"one-time",es:"pago único"}[LANG]||"einmalig") + "</small>" : "") + '</div>' +
          '<div style="margin-top:12px"><button class="btn ' + (feat ? "gold" : "forest") + '" data-buy="' + i + '"><span class="sheen"></span>' +
          (canBuy ? t("buy") : t("enquire")) + '</button></div>' +
          (!canBuy && price ? '<div class="muted" style="margin-top:8px;font-size:.8rem">' + t("flourish_note") + '</div>' : "") +
          '</div></div>';
      }).join("") +
      '<p class="trust">' + t("shop_trust") + '</p>';
    [].forEach.call(body.querySelectorAll("[data-buy]"), function (b) {
      b.addEventListener("click", function () {
        var o = OFFERS[+b.dataset.buy]; haptic("Medium");
        if (/^https:\/\//i.test(o.buy_url || "")) openExternal(o.buy_url);
        else openExternal(CFG.BOOK_URL);  // no link yet → free intro call
      });
    });
    return node;
  }

  /* ---- PROFILE ---- */
  function viewProfile() {
    var node = el('<section class="view has-topbar">' + topbar(t("profile_title")) + '<div class="wrap" id="pfBody"></div></section>');
    mount(node, "profile");
    var body = $("#pfBody", node);
    body.innerHTML =
      '<div class="card"><div class="ck">' + t("client_id") + '</div><div class="cv num">' + esc(SESSION.cid || "") + '</div>' +
      '<div class="muted" style="margin-top:2px">' + esc(SESSION.name || "") + '</div></div>' +
      '<div class="sec-h"><h2>' + t("language") + '</h2></div><div class="langrow" id="pfLang"></div>' +
      '<div class="sec-h"><h2>' + t("profile_title") + '</h2></div>' +
      '<div class="card plist">' +
      plRow("pfPush", ICO.bell, t("enable_reminders")) +
      plRow("pfMail", ICO.mail, t("contact_us")) +
      plRow("pfPriv", ICO.shield, t("privacy")) +
      plRow("pfDel", ICO.trash, t("delete_data"), "warn") +
      plRow("pfOut", ICO.exit, t("logout"), "faint") +
      '</div>' +
      '<p class="trust">Auralis Natura — ' + (LANG === "de" ? "ganzheitliches Gesundheits- &amp; Ernährungscoaching (Bildung, keine medizinische Versorgung)." : LANG === "es" ? "coaching holístico (educación, no atención médica)." : "holistic health coaching (education, not medical care).") + '</p>';
    renderLangRow($("#pfLang", body), function () { mount(viewProfile(), "profile"); });
    function rowLab(id) { return $("#" + id + " .pl-lab", body); }
    Store.get("an_push").then(function (v) { if (v === "1") rowLab("pfPush").textContent = t("reminders_on"); });
    $("#pfPush", body).addEventListener("click", function () {
      registerPush().then(function (ok) { if (ok) { Store.set("an_push", "1"); rowLab("pfPush").textContent = t("reminders_on"); hapticSuccess(); } });
    });
    $("#pfMail", body).addEventListener("click", function () { openExternal("mailto:" + (CFG.CONTACT_EMAIL || "team@auralisnatura.com")); });
    $("#pfPriv", body).addEventListener("click", function () { openExternal(CFG.PRIVACY_URL); });
    // data deletion — 2-tap confirm, then a client-initiated request (operator completes)
    var delArmed = false;
    $("#pfDel", body).addEventListener("click", function () {
      if (!delArmed) { delArmed = true; rowLab("pfDel").textContent = t("delete_confirm"); haptic("Heavy"); return; }
      api("/api/my/delete-request", { method: "POST" }).then(function () { hapticSuccess(); toast(t("delete_sent")); }).catch(function () { toast(t("err_generic")); });
    });
    $("#pfOut", body).addEventListener("click", logout);
    return node;
  }

  /* ---- shared: language row ---- */
  function renderLangRow(cont, after) {
    cont.innerHTML = ["de", "en", "es"].map(function (l) {
      return '<button data-l="' + l + '" class="' + (l === LANG ? "on" : "") + '">' + l.toUpperCase() + '</button>';
    }).join(" · ").replace(/· /g, '<span style="opacity:.4">·</span> ');
    [].forEach.call(cont.querySelectorAll("button"), function (b) {
      b.addEventListener("click", function () { LANG = b.dataset.l; Store.set("an_lang", LANG); applyLang(); haptic(); if (after) after(); });
    });
  }

  /* ---------- navigation ---------- */
  var VIEWS = { home: viewHome, book: viewBook, report: viewReport, shop: viewShop, profile: viewProfile, intake: viewIntake };
  var SUBVIEW = null;  // e.g. "intake" — a Home sub-screen where back/resume must not exit or clobber
  function goTab(tab) {
    SUBVIEW = (tab === "intake") ? "intake" : null;
    (VIEWS[tab] || viewHome)();
    // freshen status when landing on Home/Report; re-render only if that view is
    // still mounted (marker) AND we're still logged in (never repaint over login)
    if ((tab === "home" || tab === "report") && SESSION.token) {
      var marker = tab === "home" ? "#homeBody" : "#rpBody";
      refreshMe().then(function () { if (SESSION.token && $(marker)) (VIEWS[tab])(); });
    }
  }
  function currentTab() { var on = $("#tabbar .tb.on"); return on ? on.dataset.tab : null; }
  function refreshMe() {
    // NOTE: we deliberately do NOT set LANG from me.language — the UI chrome follows
    // the user's own choice (persisted in an_lang); server language drives server-rendered
    // outputs (report/emails) only.
    return api("/api/me").then(function (me) { SESSION.me = me; Store.set("an_me", JSON.stringify(me)); return me; })
      .catch(function (e) {
        if (e && e.status === 401) { forceLogin(); }                 // expired/invalid token → re-login
        else if (SESSION.me) { toast(t("offline")); }                // network fail but we have cache
        return SESSION.me;
      });
  }
  function forceLogin() {
    SESSION = { token: null, cid: null, name: "", me: null };
    Promise.all([Store.remove("an_token"), Store.remove("an_cid"), Store.remove("an_name"), Store.remove("an_me")])
      .then(function () { mount(viewLogin(false), null); });
  }
  function loadOffers() {
    loadOffers();
  }
  function logout() {
    SESSION = { token: null, cid: null, name: "", me: null };
    Promise.all([Store.remove("an_token"), Store.remove("an_cid"), Store.remove("an_name"), Store.remove("an_me"), biometricClear()])
      .then(function () { haptic(); mount(viewLogin(false), null); });
  }

  // tab bar clicks
  $("#tabbar").addEventListener("click", function (e) {
    var b = e.target.closest(".tb"); if (!b) return; haptic(); goTab(b.dataset.tab);
  });
  // hardware back (Android)
  if (P.App) {
    P.App.addListener("backButton", function (info) {
      if ($("#tabbar").hidden) return;             // on login
      if (SUBVIEW) { goTab("home"); return; }      // e.g. intake → home, never exit/lose input
      var cur = $("#tabbar .tb.on"); if (cur && cur.dataset.tab !== "home") goTab("home"); else if (info.canGoBack === false) P.App.exitApp && P.App.exitApp();
    });
    // returning to the app → refresh status (report may have become ready)
    P.App.addListener("resume", function () {
      if ($("#tabbar").hidden || !SESSION.token || SUBVIEW) return;   // don't clobber an open sub-view
      var ct = currentTab(); if (ct === "home" || ct === "report") goTab(ct);
    });
    // deep links (e.g. from a push or the Stripe return URL) — bring the user home
    // for now; Universal Links / App Links can route to specific views later
    P.App.addListener("appUrlOpen", function () { if (!$("#tabbar").hidden) goTab("home"); });
  }

  /* ---------- boot ---------- */
  function onScroll() {
    var y = window.scrollY || document.documentElement.scrollTop || 0;
    var tb = document.querySelector(".topbar"); if (tb) tb.classList.toggle("scrolled", y > 4);
    var g = document.querySelector(".hero-greet");   // large title collapses on scroll (iOS tell)
    if (g) { var p = Math.min(1, y / 72); g.style.opacity = String(1 - p * 0.9); g.style.transform = "translateY(" + (-p * 6).toFixed(1) + "px)"; }
  }
  /* pull-to-refresh: at scroll-top on Home/Report, pull down → breathing seal → refresh */
  var _ptrY = null;
  function hidePtr() { var el = $("#ptr"); if (!el) return; el.classList.remove("spin"); el.style.opacity = "0"; el.style.transform = "translate(-50%,-70px)"; }
  function wirePtr() {
    document.addEventListener("touchstart", function (e) {
      _ptrY = null;
      if ($("#tabbar").hidden || SUBVIEW || (window.scrollY || 0) > 0) return;
      var ct = currentTab(); if (ct !== "home" && ct !== "report") return;
      _ptrY = e.touches[0].clientY;
    }, { passive: true });
    document.addEventListener("touchmove", function (e) {
      if (_ptrY == null) return;
      var dy = e.touches[0].clientY - _ptrY;
      if (dy <= 0) { hidePtr(); return; }
      var p = Math.min(1, dy / 110), el = $("#ptr");
      el.style.opacity = String(p);
      el.style.transform = "translate(-50%," + (-70 + p * 70).toFixed(0) + "px) rotate(" + (p * 180).toFixed(0) + "deg)";
    }, { passive: true });
    document.addEventListener("touchend", function () {
      if (_ptrY == null) return;
      var el = $("#ptr"), pulled = parseFloat(el.style.opacity || "0") >= 0.99;
      _ptrY = null;
      if (!pulled) { hidePtr(); return; }
      el.classList.add("spin"); haptic();
      refreshMe().then(function () {
        var ct = currentTab();
        if (SESSION.token && (ct === "home" || ct === "report")) (VIEWS[ct])();
        hidePtr();
      });
    }, { passive: true });
  }
  function init() {
    host = $("#app");
    styleStatusBar();
    window.addEventListener("scroll", onScroll, { passive: true });
    wirePtr();
    Promise.all([Store.get("an_lang"), Store.get("an_token"), Store.get("an_cid"), Store.get("an_name"), Store.get("an_me")])
      .then(function (v) {
        if (v[0] && T[v[0]]) LANG = v[0];
        else { var nav = (navigator.language || "en").slice(0, 2); LANG = T[nav] ? nav : "en"; }
        applyLang();
        if (v[4]) { try { SESSION.me = JSON.parse(v[4]); } catch (e) {} }
        setTimeout(hideSplash, 300);
        if (v[1] && v[2]) {
          SESSION.token = v[1]; SESSION.cid = v[2]; SESSION.name = v[3] || "";
          loadOffers(); maybeRegisterPush();
          goTab("home");   // paints from cache, then refreshMe re-renders (or forces login on 401)
        } else {
          mount(viewLogin(false), null);
        }
      });
  }
  var _booted = false;
  function boot() { if (_booted) return; _booted = true; init(); }
  document.addEventListener("DOMContentLoaded", boot);
  if (document.readyState !== "loading") boot();
})();
