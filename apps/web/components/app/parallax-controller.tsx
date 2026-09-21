"use client";

import { useEffect } from "react";

/**
 * Small, page-agnostic scroll-motion controller for the landing page.
 *
 * Rather than duplicating scroll listeners/observers across every
 * decorative element, sections opt in declaratively via data attributes
 * on plain (server-rendered) elements:
 *
 *   data-parallax-speed="0.08"        translateY(-signal * speed), rAF + passive
 *   data-parallax-x="0.05"            optional translateX(signal * speed) — same
 *                                      scroll signal, horizontal axis; used where
 *                                      motion should read as "moving toward" a
 *                                      fixed point (e.g. resume/job panels
 *                                      converging on NERO) rather than depth
 *   data-parallax-scale-to="1.04"     optional scroll-linked scale, 1 -> value
 *   data-parallax-local               opt-in: "signal" above becomes this
 *                                      element's own scroll-into-view progress
 *                                      (bounded to roughly its transit through
 *                                      the viewport) instead of raw page
 *                                      window.scrollY. Required for anything
 *                                      outside the hero — on a long page, a
 *                                      speed multiplied by a global scrollY
 *                                      that can reach into the tens of
 *                                      thousands produces an offset large
 *                                      enough to push the element off-screen
 *                                      entirely, not a subtle drift.
 *   data-parallax-desktop-only        opt-in: transform skipped below 1024px,
 *                                      for motion whose meaning is tied to the
 *                                      desktop composition.
 *   data-scroll-progress              opt-in: writes this element's own 0->1
 *                                      transit progress to the CSS custom
 *                                      property --scene-progress, for
 *                                      scene-specific CSS to consume.
 *                                      Convention: 0% entering -> 50% primary
 *                                      interaction -> 100% exiting.
 *   data-scroll-progress-page         opt-in, at most a handful of elements:
 *                                      receives the page-level 0->1 scroll
 *                                      progress over the first viewport
 *                                      height as --scroll-progress-page.
 *   data-reveal                       fade/rise-in once the element enters view
 *   data-reveal-delay="120"           optional stagger, ms
 *
 * Renders nothing — it only wires up effects against elements already in
 * the DOM. All continuous scroll work happens via direct style writes
 * inside a single rAF loop (no React state, no per-frame re-renders).
 *
 * ---------------------------------------------------------------------
 * PERFORMANCE MODEL (rewritten after profiling — see notes inline)
 *
 * Native scroll is never hijacked. No wheel/touch handler, nothing
 * calls preventDefault, there is no virtual scroller and no custom
 * scroll physics. The browser owns the scroll position; this file only
 * reads it and moves decorative layers.
 *
 * Three rules keep that cheap, each of them the direct result of a
 * measurement rather than a guess:
 *
 * 1. NEVER write a custom property on document.documentElement during
 *    scroll. Setting *any* custom property on :root invalidates the
 *    inherited custom-property map for the whole document, forcing a
 *    full-tree style recalculation. Measured on this page: 59-133ms per
 *    write — per frame — which on its own accounted for ~28s of
 *    UpdateLayoutTree in a 42s scroll trace and pushed wheel-to-scroll
 *    latency to ~290ms. Page-level progress is now written onto the one
 *    element that consumes it (see data-scroll-progress-page), scoping
 *    the invalidation to that element's subtree. Cost measured after:
 *    ~0.5ms.
 *
 * 2. Only touch elements that are near the viewport. An
 *    IntersectionObserver with a generous margin maintains the active
 *    set; everything else is skipped entirely — no rect read, no style
 *    write, no compositor layer. On this page that is typically ~8-12
 *    of 55 elements instead of all 55.
 *
 * 3. will-change is applied only while an element is actually in that
 *    active set. A blanket `will-change: transform` on every parallax
 *    element permanently promoted 52 layers, including ones thousands
 *    of pixels off-screen.
 *
 * Reads are still batched ahead of writes within a frame so a rect read
 * never follows a style write (forced reflow), and every write is
 * skipped when the value it would set is unchanged.
 *
 * MOTION MODEL. Scroll-derived values are followed with a single tight
 * ease (EASE below). The previous velocity-adaptive lerp bottomed out
 * at 0.14, i.e. ~15 frames — a quarter of a second — for a layer to
 * reach its scroll-derived position. That trailing is what made the
 * page feel like it was being scrolled *for* the user rather than by
 * them. At 0.85 the residual is ~1% after two frames: still softens the
 * coarse steps of a wheel tick, but arrives within the same visual beat
 * as the content it sits behind.
 */

