// Explore: reveal stages on scroll, mark the current stage in the bar and the opened card.
// Without this script, or with reduced motion, the server-rendered page is fully visible.
(function () {
  var stages = document.querySelectorAll("section.stage");
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!("IntersectionObserver" in window) || !stages.length) return;
  var links = document.querySelectorAll(".stagebar a");
  var current = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      links.forEach(function (a) {
        if (a.getAttribute("href") === "#" + e.target.id) a.setAttribute("aria-current", "true");
        else a.removeAttribute("aria-current");
      });
    });
  }, { rootMargin: "-30% 0px -60% 0px" });
  stages.forEach(function (s) { current.observe(s); });
  if (!reduced) {
    var reveal = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); reveal.unobserve(e.target); }
      });
    }, { threshold: 0.1 });
    stages.forEach(function (s) {
      if (s.getBoundingClientRect().top > window.innerHeight) { s.classList.add("reveal"); reveal.observe(s); }
    });
  }
  document.addEventListener("htmx:afterRequest", function (e) {
    var card = e.detail.elt;
    if (!card.classList || !card.classList.contains("qcard")) return;
    card.parentNode.querySelectorAll(".qcard").forEach(function (c) { c.removeAttribute("aria-pressed"); });
    card.setAttribute("aria-pressed", "true");
  });
})();
