(function () {
  if (!window.gsap) return;

  const mm = gsap.matchMedia();

  mm.add("(prefers-reduced-motion: no-preference)", function () {
    gsap.defaults({ duration: 0.5, ease: "power2.out" });

    document.addEventListener("nir:ready", function () {
      const tl = gsap.timeline();
      const addFrom = function (selector, vars, position) {
        if (document.querySelector(selector)) tl.from(selector, vars, position);
      };

      addFrom(".nir-masthead", { autoAlpha: 0, y: 16, duration: 0.45 });
      addFrom(".nir-stats", { autoAlpha: 0, y: 12, duration: 0.4 }, "-=0.25");
      addFrom(".nir-tabs", { autoAlpha: 0, y: 10, duration: 0.35 }, "-=0.25");
      addFrom(".nir-controls", { autoAlpha: 0, y: 8, duration: 0.35 }, "-=0.2");
      addFrom(".nir-summary-bar", { autoAlpha: 0, y: 8, duration: 0.3 }, "-=0.2");
      addFrom(".nir-top-stories", { autoAlpha: 0, y: 12, duration: 0.4 }, "-=0.15");
      addFrom(".nir-list", { autoAlpha: 0, y: 12, duration: 0.4 }, "-=0.2");
    }, { once: true });

    document.addEventListener("nir:storiesRendered", function () {
      const cards = Array.from(document.querySelectorAll(".nir-story-card")).slice(0, 12);
      if (!cards.length) return;
      gsap.killTweensOf(cards);
      gsap.set(cards, { clearProps: "transform" });
      gsap.from(cards, { autoAlpha: 0, y: 14, stagger: 0.04, duration: 0.35, clearProps: "opacity,visibility,transform" });
    });

    document.addEventListener("nir:listRendered", function () {
      const cards = Array.from(document.querySelectorAll(".nir-news-card")).slice(0, 30);
      if (!cards.length) return;
      gsap.from(cards, { autoAlpha: 0, y: 10, stagger: 0.025, duration: 0.35, clearProps: "transform,opacity,visibility" });
    });

    const revealEls = document.querySelectorAll(".nir-community, .nir-diagnostics");
    if (revealEls.length && window.IntersectionObserver) {
      gsap.set(revealEls, { y: 12 });
      const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            gsap.to(entry.target, { y: 0, duration: 0.4, clearProps: "transform" });
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.08 });
      revealEls.forEach(function (el) { observer.observe(el); });
    }
  });
}());
