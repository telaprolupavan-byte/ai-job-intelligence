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
 *                                      entirely, not a subtle drift. The hero
 *                                      omits this attribute on purpose: its
 *                                      already-verified motion is scrollY-based
 *                                      and is left exactly as it was.
 *   data-parallax-desktop-only        opt-in: this element's transform is
 *                                      skipped entirely below 1024px. For
 *                                      motion whose *meaning* is tied to the
 *                                      desktop composition — the Job
 *                                      Intelligence panels sliding toward a
 *                                      NERO that only sits beside them at lg
 *                                      — where the same drift on a stacked
 *                                      phone layout is just a few pixels of
 *                                      horizontal jitter under the page
 *                                      gutter. Any --scene-progress the
 *                                      element also opts into is still
 *                                      written; only the transform is
 *                                      suppressed.
 *   data-scroll-progress               opt-in, foundation for future cinematic
 *                                      scenes: writes this element's own 0->1
 *                                      transit progress to the CSS custom
 *                                      property --scene-progress (no transform
 *                                      is implied — pure data for scene-specific
 *                                      CSS/JS to consume). Works with or
 *                                      without data-parallax-speed, and reuses
 *                                      whatever rect the parallax pass already
 *                                      read for that element, so adding it
 *                                      costs no extra layout reads. Convention:
 *                                      0% entering -> 25% developing -> 50%
 *                                      primary interaction -> 75% transitioning
 *                                      -> 100% exiting. Not every section needs
 *                                      to use this — it's a reusable concept,
 *                                      not a requirement.
 *   data-reveal                       fade/rise-in once the element enters view
 *   data-reveal-delay="120"           optional stagger, ms
 *
 * Renders nothing — it only wires up effects against elements already in
 * the DOM. All continuous scroll work happens via direct style writes
 * inside a single rAF loop (no React state, no per-frame re-renders).
 *
 * Motion model (cinematic-foundation pass): native scroll is never
 * hijacked or replaced with a virtual/fake-container scroller — the
 * browser's own inertial scrolling (trackpad, touch, mouse wheel) drives
 * the real page position, exactly as it always has, which is what keeps
 * this accessible and correct on mobile Safari/Chrome and with assistive
 * tech. What's new is that the *decorative* parallax layer no longer
 * snaps 1:1 to raw scroll position every frame; each parallax-driven
 * value eases toward its scroll-derived target with a velocity-aware
 * damping factor (tighter following at high velocity so fast scrolling
 * doesn't feel laggy/chaotic, looser trailing at low velocity so slow
 * scrolling reads as fluid). That's the whole "inertial" effect: a
 * lightweight lerp on top of real, native scroll input — not a new
 * scrolling system.
 */
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

      revealEls.forEach((el, index) => {
        const delay = el.dataset.revealDelay;
        if (delay) el.style.setProperty("--reveal-delay", `${delay}ms`);
        revealObserver?.observe(el);
        void index;
      });
    };

    setupReveal();

    const root = document.documentElement;

    // Every scroll-linked value ("signal") eases toward a scroll-derived
    // target instead of snapping to it, producing the inertial/cinematic
    // catch-up feel. minEase/maxEase bound how tight that following is;
    // computeEase() picks a point between them from current scroll
    // velocity so a fast flick doesn't leave decorative layers visibly
    // dragging behind (chaotic), while idle/slow scrolling keeps a soft,
    // fluid trail instead of rigidly matching the wheel 1:1.
    const MIN_EASE = 0.14;
    const MAX_EASE = 0.38;
    // px/ms; above this the ease factor is already maxed out. Roughly a
    // fast trackpad flick — measured, not tuned to a specific device.
    const VELOCITY_SATURATION = 2.2;

    const computeEase = (velocityAbs: number) => {
      const t = Math.min(velocityAbs / VELOCITY_SATURATION, 1);
      return MIN_EASE + (MAX_EASE - MIN_EASE) * t;
    };

    const clamp01 = (value: number) => Math.min(Math.max(value, 0), 1);

    const computeLocalProgress = (el: HTMLElement, viewportH: number) => {
      const rect = el.getBoundingClientRect();
      // 0 as the element's bottom reaches the viewport's bottom edge
      // (about to enter), 1 as its top passes the viewport's top edge
      // (about to leave) — monotonic across the transit, independent of
      // how far down the page the element sits.
      return clamp01((viewportH - rect.top) / (viewportH + rect.height));
    };

    const parallaxEls = Array.from(
      document.querySelectorAll<HTMLElement>(
        "[data-parallax-speed], [data-parallax-x], [data-scroll-progress]",
      ),
    ).map((el) => {
      const local =
        el.dataset.parallaxLocal !== undefined ||
        (el.dataset.parallaxSpeed === undefined &&
          el.dataset.parallaxX === undefined);
      // Seed the eased value from the real, un-eased target so the
      // very first paint matches exactly what the original system used
      // to render — only scroll-driven changes after mount ease in.
      const initialProgress = local
        ? computeLocalProgress(el, window.innerHeight)
        : 0;
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
        renderedProgress: initialProgress,
      };
    });

    let mobileFactor = window.innerWidth < 768 ? 0.5 : 1;
    let isDesktop = window.innerWidth >= 1024;
    let scaleRange = window.innerHeight;

    let rafId: number | null = null;
    let running = false;
    let lastFrameTime = performance.now();
    let lastScrollY = window.scrollY;
    let smoothedVelocity = 0; // px/ms, exponentially smoothed
    // Unbounded eased scrollY — drives the hero's (non-local) translate
    // signal exactly like the original raw-scrollY signal did, just
    // eased. Kept separate from the 0..1 scale/progress value below:
    // conflating the two would freeze hero translation once scrolled
    // past one viewport height, which is where the clamped value
    // saturates.
    let renderedGlobalScrollY = window.scrollY;

    // In normalized (0..1 progress) units, not raw pixels, so it means
    // the same "close enough" threshold whether it's checking a local
    // element's viewport-transit progress or the page-level scroll
    // progress derived from renderedGlobalScrollY below.
    const PROGRESS_SETTLE_EPSILON = 0.0006;

    const frame = (now: number) => {
      const dt = Math.max(now - lastFrameTime, 1);
      const rawScrollY = window.scrollY;
      const viewportH = window.innerHeight;

      const instantVelocity = (rawScrollY - lastScrollY) / dt;
      smoothedVelocity += (instantVelocity - smoothedVelocity) * 0.3;
      lastScrollY = rawScrollY;
      lastFrameTime = now;

      const ease = computeEase(Math.abs(smoothedVelocity));

      // Read pass first, write pass second. Reading layout
      // (getBoundingClientRect) for a "local" element and then writing
      // el.style.transform for the *previous* element in the same loop
      // forces the browser to resolve layout synchronously on every
      // subsequent read — classic layout thrashing, and the main source
      // of scroll jank here: it scales with how many data-parallax-local
      // elements are on screen at once (four Job Intelligence panels,
      // the eight-stage Journey rail, etc.), which is exactly when fast
      // or continuous scrolling felt worst. Batching all reads before
      // any writes eliminates the forced reflow without changing any of
      // the motion math below. Non-local entries need no rect read at
      // all — only the shared scrollY-derived values below.
      const reads = parallaxEls.map((entry) => ({
        entry,
        targetProgress: entry.local
          ? computeLocalProgress(entry.el, viewportH)
          : 0,
      }));

      renderedGlobalScrollY += (rawScrollY - renderedGlobalScrollY) * ease;
      const globalProgress = clamp01(renderedGlobalScrollY / scaleRange);

      let maxDelta = Math.abs(rawScrollY - renderedGlobalScrollY) / scaleRange;

      for (const { entry, targetProgress } of reads) {
        const { el, speed, speedX, scaleTo, local, desktopOnly, writeProgressVar } =
          entry;

        if (local) {
          entry.renderedProgress +=
            (targetProgress - entry.renderedProgress) * ease;
          maxDelta = Math.max(
            maxDelta,
            Math.abs(targetProgress - entry.renderedProgress),
          );
        }

        if (writeProgressVar) {
          const progress = local ? entry.renderedProgress : globalProgress;
          el.style.setProperty("--scene-progress", progress.toFixed(4));
        }

        if (!speed && !speedX && !scaleTo) continue;

        if (desktopOnly && !isDesktop) {
          // Clear once rather than every frame, so a resize down to a
          // phone width doesn't leave a stale offset baked in.
          if (el.style.transform) el.style.transform = "";
          continue;
        }

        // Same signal shape the original hero motion was verified
        // against: a roughly-linear ramp centered on zero. For the hero
        // (local === false) it's still derived from page scrollY (now
        // eased); for everything else it's re-based on the element's
        // own transit so a speed multiplier can never push it off-screen
        // on a long page.
        const signal = local
          ? (entry.renderedProgress - 0.5) * viewportH
          : renderedGlobalScrollY;

        const translateY = -signal * speed * mobileFactor;
        const translateX = signal * speedX * mobileFactor;
        let transform = `translate3d(${translateX.toFixed(2)}px, ${translateY.toFixed(2)}px, 0)`;
        if (scaleTo) {
          const scaleProgress = local ? entry.renderedProgress : globalProgress;
          const scale = 1 + (scaleTo - 1) * scaleProgress;
          transform += ` scale(${scale.toFixed(4)})`;
        }
        el.style.transform = transform;
      }

      // Exposed for future scenes to hook into via CSS calc()/clamp() —
      // not consumed by anything in this foundation pass. Clamping
      // velocity keeps a runaway value (e.g. a huge programmatic jump)
      // from ever producing an unusable number for a future consumer.
      root.style.setProperty("--scroll-progress-page", globalProgress.toFixed(4));
      root.style.setProperty(
        "--scroll-velocity",
        Math.max(-1, Math.min(1, smoothedVelocity / VELOCITY_SATURATION)).toFixed(3),
      );

      if (maxDelta > PROGRESS_SETTLE_EPSILON) {
        rafId = window.requestAnimationFrame(frame);
      } else {
        // Settled: stop ticking rather than looping forever at rest.
        // onScroll resumes the loop on the next real scroll input.
        rafId = null;
      }
    };

    const onScroll = () => {
      if (rafId === null) {
        // Loop was idle — reset the velocity clock here rather than
        // leaving it at whatever stale timestamp the last settle left
        // behind, otherwise the first frame of a new scroll computes
        // velocity over a multi-second gap and under-reports it.
        lastFrameTime = performance.now();
        lastScrollY = window.scrollY;
        rafId = window.requestAnimationFrame(frame);
      }
    };

    const onResize = () => {
      mobileFactor = window.innerWidth < 768 ? 0.5 : 1;
      isDesktop = window.innerWidth >= 1024;
      scaleRange = window.innerHeight;
    };

    const clearTransforms = () => {
      for (const { el } of parallaxEls) el.style.transform = "";
    };

    const clearProgressVars = () => {
      for (const { el, writeProgressVar } of parallaxEls) {
        if (writeProgressVar) el.style.removeProperty("--scene-progress");
      }
      root.style.removeProperty("--scroll-progress-page");
      root.style.removeProperty("--scroll-velocity");
    };

    const startParallax = () => {
      if (running || !parallaxEls.length) return;
      running = true;
      lastFrameTime = performance.now();
      lastScrollY = window.scrollY;
      // Synchronous, not scheduled: paints the initial transforms
      // immediately (matching the pre-existing behavior this was
      // verified against) instead of leaving a one-frame gap where
      // parallax elements sit at their untransformed layout position.
      frame(lastFrameTime);
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", onResize, { passive: true });
    };

    const stopParallax = () => {
      if (!running) return;
      running = false;
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId);
        rafId = null;
      }
      clearTransforms();
      clearProgressVars();
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
      stopParallax();
      revealObserver?.disconnect();
      reduceMotionQuery.removeEventListener(
        "change",
        onMotionPreferenceChange,
      );
    };
  }, []);

  return null;
}
