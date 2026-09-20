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
 *   data-reveal                       fade/rise-in once the element enters view
 *   data-reveal-delay="120"           optional stagger, ms
 *
 * Renders nothing — it only wires up effects against elements already in
 * the DOM. All continuous scroll work happens via direct style writes
 * inside a single rAF loop (no React state, no per-frame re-renders).
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

    const parallaxEls = Array.from(
      document.querySelectorAll<HTMLElement>(
        "[data-parallax-speed], [data-parallax-x]",
      ),
    ).map((el) => ({
      el,
      speed: parseFloat(el.dataset.parallaxSpeed ?? "0") || 0,
      speedX: parseFloat(el.dataset.parallaxX ?? "0") || 0,
      scaleTo: el.dataset.parallaxScaleTo
        ? parseFloat(el.dataset.parallaxScaleTo)
        : null,
      local: el.dataset.parallaxLocal !== undefined,
    }));

    let mobileFactor = window.innerWidth < 768 ? 0.5 : 1;
    let scaleRange = window.innerHeight;
    let ticking = false;
    let running = false;

    const applyTransforms = () => {
      const scrollY = window.scrollY;
      const viewportH = window.innerHeight;

      for (const { el, speed, speedX, scaleTo, local } of parallaxEls) {
        // "signal" and "progress" are the two knobs every formula below
        // is built from — for the hero (local === false) they're exactly
        // the original page-global scrollY / scrollY-over-viewport-height
        // this was verified against. For anything local, they're the same
        // shape of value (a roughly-linear ramp, 0 near the top of the
        // element's transit through the viewport), just re-based on that
        // element's own position instead of the whole page's.
        let signal: number;
        let progress = 0;

        if (local) {
          const rect = el.getBoundingClientRect();
          // 0 as the element's bottom reaches the viewport's bottom edge
          // (about to enter), 1 as its top passes the viewport's top edge
          // (about to leave) — monotonic across the transit, independent
          // of how far down the page the element sits.
          progress = Math.min(
            Math.max(
              (viewportH - rect.top) / (viewportH + rect.height),
              0,
            ),
            1,
          );
          signal = (progress - 0.5) * viewportH;
        } else {
          signal = scrollY;
          if (scaleTo) progress = Math.min(Math.max(scrollY / scaleRange, 0), 1);
        }

        const translateY = -signal * speed * mobileFactor;
        const translateX = signal * speedX * mobileFactor;
        let transform = `translate3d(${translateX.toFixed(2)}px, ${translateY.toFixed(2)}px, 0)`;
        if (scaleTo) {
          const scale = 1 + (scaleTo - 1) * progress;
          transform += ` scale(${scale.toFixed(4)})`;
        }
        el.style.transform = transform;
      }
      ticking = false;
    };

    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(applyTransforms);
        ticking = true;
      }
    };

    const onResize = () => {
      mobileFactor = window.innerWidth < 768 ? 0.5 : 1;
      scaleRange = window.innerHeight;
    };

    const clearTransforms = () => {
      for (const { el } of parallaxEls) el.style.transform = "";
    };

    const startParallax = () => {
      if (running || !parallaxEls.length) return;
      running = true;
      applyTransforms();
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", onResize, { passive: true });
    };

    const stopParallax = () => {
      if (!running) return;
      running = false;
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      clearTransforms();
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
