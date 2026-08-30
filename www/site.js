// Callosum public site — shared scroll-reveal behavior (2026-08-30).
// Previously hand-copied into index.html and how-it-works.html separately; identical logic, one home.
// Honors prefers-reduced-motion (reveals everything immediately, no animation) and degrades to "always visible"
// if IntersectionObserver isn't available.
(function () {
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var revs = document.querySelectorAll(".reveal:not(.in)");
  if (reduce) {
    revs.forEach(function (r) { r.classList.add("in"); });
  } else if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: .16, rootMargin: "0px 0px -8% 0px" });
    revs.forEach(function (r) { io.observe(r); });
  } else {
    revs.forEach(function (r) { r.classList.add("in"); });
  }
})();
