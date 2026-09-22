/* i18n runtime — injected by build.py after the window._T data block */
(function(){
  var T = window._T;
  if (!T) return;

  var LANG_CODES = {EN:'en',ES:'es',DE:'de',IT:'it',FR:'fr',PT:'pt-BR'};
  var SUPPORTED = ['EN','ES','DE','IT','FR','PT'];

  /* keep the lang-switcher pill + dropdown checkmark in sync with the applied
     language — the dropdown's own click handler only updates itself when the
     user clicks an option, so a language restored from localStorage or
     auto-detected from navigator.language on load would otherwise leave the
     pill stuck showing "EN" while the page content is already translated. */
  function syncLangUI(lang) {
    var codeEl = document.getElementById('lang-code');
    if (codeEl) codeEl.textContent = lang;
    document.querySelectorAll('.lang-opt').forEach(function(o){
      var isActive = o.getAttribute('data-lang') === lang;
      o.classList.toggle('active', isActive);
      o.setAttribute('aria-selected', isActive ? 'true' : 'false');
      var chk = o.querySelector('.lcheck');
      if (isActive && !chk) {
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 14 10');
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor');
        svg.setAttribute('stroke-width', '2');
        svg.setAttribute('stroke-linecap', 'round');
        svg.setAttribute('stroke-linejoin', 'round');
        svg.setAttribute('class', 'lcheck');
        svg.innerHTML = '<polyline points="1,5 5,9 13,1"/>';
        o.appendChild(svg);
      } else if (!isActive && chk) {
        chk.remove();
      }
    });
  }

  function applyLang(lang) {
    if (SUPPORTED.indexOf(lang) < 0) lang = 'EN';
    var s = T[lang] || T['EN'];
    if (!s) return;

    /* ── text nodes: data-i18n ─────────────────────────────────────────── */
    document.querySelectorAll('[data-i18n]').forEach(function(el){
      var key = el.getAttribute('data-i18n');
      if (!s[key]) return;
      /* Bottom-nav <a> contains an <svg> child — replace only the text node */
      if (el.querySelector('svg,button')) {
        for (var i = el.childNodes.length - 1; i >= 0; i--) {
          var n = el.childNodes[i];
          if (n.nodeType === 3 && n.textContent.trim()) {
            n.textContent = s[key];
            break;
          }
        }
      } else {
        el.textContent = s[key];
      }
    });

    /* ── HTML zones: data-i18n-zone ────────────────────────────────────── */
    /* vids_block skipped — its video buttons have JS listeners bound at load */
    document.querySelectorAll('[data-i18n-zone]').forEach(function(el){
      var key = el.getAttribute('data-i18n-zone');
      if (key === 'vids_block') return;
      if (s[key]) el.innerHTML = s[key];
    });

    /* ── <html lang> attribute ─────────────────────────────────────────── */
    document.documentElement.lang = LANG_CODES[lang] || 'en';

    syncLangUI(lang);
  }

  /* expose so the dropdown handler can call it */
  window._i18n = applyLang;

  /* ── on load: pick language from localStorage > navigator ────────────── */
  var saved = null;
  try { saved = localStorage.getItem('gpen-lang'); } catch(e){}
  var navLang = ((navigator.language || navigator.userLanguage || '').slice(0,2)).toUpperCase();
  /* pt-BR → PT */
  if (!navLang || navLang === 'PT') navLang = 'PT';
  var initLang = (saved && SUPPORTED.indexOf(saved) >= 0) ? saved :
                 (SUPPORTED.indexOf(navLang) >= 0 ? navLang : 'EN');

  if (initLang !== 'EN') applyLang(initLang);

  /* save chosen language to localStorage whenever the dropdown fires _i18n */
  var _orig = window._i18n;
  window._i18n = function(lang){
    _orig(lang);
    try { localStorage.setItem('gpen-lang', lang); } catch(e){}
  };
})();
