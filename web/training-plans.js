(function() {
  // ---- GA4 Analytics Helper ----
  function track(event, params) {
    if (typeof gtag === 'function') {
      gtag('event', event, params || {});
    } else if (window.dataLayer) {
      var obj = { event: event };
      if (params) { for (var k in params) obj[k] = params[k]; }
      window.dataLayer.push(obj);
    }
  }

  track('tp_page_view', { page: 'landing' });

  // ---- Scroll Reveal System (IntersectionObserver) ----
  if ('IntersectionObserver' in window) {
    var revealGroups = [
      ['.tp-pullquote'],
      ['.tp-sample-week'],
      ['.tp-process'],
      ['.tp-pricing-card'],
      ['.tp-deliverables', '.tp-deliverable-row'],
      ['.tp-steps', '.tp-step'],
      ['.tp-faq-list', '.tp-faq-item'],
      ['.tp-audience-grid', '.tp-audience-col']
    ];

    var revealObs = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (!entry.isIntersecting) return;
        var targets = entry.target.querySelectorAll('.tp-animate');
        if (targets.length === 0) {
          entry.target.classList.add('is-visible');
        } else {
          targets.forEach(function(t) { t.classList.add('is-visible'); });
        }
        revealObs.unobserve(entry.target);
      });
    }, { threshold: 0.1 });

    revealGroups.forEach(function(group) {
      var el = document.querySelector(group[0]);
      if (!el) return;
      if (group[1]) {
        el.querySelectorAll(group[1]).forEach(function(child, i) {
          child.classList.add('tp-animate');
          child.style.transitionDelay = (i * 0.08) + 's';
        });
        revealObs.observe(el);
      } else {
        el.classList.add('tp-animate');
        revealObs.observe(el);
      }
    });
  }

  // ---- Scroll Depth Tracking ----
  (function() {
    var depths = {};
    var tick = null;
    window.addEventListener('scroll', function() {
      if (tick) return;
      tick = requestAnimationFrame(function() {
        tick = null;
        var scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        var docHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        if (docHeight <= 0) return;
        var pct = Math.round((scrollTop / docHeight) * 100);
        [25, 50, 75, 100].forEach(function(d) {
          if (pct >= d && !depths[d]) {
            depths[d] = true;
            track('tp_scroll_depth', { depth: d, page: 'landing' });
          }
        });
      });
    });
  })();

  // ---- CTA Click Attribution ----
  document.querySelectorAll('.tp-btn, .tp-sticky-cta a').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var loc = 'unknown';
      if (this.closest('.tp-hero-cta') || this.closest('.tp-hero')) loc = 'hero';
      else if (this.closest('.tp-pricing-cta')) loc = 'pricing';
      else if (this.closest('.tp-sticky-cta')) loc = 'sticky_mobile';
      track('tp_cta_click', { location: loc, text: this.textContent.trim().substring(0, 40) });
    });
  });

  // ---- FAQ Accordion ----
  document.querySelectorAll('.tp-faq-q').forEach(function(q) {
    q.addEventListener('click', function() {
      var item = this.parentElement;
      var wasOpen = item.classList.contains('open');
      document.querySelectorAll('.tp-faq-item').forEach(function(i) {
        i.classList.remove('open');
      });
      if (!wasOpen) {
        item.classList.add('open');
        var qText = this.childNodes[0] ? this.childNodes[0].textContent.trim() : '';
        track('tp_faq_open', { question: qText.substring(0, 60) });
      }
    });
  });

  // ---- Smooth scroll for #how-it-works ----
  var howLink = document.querySelector('.tp-landing a[href="#how-it-works"]');
  if (howLink) {
    howLink.addEventListener('click', function(e) {
      e.preventDefault();
      var target = document.querySelector('#how-it-works');
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  // ---- Rotating Reality Checks (slide transition) ----
  var realityChecks = [
    "You downloaded a 12-week plan from the internet. It assumed you had 15 hours a week and zero injuries. How'd that go?",
    "Your buddy's training plan worked great. For your buddy. You're not your buddy.",
    "A 50-year-old with 5 hours needs fundamentally different training than a 28-year-old with 15. Different hours demand different science.",
    "You know what a generic plan does at mile 80 of Unbound? Nothing. Because it doesn't know you're at Unbound.",
    "Every training plan is a bet. Most plans are betting you're a 25-year-old with unlimited time and perfect recovery. Are you?",
    "The plan said 'tempo ride, 2 hours.' You had 45 minutes before school pickup. So you skipped it. Then you skipped Tuesday too.",
    "Your FTP is 230. Your plan was written for someone with an FTP of 300. You've been training in the wrong zones for 8 weeks.",
    "You have a smart trainer collecting dust. You have a race in 16 weeks. You have no plan. You have excuses. Pick one to fix.",
    "Nutrition plan: 'eat 60g carbs per hour.' At what elevation? In what heat? For what distance? Details matter. Vague advice kills races.",
    "Your strength training is whatever YouTube recommended this week. Your left hip flexor has an opinion about that.",
    "Rest days aren't lazy. They're where adaptation happens. Your plan should know which ones are strategic and which ones are panic.",
    "You're training for a 100-mile gravel race with a plan designed for 40km road crits. The specificity isn't there.",
    "Three hours a week can build you for a gravel century. But not with a plan that wastes two of them on junk miles.",
    "You told your last plan about your bad knee. It gave you plyometrics in week 3.",
    "Heat kills more gravel races than fitness. If your plan doesn't have an acclimatization protocol, it's not a plan. It's a wish.",
    "You tapered for 3 weeks because 'that's what the article said.' You lost fitness. Race day felt flat. Taper length is individual.",
    "Your race starts at 7,000 feet. Your plan was written at sea level. That's a different sport and nobody told you.",
    "Training without power zones is like cooking without measurements. You can do it. It's just worse.",
    "You finished your last race. You also bonked at mile 60, walked two climbs, and questioned your life choices. 'Finished' is a low bar.",
    "Somewhere right now, someone is doing their third 'base phase' of the year because they keep restarting the same generic plan.",
    "Your plan says 'G-Spot, 2 hours.' At what cadence? In what position? After how much fatigue? Those dimensions change the workout entirely. Most plans don't even know they exist.",
    "Mile 80 of your race, you'll be grinding at 55rpm in the drops on tired legs. Your training plan should have prepared you for that exact scenario. Did it?"
  ];

  var quoteEl = document.getElementById('tp-quote-text');
  if (quoteEl) {
    for (var qi = realityChecks.length - 1; qi > 0; qi--) {
      var qj = Math.floor(Math.random() * (qi + 1));
      var tmp = realityChecks[qi]; realityChecks[qi] = realityChecks[qj]; realityChecks[qj] = tmp;
    }
    var quoteIndex = 0;
    quoteEl.textContent = realityChecks[0];

    setInterval(function() {
      quoteEl.style.opacity = '0';
      quoteEl.style.transform = 'translateY(-10px)';
      setTimeout(function() {
        quoteIndex = (quoteIndex + 1) % realityChecks.length;
        quoteEl.textContent = realityChecks[quoteIndex];
        quoteEl.style.transform = 'translateY(10px)';
        void quoteEl.offsetHeight;
        quoteEl.style.opacity = '1';
        quoteEl.style.transform = 'translateY(0)';
      }, 450);
    }, 8000);
  }

  // ---- Sample Week Clickable Blocks ----
  var sampleDetail = document.getElementById('tp-sample-detail');

  var zoneColors = {
    z1: '#e8e8e8', z2: '#F5E5D3', z3: '#c9b8a3',
    z4: '#59473C', z5: '#222', z6: '#000'
  };

  function buildWorkoutViz(structureJSON, meta) {
    var blocks = JSON.parse(structureJSON);
    var vizHTML = '<div class="tp-workout-viz">';
    blocks.forEach(function(b) {
      var heightPx = Math.round(b.h * 0.95);
      var bg = zoneColors[b.z] || '#ccc';
      var border = b.z === 'z2' ? '#59473C' : '#000';
      vizHTML += '<div class="tp-viz-block tp-viz-' + b.z + '" style="flex-basis:' + b.w + '%;height:' + heightPx + 'px;background:' + bg + ';border:2px solid ' + border + ';">';
      if (b.l) vizHTML += '<span class="tp-viz-label">' + b.l + '</span>';
      vizHTML += '</div>';
    });
    vizHTML += '</div>';
    if (meta) {
      var parts = meta.split(' | ');
      vizHTML += '<div class="tp-viz-meta">';
      parts.forEach(function(p) { vizHTML += '<span>' + p + '</span>'; });
      vizHTML += '</div>';
    }
    return vizHTML;
  }

  document.querySelectorAll('.tp-sample-block[data-detail]').forEach(function(block) {
    block.addEventListener('click', function() {
      var wasActive = this.classList.contains('active');
      document.querySelectorAll('.tp-sample-block').forEach(function(b) {
        b.classList.remove('active');
      });
      if (wasActive) {
        sampleDetail.style.display = 'none';
      } else {
        this.classList.add('active');
        var html = '';
        if (this.dataset.structure) {
          html += buildWorkoutViz(this.dataset.structure, this.dataset.meta || '');
        }
        html += '<div>' + this.dataset.detail + '</div>';
        sampleDetail.innerHTML = html;
        sampleDetail.style.display = 'block';
        track('tp_sample_week_click', {
          workout: this.textContent.trim().replace(/\s+/g, ' ').substring(0, 30)
        });
      }
    });
  });
})();