// Followed, not snapped, so a 100px wheel tick doesn't step the
// decorative layers in one jump — but tight enough that the layer is
// visually there within ~2 frames.
const EASE = 0.85;

// In normalized (0..1 progress) units. Once every tracked value is this
// close to its target the loop stops; onScroll restarts it.
const SETTLE_EPSILON = 0.0015;

// How far outside the viewport an element still counts as "animating".
// Generous enough that nothing is ever seen snapping into position as
// it enters, small enough that most of a 12,000px page stays idle.
const ACTIVE_MARGIN_DESKTOP = "75% 0px 75% 0px";
const ACTIVE_MARGIN_MOBILE = "35% 0px 35% 0px";

/**
 * Purely decorative CSS loops that should not run while off screen.
 *
 * These are `infinite` keyframe animations, so without this they keep
 * the compositor producing frames for the whole session regardless of
 * scroll position — eight floating NERO figures, two dash-flow loops,
 * the scroll chevron and the two ring pulses. Each is decorative only:
 * pausing one off screen is unobservable, and it resumes mid-cycle
 * when it comes back, so nothing ever restarts visibly.
 *
 * Content-bearing motion is deliberately absent from this list; only
 * ambient loops belong here.
 */
const ANIMATED_SELECTOR =
  ".nero-float, .scroll-dot, .job-intel-streams-animated," +
  " .finale-road-animated, .system-hub-pulse, .job-intel-clarity-pulse";

// Wider than the parallax margin: an ambient loop only has to be
// running by the time it is actually visible.
const ANIM_MARGIN = "25% 0px 25% 0px";

