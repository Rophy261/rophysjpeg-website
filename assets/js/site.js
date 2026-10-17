/* RophysJpeg — site behaviour: mobile menu, gallery progress indicator,
   accessible lightbox, contact-form state. No dependencies, no tracking. */
(function () {
  "use strict";

  var doc = document;
  var body = doc.body;
  var FOCUSABLE = 'a[href], button:not([disabled]), video[controls], input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function visible(el) { return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length); }

  function trapTab(e, container) {
    if (e.key !== "Tab") return;
    var items = Array.prototype.filter.call(container.querySelectorAll(FOCUSABLE), visible);
    if (!items.length) return;
    var first = items[0], last = items[items.length - 1];
    if (e.shiftKey && doc.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && doc.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  /* ------------------------------------------------------------ mobile menu */
  var header = doc.querySelector("[data-header]");
  var toggle = doc.querySelector("[data-menu-toggle]");
  var panel = doc.querySelector("[data-mobile-menu]");
  var label = doc.querySelector("[data-menu-label]");

  function setMenu(open, restoreFocus) {
    if (!toggle || !panel) return;
    panel.hidden = !open;
    body.classList.toggle("menu-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    if (label) label.textContent = open ? "Close menu" : "Open menu";
    if (open) {
      var first = panel.querySelector("a");
      if (first) first.focus();
    } else if (restoreFocus) {
      toggle.focus();
    }
  }
  if (toggle && panel) {
    toggle.addEventListener("click", function () { setMenu(panel.hidden, false); });
    header.addEventListener("keydown", function (e) {
      if (panel.hidden) return;
      if (e.key === "Escape") { setMenu(false, true); return; }
      trapTab(e, header);
    });
    window.addEventListener("resize", function () {
      if (!panel.hidden && window.innerWidth > 1024) setMenu(false, false);
    });
  }

  /* ------------------------------------------------- gallery progress wiggle */
  var stroke = doc.querySelector(".progress-indicator .stroke");
  if (stroke) {
    var ticking = false;
    var update = function () {
      ticking = false;
      var max = doc.documentElement.scrollHeight - window.innerHeight;
      var p = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
      stroke.style.strokeDashoffset = String(-231 * p);   // full wiggle at top, empties as you scroll
    };
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(update); }
    }, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  /* --------------------------------------------------------------- lightbox */
  var box = doc.querySelector("[data-lightbox]");
  var links = Array.prototype.slice.call(doc.querySelectorAll("[data-gallery] .zoom"));
  if (box && links.length) {
    var bImg = box.querySelector("[data-lightbox-img]");
    var bCount = box.querySelector("[data-lightbox-count]");
    var bClose = box.querySelector("[data-lightbox-close]");
    var bPrev = box.querySelector("[data-lightbox-prev]");
    var bNext = box.querySelector("[data-lightbox-next]");
    var current = 0, opener = null;

    if (links.length < 2) { bPrev.hidden = true; bNext.hidden = true; }

    var preload = function (i) {
      var a = links[(i + links.length) % links.length];
      var im = new Image();
      im.sizes = "100vw";
      im.srcset = a.getAttribute("data-full-srcset");
      im.src = a.href;
    };
    var show = function (i) {
      current = (i + links.length) % links.length;
      var a = links[current];
      var thumb = a.querySelector("img");
      bImg.sizes = "100vw";
      bImg.srcset = a.getAttribute("data-full-srcset");
      bImg.src = a.href;
      bImg.alt = thumb.alt;
      bCount.textContent = (current + 1) + " / " + links.length;
      preload(current + 1); preload(current - 1);
    };
    var open = function (i) {
      opener = doc.activeElement;
      show(i);
      box.hidden = false;
      body.classList.add("lightbox-open");
      bClose.focus();
    };
    var close = function () {
      box.hidden = true;
      body.classList.remove("lightbox-open");
      bImg.removeAttribute("src"); bImg.removeAttribute("srcset");
      if (opener && opener.focus) opener.focus();
    };

    links.forEach(function (a, i) {
      a.addEventListener("click", function (e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return; // allow "open in new tab"
        e.preventDefault();
        open(i);
      });
    });
    bClose.addEventListener("click", close);
    bPrev.addEventListener("click", function () { show(current - 1); });
    bNext.addEventListener("click", function () { show(current + 1); });
    box.addEventListener("click", function (e) { if (e.target === box) close(); });
    box.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.preventDefault(); close(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); show(current + 1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); show(current - 1); }
      else trapTab(e, box);
    });
    var sx = null, sy = null;
    box.addEventListener("touchstart", function (e) {
      if (e.touches.length === 1) { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }
    }, { passive: true });
    box.addEventListener("touchend", function (e) {
      if (sx === null) return;
      var dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) show(current + (dx < 0 ? 1 : -1));
      sx = sy = null;
    });
  }


  /* ------------------------------------------------------------ video page */
  var vmodal = doc.querySelector("[data-vmodal]");
  var vtriggers = Array.prototype.slice.call(doc.querySelectorAll("[data-vindex]"));
  if (vmodal && vtriggers.length) {
    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var canHover = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    var items = [];
    vtriggers.forEach(function (a) {
      var i = +a.getAttribute("data-vindex");
      if (!items[i]) items[i] = a;
    });
    var mVideo = vmodal.querySelector("[data-vmodal-video]");
    var mTitle = vmodal.querySelector("[data-vmodal-title]");
    var mTag = vmodal.querySelector("[data-vmodal-tag]");
    var mCredit = vmodal.querySelector("[data-vmodal-credit]");
    var mClose = vmodal.querySelector("[data-vmodal-close]");
    var mPrev = vmodal.querySelector("[data-vmodal-prev]");
    var mNext = vmodal.querySelector("[data-vmodal-next]");
    var feature = doc.querySelector("[data-autopreview]");
    var vcur = 0, vopener = null;

    var loadItem = function (i) {
      vcur = (i + items.length) % items.length;
      var a = items[vcur];
      var yt = a.getAttribute("data-youtube");
      var mYt = vmodal.querySelector("[data-vmodal-yt]");
      mVideo.pause();
      if (yt && mYt) {
        mVideo.removeAttribute("src"); mVideo.load(); mVideo.hidden = true;
        mYt.hidden = false;
        mYt.title = a.getAttribute("data-title");
        mYt.src = "https://www.youtube-nocookie.com/embed/" + encodeURIComponent(yt) + "?autoplay=1&rel=0&playsinline=1";
      } else {
        if (mYt) { mYt.hidden = true; mYt.removeAttribute("src"); }
        mVideo.hidden = false;
        mVideo.poster = a.getAttribute("data-poster");
        mVideo.src = a.getAttribute("data-src");
        mVideo.setAttribute("aria-label", a.getAttribute("data-title"));
      }
      mTitle.textContent = a.getAttribute("data-title");
      mTag.textContent = a.getAttribute("data-tag") || "";
      mCredit.textContent = a.getAttribute("data-credit") || "";
      var mLink = vmodal.querySelector("[data-vmodal-link]");
      if (mLink) {
        var href = a.getAttribute("data-link");
        if (href) { mLink.href = href; mLink.textContent = (a.getAttribute("data-link-label") || "Watch original") + " \u2197"; mLink.hidden = false; }
        else { mLink.hidden = true; mLink.removeAttribute("href"); }
      }
      if (!yt) {
        var p = mVideo.play();
        if (p && p.catch) p.catch(function () { /* autoplay with sound blocked: controls are visible */ });
      }
    };
    var openV = function (i) {
      vopener = doc.activeElement;
      if (feature) feature.pause();
      vmodal.hidden = false;
      body.classList.add("lightbox-open");
      loadItem(i);
      mClose.focus();
    };
    var closeV = function () {
      var cy = vmodal.querySelector("[data-vmodal-yt]");
      if (cy) { cy.removeAttribute("src"); cy.hidden = true; }
      mVideo.pause();
      mVideo.removeAttribute("src");
      mVideo.load();
      vmodal.hidden = true;
      body.classList.remove("lightbox-open");
      if (feature && !reduceMotion) { var fp = feature.play(); if (fp && fp.catch) fp.catch(function () {}); }
      if (vopener && vopener.focus) vopener.focus();
    };
    vtriggers.forEach(function (a) {
      a.addEventListener("click", function (e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
        e.preventDefault();
        openV(+a.getAttribute("data-vindex"));
      });
    });
    mClose.addEventListener("click", closeV);
    mPrev.addEventListener("click", function () { loadItem(vcur - 1); });
    mNext.addEventListener("click", function () { loadItem(vcur + 1); });
    vmodal.addEventListener("click", function (e) { if (e.target === vmodal) closeV(); });
    vmodal.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.preventDefault(); closeV(); }
      else if (e.key === "ArrowRight" && e.target !== mVideo) { e.preventDefault(); loadItem(vcur + 1); }
      else if (e.key === "ArrowLeft" && e.target !== mVideo) { e.preventDefault(); loadItem(vcur - 1); }
      else trapTab(e, vmodal);
    });

    // featured film: silent looping preview (skipped when the visitor prefers reduced motion)
    if (feature && !reduceMotion) {
      var tryPlay = function () { var fp = feature.play(); if (fp && fp.catch) fp.catch(function () {}); };
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (entries) {
          entries.forEach(function (en) { if (en.isIntersecting) tryPlay(); else feature.pause(); });
        }, { threshold: 0.25 }).observe(feature);
      } else { tryPlay(); }
    }

    // grid cards: silent preview on hover / keyboard focus (desktop pointers only)
    if (canHover && !reduceMotion) {
      Array.prototype.forEach.call(doc.querySelectorAll(".vcard[data-src]"), function (card) {
        var pv = null;
        var start = function () {
          if (!pv) {
            pv = doc.createElement("video");
            pv.muted = true; pv.loop = true; pv.playsInline = true; pv.preload = "auto";
            pv.setAttribute("aria-hidden", "true");
            pv.src = card.getAttribute("data-src");
            card.querySelector(".vthumb").appendChild(pv);
          }
          var pp = pv.play();
          if (pp && pp.then) pp.then(function () { card.classList.add("is-previewing"); }).catch(function () {});
        };
        var stop = function () {
          card.classList.remove("is-previewing");
          if (pv) pv.pause();
        };
        card.addEventListener("mouseenter", start);
        card.addEventListener("mouseleave", stop);
        card.addEventListener("focus", start);
        card.addEventListener("blur", stop);
      });
    }
  }


  /* ---------------------------------------------------- gallery peek (home) */
  if (window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches &&
      !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    Array.prototype.forEach.call(doc.querySelectorAll("[data-peek]"), function (card) {
      var urls = (card.getAttribute("data-peek") || "").split(" ").filter(Boolean);
      if (!urls.length) return;
      var thumb = card.querySelector(".vthumb");
      var layer = null, timer = null, k = 0, loaded = false;
      var next = function () {
        if (!layer) {
          layer = doc.createElement("img");
          layer.className = "vpeek";
          layer.alt = "";
          layer.setAttribute("aria-hidden", "true");
          thumb.insertBefore(layer, thumb.querySelector(".vgal"));
        }
        layer.src = urls[k % urls.length];
        k += 1;
        layer.classList.add("is-on");
      };
      var start = function () {
        if (!loaded) { urls.forEach(function (u) { var im = new Image(); im.src = u; }); loaded = true; }
        clearInterval(timer);
        timer = setTimeout(function () { next(); timer = setInterval(next, 1100); }, 350);
      };
      var stop = function () {
        clearTimeout(timer); clearInterval(timer); timer = null; k = 0;
        if (layer) layer.classList.remove("is-on");
      };
      card.addEventListener("mouseenter", start);
      card.addEventListener("mouseleave", stop);
      card.addEventListener("focus", start);
      card.addEventListener("blur", stop);
    });
  }

  /* ----------------------------------------------------------- contact form */
  var form = doc.querySelector("[data-contact-form]");
  if (form) {
    var cfg = (window.ROPHYSJPEG_CONFIG && window.ROPHYSJPEG_CONFIG.contactForm) || {};
    var submit = form.querySelector("[data-contact-submit]");
    var status = form.querySelector("[data-contact-status]");
    var recipient = form.getAttribute("data-recipient");
    var emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    var useService = !!(cfg.enabled && /^https:\/\/\S+$/.test(cfg.endpoint || "") &&
      (cfg.provider !== "web3forms" || (cfg.accessKey || "").length > 10));
    var setStatus = function (msg, state) {
      status.textContent = msg;
      if (state) status.setAttribute("data-state", state); else status.removeAttribute("data-state");
    };
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (form.elements._gotcha && form.elements._gotcha.value) return; // bot
      var email = form.elements.email, subject = form.elements.subject, message = form.elements.message;
      [email, subject, message].forEach(function (f) { f.removeAttribute("aria-invalid"); });
      var bad = [];
      if (!emailRe.test(email.value.trim())) bad.push(email);
      if (!subject.value.trim()) bad.push(subject);
      if (!message.value.trim()) bad.push(message);
      if (bad.length) {
        bad.forEach(function (f) { f.setAttribute("aria-invalid", "true"); });
        setStatus("Please fill in a valid email address, a subject and a message.", "error");
        bad[0].focus();
        return;
      }
      if (!useService) {
        var body = message.value.trim() + "\n\nReply to: " + email.value.trim();
        window.location.href = "mailto:" + recipient + "?subject=" + encodeURIComponent(subject.value.trim()) +
          "&body=" + encodeURIComponent(body);
        setStatus("Your email app should open with your message ready. Just press send. If nothing opened, email " + recipient + " directly.", "success");
        return;
      }
      if (cfg.provider === "formsubmit") {
        submit.disabled = true;
        setStatus("Sending…", null);
        fetch(cfg.endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ email: email.value.trim(), _replyto: email.value.trim(), _subject: subject.value.trim(),
            subject: subject.value.trim(), message: message.value.trim(), _template: "table" })
        })
          .then(function (res) { return res.json().catch(function () { return {}; }).then(function (json) {
            if (!(res.ok && String(json.success) === "true")) throw new Error(json.message || "delivery failed");
            form.reset();
            setStatus(cfg.successMessage || "Thanks! Your message has been sent. I’ll get back to you soon.", "success");
          }); })
          .catch(function () { setStatus("Your message could not be sent. Please email " + recipient + " directly.", "error"); })
          .then(function () { submit.disabled = false; });
        return;
      }
      var data = new FormData();
      data.append("email", email.value.trim());
      data.append("message", message.value.trim());
      if (cfg.provider === "web3forms") {
        data.append("access_key", cfg.accessKey);
        data.append("subject", subject.value.trim());
        data.append("from_name", "rophysjpeg.com");
        data.append("replyto", email.value.trim());
      } else {
        data.append("_replyto", email.value.trim());
        data.append("_subject", subject.value.trim());
      }
      submit.disabled = true;
      setStatus("Sending…", null);
      fetch(cfg.endpoint, { method: "POST", body: data, headers: { Accept: "application/json" } })
        .then(function (res) {
          return res.json().catch(function () { return {}; }).then(function (json) {
            if (!(res.ok && json.success !== false && !json.errors)) throw new Error("delivery failed");
            form.reset();
            setStatus(cfg.successMessage || "Thanks! Your message has been sent.", "success");
          });
        })
        .catch(function () { setStatus("Your message could not be sent. Please email " + recipient + " directly.", "error"); })
        .then(function () { submit.disabled = false; });
    });
  }
  /* Home: gentle reveal-on-scroll for the featured work, cards and contact strip */
  (function () {
    var home = doc.querySelector(".listing.home");
    if (!home) return;
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var els = home.querySelectorAll(".vfeature, .hsection, .home-work .vgrid > li, .hcontact");
    if (reduce || !("IntersectionObserver" in window)) return;
    Array.prototype.forEach.call(els, function (el) {
      el.classList.add("reveal");
      if (el.matches(".vgrid > li")) {
        var i = Array.prototype.indexOf.call(el.parentNode.children, el);
        el.style.transitionDelay = (i % 3) * 70 + "ms";
      }
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px 10% 0px", threshold: 0 });
    Array.prototype.forEach.call(els, function (el) { io.observe(el); });
  })();
})();
