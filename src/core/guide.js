/* G Pen Core — guide page behavior.
   One copy, shared by every guide page (build.py inlines it before </body>, after the
   i18n runtime, so offline.html keeps working from file://). Every block looks up its
   own elements and quietly does nothing when a page doesn't have them: the Grinder has
   no videos, the index page has no sections or sheet.

   Owns: sticky header state, section scroll-spy (top pills + mobile bottom nav), the
   language menu, the store region (?store=), the product-switcher sheet and the video modal. Dialogs trap focus,
   return it on close, make the rest of the page inert, and share one scroll lock so
   closing one can't unlock the page while the other is still open. */
(function(){
  var d = document;
  function $(id){ return d.getElementById(id); }
  function arr(list){ return Array.prototype.slice.call(list); }

  /* ---------- shared: scroll lock, inert background, focus trap ---------- */
  var locks = 0;
  function lock(){ if (locks++ === 0) d.body.style.overflow = 'hidden'; }
  function unlock(){ if (locks > 0 && --locks === 0) d.body.style.overflow = ''; }

  function setInert(on, keep){
    arr(d.body.children).forEach(function(el){
      if (el.tagName === 'SCRIPT' || keep.indexOf(el) >= 0) return;
      if (on) el.setAttribute('inert', ''); else el.removeAttribute('inert');
    });
  }
  function focusables(root){
    return arr(root.querySelectorAll('a[href], button:not([disabled]), summary, iframe, [tabindex]:not([tabindex="-1"])'))
      .filter(function(el){
        /* skip what can't be seen, e.g. links inside a closed Legacy products fold */
        return el.checkVisibility ? el.checkVisibility() : el.getClientRects().length > 0;
      });
  }
  function trapTab(root, e){
    var f = focusables(root); if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && d.activeElement === first){ e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && d.activeElement === last){ e.preventDefault(); first.focus(); }
  }
  function refocus(el){ if (el && el.focus && d.contains(el)) { try { el.focus({ preventScroll: true }); } catch (x) { el.focus(); } } }

  /* ---------- sticky header ---------- */
  var bar = $('bar');
  if (bar){
    var onScroll = function(){ bar.classList.toggle('stuck', window.scrollY > 12); };
    onScroll(); window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ---------- scroll spy: the bottom nav's own links define the sections ---------- */
  var bottomLinks = arr(d.querySelectorAll('.bottom-nav a[href^="#"]'));
  if (bottomLinks.length){
    var hrefs   = bottomLinks.map(function(a){ return a.getAttribute('href'); });
    var topLinks = hrefs.map(function(h){ return d.querySelector('nav.jump a[href="' + h + '"]'); });
    var targets = hrefs.map(function(h){ return d.querySelector(h); });
    var current = -1, ticking = false, pinned = -1;
    var navH = function(){ return bar ? bar.getBoundingClientRect().height : 52; };

    var setActive = function(i){
      if (i === current) return; current = i;
      [topLinks, bottomLinks].forEach(function(group){
        group.forEach(function(a, j){
          if (!a) return;
          if (j === i) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
        });
      });
    };
    /* The last section whose top has crossed the sticky header wins. More reliable than
       IntersectionObserver when two short sections are on screen at once. At the very
       bottom of the page the last section wins outright: it may be too short to ever reach
       the header. (This replaces an invisible spacer that padded the page so it could,
       which left up to ~450px of empty space under the footer.) */
    var spy = function(){
      ticking = false;
      if (pinned >= 0){ setActive(pinned); return; }
      var active = 0;
      for (var i = 0; i < targets.length; i++){
        if (targets[i] && targets[i].getBoundingClientRect().top <= navH() + 24) active = i;
      }
      var root = d.documentElement;
      if (window.scrollY > 0 && window.innerHeight + window.scrollY >= root.scrollHeight - 2) active = targets.length - 1;
      setActive(active);
    };
    spy();
    var queue = function(){ if (!ticking){ ticking = true; requestAnimationFrame(spy); } };
    window.addEventListener('scroll', queue, { passive: true });
    window.addEventListener('resize', queue);
    /* A tapped nav item is the reader's stated intent: keep it active through the smooth
       scroll it starts (and after, even if its section is too short to reach the header),
       until the reader scrolls on their own again. */
    bottomLinks.concat(topLinks).forEach(function(a){
      if (!a) return;
      a.addEventListener('click', function(e){
        var href = a.getAttribute('href'), i = hrefs.indexOf(href), target = targets[i];
        if (i < 0 || !target) return;
        e.preventDefault();
        pinned = i; setActive(i);
        var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        target.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' });
        try { history.replaceState(history.state, '', href); } catch (x) {}
      });
    });
    ['wheel', 'touchstart', 'keydown'].forEach(function(type){
      window.addEventListener(type, function(){ if (pinned >= 0){ pinned = -1; queue(); } }, { passive: true });
    });
  }

  /* ---------- language menu (a listbox: arrows, Home/End, Enter/Space, Escape) ---------- */
  var langBtn = $('lang-btn'), drop = $('lang-drop');
  var closeDrop = function(){};
  if (langBtn && drop){
    var opts = arr(drop.querySelectorAll('.lang-opt'));
    opts.forEach(function(o){ o.tabIndex = -1; });
    var activeOpt = function(){ return drop.querySelector('.lang-opt.active') || opts[0]; };
    var openDrop = function(focusList){
      drop.hidden = false; langBtn.setAttribute('aria-expanded', 'true');
      if (focusList) activeOpt().focus();
    };
    closeDrop = function(returnFocus){
      if (drop.hidden) return;
      drop.hidden = true; langBtn.setAttribute('aria-expanded', 'false');
      if (returnFocus) langBtn.focus();
    };
    var choose = function(o){
      if (window._i18n) window._i18n(o.getAttribute('data-lang'));
      closeDrop(true);
    };
    langBtn.addEventListener('click', function(e){
      e.stopPropagation();
      /* detail 0 = activated from the keyboard: move focus into the list */
      if (drop.hidden) openDrop(e.detail === 0); else closeDrop(false);
    });
    langBtn.addEventListener('keydown', function(e){
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp'){ e.preventDefault(); openDrop(true); }
    });
    drop.addEventListener('click', function(e){
      var o = e.target.closest('.lang-opt'); if (!o) return;
      e.stopPropagation(); choose(o);
    });
    drop.addEventListener('keydown', function(e){
      var i = opts.indexOf(d.activeElement), n = opts.length;
      if (e.key === 'ArrowDown'){ e.preventDefault(); opts[(i + 1) % n].focus(); }
      else if (e.key === 'ArrowUp'){ e.preventDefault(); opts[(i - 1 + n) % n].focus(); }
      else if (e.key === 'Home'){ e.preventDefault(); opts[0].focus(); }
      else if (e.key === 'End'){ e.preventDefault(); opts[n - 1].focus(); }
      else if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); if (i >= 0) choose(opts[i]); }
      else if (e.key === 'Tab'){ closeDrop(false); }
    });
    var outside = function(e){ if (!drop.hidden && !drop.contains(e.target) && !langBtn.contains(e.target)) closeDrop(false); };
    d.addEventListener('click', outside);
    d.addEventListener('pointerdown', outside);   /* iOS: taps on plain text fire no click */
  }

  /* ---------- product switcher sheet ---------- */
  var guidesBtn = $('guides-btn'), sheet = $('product-sheet');
  var sheetBackdrop = $('sheet-backdrop'), sheetClose = $('sheet-close');
  var sheetOpen = false, closeSheet = function(){};
  if (guidesBtn && sheet && sheetBackdrop){
    var hideTimer = 0, sheetReturn = null, openedAt = 0;
    var openSheet = function(){
      if (sheetOpen) return;
      sheetOpen = true; clearTimeout(hideTimer); openedAt = Date.now();
      sheetReturn = d.activeElement;
      sheet.hidden = false; sheetBackdrop.hidden = false;
      sheet.getBoundingClientRect();            /* commit the closed position so it animates */
      sheet.classList.add('open'); sheetBackdrop.classList.add('open');
      guidesBtn.setAttribute('aria-expanded', 'true');
      lock(); setInert(true, [sheet, sheetBackdrop]);
      /* the current product's card is often below the fold of the sheet */
      var cur = sheet.querySelector('[aria-current="true"]');
      var body = sheet.querySelector('.sheet-body');
      if (cur && body){
        var off = cur.getBoundingClientRect().top - body.getBoundingClientRect().top + body.scrollTop;
        body.scrollTop = Math.max(0, off - (body.clientHeight - cur.offsetHeight) / 2);
      }
      refocus(sheetClose || sheet);
    };
    closeSheet = function(){
      if (!sheetOpen) return;
      sheetOpen = false;
      sheet.classList.remove('open'); sheetBackdrop.classList.remove('open');
      guidesBtn.setAttribute('aria-expanded', 'false');
      setInert(false, []); unlock();
      hideTimer = setTimeout(function(){ sheet.hidden = true; sheetBackdrop.hidden = true; }, 320);
      refocus(sheetReturn || guidesBtn);
    };
    guidesBtn.addEventListener('click', openSheet);
    if (sheetClose) sheetClose.addEventListener('click', closeSheet);
    /* a quick double tap on "All guides" lands its second tap on the backdrop that just
       appeared under the finger: don't let that close the sheet again */
    sheetBackdrop.addEventListener('click', function(){ if (Date.now() - openedAt > 400) closeSheet(); });

    /* Swipe down to close — only when the list is scrolled to its top, so scrolling the
       product list back up doesn't dismiss the sheet. */
    var sheetBody = sheet.querySelector('.sheet-body') || sheet;
    var startY = 0, startTop = 0;
    var fromHead = false;
    sheet.addEventListener('touchstart', function(e){
      startY = e.touches[0].clientY; startTop = sheetBody.scrollTop;
      /* a swipe that starts on the handle or the title bar closes it wherever the list is scrolled */
      fromHead = !sheetBody.contains(e.target);
    }, { passive: true });
    sheet.addEventListener('touchend', function(e){
      if (e.changedTouches[0].clientY - startY > 60 && (fromHead || startTop <= 0)) closeSheet();
    }, { passive: true });
  }

  /* ---------- video modal (Vimeo) ---------- */
  var vm = $('vm'), vmBackdrop = $('vm-backdrop'), vmFrame = $('vm-iframe'), vmClose = $('vm-close');
  var vmOpen = false, closeVideo = function(){};
  if (vm && vmFrame && vmBackdrop){
    var vmReturn = null;
    var openVideo = function(card){
      var id = card.getAttribute('data-vimeo'); if (!id) return;
      var hash = card.getAttribute('data-vimeo-hash');
      vmFrame.src = 'https://player.vimeo.com/video/' + encodeURIComponent(id) +
                    '?autoplay=1&dnt=1' + (hash ? '&h=' + encodeURIComponent(hash) : '');
      var title = card.querySelector('.vid-title');
      vmFrame.title = title ? title.textContent.trim() : 'Video';
      vmReturn = card;
      vmBackdrop.hidden = false; vm.hidden = false; vmOpen = true;
      lock(); setInert(true, [vm, vmBackdrop]);
      refocus(vmClose || vm);
    };
    closeVideo = function(){
      if (!vmOpen) return;
      vmOpen = false;
      vmFrame.src = 'about:blank';   /* stops playback */
      vmBackdrop.hidden = true; vm.hidden = true;
      setInert(false, []); unlock();
      refocus(vmReturn);
    };
    /* Delegated, so it survives a language switch re-rendering the video cards. */
    d.addEventListener('click', function(e){
      var card = e.target.closest && e.target.closest('.vid[data-vimeo]');
      if (card){ e.preventDefault(); openVideo(card); }
    });
    if (vmClose) vmClose.addEventListener('click', closeVideo);
    vmBackdrop.addEventListener('click', closeVideo);
    vm.addEventListener('click', function(e){ if (e.target === vm) closeVideo(); });
  }

  /* ---------- store region: which G Pen store the store links go to ---------- */
  /* The static pages link to the US store. A visitor sent from another store's site
     (ca.gpen.com links here with ?store=ca) gets that store instead, same rule as ?lang=:
     ?store= > saved choice > US, and a ?store= link sticks for the next guides they open.
     To add a store: one entry here. base replaces https://www.gpen.com on every store
     link; register replaces /pages/register; langPrefix puts a language folder in front
     of the path (Canada's French pages live under /fr). */
  var STORES = {
    us: { base: 'https://www.gpen.com', register: '/pages/register' },
    ca: { base: 'https://ca.gpen.com', register: '/register/', langPrefix: { fr: '/fr' } }
  };
  var STORE_LINK = /^https?:\/\/(?:www\.)?gpen\.com(?=[\/?#]|$)/i;
  var REGISTER = /^\/pages\/register\/?(?=[?#]|$)/;
  var store = 'us';
  try {
    var qStore = ((location.search.match(/[?&]store=([a-z]{2})\b/i) || [])[1] || '').toLowerCase();
    if (STORES[qStore]){ store = qStore; localStorage.setItem('gpen-store', store); }
    else { var saved = localStorage.getItem('gpen-store'); if (STORES[saved]) store = saved; }
  } catch (x) {}
  function applyStore(){
    /* the Upgrades prices are the US store's: other stores' differ, so they're hidden there */
    d.documentElement.setAttribute('data-store', store);
    if (store === 'us' && !d.querySelector('a[data-us-href]')) return;
    var cfg = STORES[store];
    var prefix = (cfg.langPrefix || {})[(d.documentElement.lang || 'en').slice(0, 2).toLowerCase()] || '';
    arr(d.querySelectorAll('a[href]')).forEach(function(a){
      /* the US address is the source of truth: a language switch re-renders some links */
      var us = a.getAttribute('data-us-href') || a.getAttribute('href');
      if (!STORE_LINK.test(us)) return;
      a.setAttribute('data-us-href', us);
      var path = us.replace(STORE_LINK, '') || '/';
      if (REGISTER.test(path)) path = path.replace(REGISTER, cfg.register);
      a.setAttribute('href', cfg.base + prefix + path);
    });
  }
  applyStore();
  /* a language change re-renders translated blocks and can move a Canadian visitor to the
     French store pages, so the links are worked out again after it */
  var langChange = window._i18n;
  if (langChange) window._i18n = function(lang){ langChange(lang); applyStore(); };

  /* ---------- deep links: /micro-ii/#faq-2 opens that answer, #help the question list ----------
     Support sends links like these; a target inside a closed <details> would land on a
     collapsed accordion, so every <details> around it opens first, then it scrolls into view. */
  function openTarget(){
    var id = decodeURIComponent(location.hash.slice(1));
    var el = id && d.getElementById(id);
    if (!el) return;
    var opened = false;
    if (id === 'help'){ var faq = el.querySelector('details.collapsible'); if (faq && !faq.open){ faq.open = true; opened = true; } }
    for (var p = el; p; p = p.parentElement){
      if (p.tagName === 'DETAILS' && !p.open){ p.open = true; opened = true; }
    }
    if (opened) el.scrollIntoView({ block: 'start' });
  }
  openTarget();
  window.addEventListener('hashchange', openTarget);

  /* ---------- back/forward cache: restore the page with nothing left open ---------- */
  window.addEventListener('pageshow', function(e){
    if (!e.persisted) return;
    closeDrop(false); closeVideo(); closeSheet();
  });

  /* ---------- one keyboard handler, innermost layer first ---------- */
  d.addEventListener('keydown', function(e){
    if (e.key === 'Escape'){
      if (drop && !drop.hidden){ e.preventDefault(); closeDrop(true); return; }
      if (vmOpen){ e.preventDefault(); closeVideo(); return; }
      if (sheetOpen){ e.preventDefault(); closeSheet(); return; }
    } else if (e.key === 'Tab'){
      if (vmOpen) trapTab(vm, e);
      else if (sheetOpen) trapTab(sheet, e);
    }
  });
})();