export default function ParallaxController() {
  useEffect(() => {
    const reduceMotionQuery = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    );

    const revealEls = Array.from(
      document.querySelectorAll<HTMLElement>("[data-reveal]"),
    );
    let revealObserver: IntersectionObserver | null = null;

    const setupReveal = () => {
      if (reduceMotionQuery.matches) {
        revealEls.forEach((el) => el.classList.add("is-revealed"));
        return;
      }

      revealObserver = new IntersectionObserver(
        (entries, observer) => {
          for (const entry of entries) {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-revealed");
              observer.unobserve(entry.target);
            }
          }
        },
        { threshold: 0.2, rootMargin: "0px 0px -10% 0px" },
      );

      revealEls.forEach((el) => {
        const delay = el.dataset.revealDelay;
        if (delay) el.style.setProperty("--reveal-delay", `${delay}ms`);
        revealObserver?.observe(el);
      });
    };

    setupReveal();

    const clamp01 = (value: number) => Math.min(Math.max(value, 0), 1);

    type Entry = {
      el: HTMLElement;
      speed: number;
      speedX: number;
      scaleTo: number | null;
      local: boolean;
      desktopOnly: boolean;
      writeProgressVar: boolean;
      renderedProgress: number;
      active: boolean;
      lastTransform: string;
      lastProgressVar: string;
    };

    const computeLocalProgress = (el: HTMLElement, viewportH: number) => {
      const rect = el.getBoundingClientRect();
      // 0 as the element's bottom reaches the viewport's bottom edge
      // (about to enter), 1 as its top passes the viewport's top edge
      // (about to leave) — monotonic across the transit, independent of
      // how far down the page the element sits.
      return clamp01((viewportH - rect.top) / (viewportH + rect.height));
    };

    const parallaxEls: Entry[] = Array.from(
      document.querySelectorAll<HTMLElement>(
        "[data-parallax-speed], [data-parallax-x], [data-scroll-progress]",
      ),
    ).map((el) => {
      const local =
        el.dataset.parallaxLocal !== undefined ||
        (el.dataset.parallaxSpeed === undefined &&
          el.dataset.parallaxX === undefined);
      return {
        el,
        speed: parseFloat(el.dataset.parallaxSpeed ?? "0") || 0,
        speedX: parseFloat(el.dataset.parallaxX ?? "0") || 0,
        scaleTo: el.dataset.parallaxScaleTo
          ? parseFloat(el.dataset.parallaxScaleTo)
          : null,
        local,
        desktopOnly: el.dataset.parallaxDesktopOnly !== undefined,
        writeProgressVar: el.dataset.scrollProgress !== undefined,
        // Seeded on activation from the real target, so an element's
        // first painted frame already matches its scroll position
        // instead of easing in from zero.
        renderedProgress: local ? computeLocalProgress(el, window.innerHeight) : 0,
        active: false,
        lastTransform: "",
        lastProgressVar: "",
      };
    });

    // The page-level progress consumer(s). Previously this value went
    // onto :root, which is what made scrolling expensive; it now goes
    // only where it is read.
    const pageProgressEls = Array.from(
      document.querySelectorAll<HTMLElement>("[data-scroll-progress-page]"),
    );
    let lastPageProgress = "";

    let viewportH = window.innerHeight;
    let viewportW = window.innerWidth;
    let mobileFactor = viewportW < 768 ? 0.45 : 1;
    let isDesktop = viewportW >= 1024;
    let isMobile = viewportW < 768;

    // --- active set -------------------------------------------------
    // Everything outside this set is skipped completely each frame.
    const entryByEl = new Map<Element, Entry>();
    parallaxEls.forEach((entry) => entryByEl.set(entry.el, entry));

    const deactivate = (entry: Entry) => {
      if (!entry.active) return;
      entry.active = false;
      // Leave the element where it is visually (it is off-screen), but
      // drop the compositor layer so an off-screen decorative div isn't
      // holding GPU memory for the rest of the session.
      entry.el.style.willChange = "";
    };

    const activate = (entry: Entry) => {
      if (entry.active) return;
      entry.active = true;
      if (entry.speed || entry.speedX || entry.scaleTo) {
        entry.el.style.willChange = "transform";
      }
      // Re-seed so it enters at the right offset rather than easing in
      // from wherever it was left when it went inactive.
      if (entry.local) {
        entry.renderedProgress = computeLocalProgress(entry.el, viewportH);
      }
    };

    const activeObserver = new IntersectionObserver(
      (entries) => {
        for (const record of entries) {
          const entry = entryByEl.get(record.target);
          if (!entry) continue;
          if (record.isIntersecting) activate(entry);
          else deactivate(entry);
        }
        // Newly-activated elements need a frame to be positioned.
        requestTick();
      },
      { rootMargin: isMobile ? ACTIVE_MARGIN_MOBILE : ACTIVE_MARGIN_DESKTOP },
    );

    // --- ambient animation gating ------------------------------------
    // Independent of the parallax loop: it only toggles a class, and
    // only when an element crosses the boundary, so it costs nothing
    // per frame.
    const animatedEls = Array.from(
      document.querySelectorAll<HTMLElement>(ANIMATED_SELECTOR),
    );
    animatedEls.forEach((el) => el.classList.add("is-offscreen"));

    const animObserver = new IntersectionObserver(
      (records) => {
        for (const record of records) {
          record.target.classList.toggle("is-offscreen", !record.isIntersecting);
        }
      },
      { rootMargin: ANIM_MARGIN },
    );

    const startAnimGating = () => animatedEls.forEach((el) => animObserver.observe(el));
    const stopAnimGating = () => {
      animObserver.disconnect();
      animatedEls.forEach((el) => el.classList.remove("is-offscreen"));
    };

    let rafId: number | null = null;
    let running = false;
    let renderedGlobalScrollY = window.scrollY;
    let pageScrollRange = window.innerHeight;

    const frame = () => {
      rafId = null;
      const rawScrollY = window.scrollY;

      // ---- READ PASS -------------------------------------------------
      // Every getBoundingClientRect happens before any style write, so a
      // read never has to flush a write from earlier in this same frame.
      // Only active (near-viewport) entries are read at all.
      const reads: { entry: Entry; targetProgress: number }[] = [];
      for (const entry of parallaxEls) {
        if (!entry.active) continue;
        reads.push({
          entry,
          targetProgress: entry.local
            ? computeLocalProgress(entry.el, viewportH)
            : 0,
        });
      }

      // ---- WRITE PASS ------------------------------------------------
      renderedGlobalScrollY += (rawScrollY - renderedGlobalScrollY) * EASE;
      const globalProgress = clamp01(renderedGlobalScrollY / pageScrollRange);

      let maxDelta = Math.abs(rawScrollY - renderedGlobalScrollY) / pageScrollRange;

      for (const { entry, targetProgress } of reads) {
        const { el, speed, speedX, scaleTo, local, desktopOnly, writeProgressVar } =
          entry;

        if (local) {
          entry.renderedProgress +=
            (targetProgress - entry.renderedProgress) * EASE;
          maxDelta = Math.max(
            maxDelta,
            Math.abs(targetProgress - entry.renderedProgress),
          );
        }

        if (writeProgressVar) {
          const progress = local ? entry.renderedProgress : globalProgress;
          const next = progress.toFixed(3);
          // Skipping the no-op write matters: each one invalidates this
          // element's subtree style.
          if (next !== entry.lastProgressVar) {
            entry.lastProgressVar = next;
            el.style.setProperty("--scene-progress", next);
          }
        }

        if (!speed && !speedX && !scaleTo) continue;

        if (desktopOnly && !isDesktop) {
          if (entry.lastTransform !== "") {
            entry.lastTransform = "";
            el.style.transform = "";
          }
          continue;
        }

        const signal = local
          ? (entry.renderedProgress - 0.5) * viewportH
          : renderedGlobalScrollY;

        const translateY = -signal * speed * mobileFactor;
        const translateX = signal * speedX * mobileFactor;
        let transform = `translate3d(${translateX.toFixed(1)}px, ${translateY.toFixed(1)}px, 0)`;
        // Scale re-rasterizes the layer, which is the single most
        // expensive thing a decorative layer can do on a phone GPU. The
        // translate-only depth cue is kept; the zoom is desktop-only.
        if (scaleTo && !isMobile) {
          const scaleProgress = local ? entry.renderedProgress : globalProgress;
          const scale = 1 + (scaleTo - 1) * scaleProgress;
          transform += ` scale(${scale.toFixed(3)})`;
        }
        if (transform !== entry.lastTransform) {
          entry.lastTransform = transform;
          el.style.transform = transform;
        }
      }

      // Page-level progress, written only onto its declared consumers.
      if (pageProgressEls.length) {
        const next = globalProgress.toFixed(3);
        if (next !== lastPageProgress) {
          lastPageProgress = next;
          for (const el of pageProgressEls) {
            el.style.setProperty("--scroll-progress-page", next);
          }
        }
      }

      if (maxDelta > SETTLE_EPSILON) {
        rafId = window.requestAnimationFrame(frame);
      }
      // Otherwise: settled. Stop ticking; onScroll restarts the loop.
    };

    const requestTick = () => {
      if (rafId === null && running) rafId = window.requestAnimationFrame(frame);
    };

    // Passive: this never blocks or cancels the browser's own scrolling.
    const onScroll = () => requestTick();

    let resizeTimer: number | null = null;
    const onResize = () => {
      // Debounced — a resize invalidates every cached rect, and doing
      // that work on every intermediate pixel of a window drag is pure
      // waste.
      if (resizeTimer !== null) window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        viewportH = window.innerHeight;
        viewportW = window.innerWidth;
        mobileFactor = viewportW < 768 ? 0.45 : 1;
        isDesktop = viewportW >= 1024;
        isMobile = viewportW < 768;
        pageScrollRange = viewportH;
        requestTick();
      }, 150);
    };

    const clearAll = () => {
      for (const entry of parallaxEls) {
        entry.el.style.transform = "";
        entry.el.style.willChange = "";
        entry.lastTransform = "";
        if (entry.writeProgressVar) {
          entry.el.style.removeProperty("--scene-progress");
          entry.lastProgressVar = "";
        }
      }
      for (const el of pageProgressEls) {
        el.style.removeProperty("--scroll-progress-page");
      }
      lastPageProgress = "";
    };

    const startParallax = () => {
      if (running || !parallaxEls.length) return;
      running = true;
      startAnimGating();
      parallaxEls.forEach((entry) => activeObserver.observe(entry.el));
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", onResize, { passive: true });
      requestTick();
    };

    const stopParallax = () => {
      if (!running) return;
      running = false;
      stopAnimGating();
      activeObserver.disconnect();
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId);
        rafId = null;
      }
      parallaxEls.forEach((entry) => {
        entry.active = false;
      });
      clearAll();
    };

    if (!reduceMotionQuery.matches) startParallax();

    const onMotionPreferenceChange = () => {
      if (reduceMotionQuery.matches) {
        stopParallax();
        revealObserver?.disconnect();
        revealEls.forEach((el) => el.classList.add("is-revealed"));
      } else {
        startParallax();
        revealObserver?.disconnect();
        revealEls.forEach((el) => el.classList.remove("is-revealed"));
        setupReveal();
      }
    };

    reduceMotionQuery.addEventListener("change", onMotionPreferenceChange);

    return () => {
      if (resizeTimer !== null) window.clearTimeout(resizeTimer);
      stopParallax();
      activeObserver.disconnect();
      animObserver.disconnect();
      revealObserver?.disconnect();
      reduceMotionQuery.removeEventListener("change", onMotionPreferenceChange);
    };
  }, []);

  return null;
}
