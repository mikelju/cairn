// Ask screen: mark the pressed question. Without this script the server-rendered page still works.
document.addEventListener("htmx:afterRequest", function (e) {
  var btn = e.detail.elt;
  if (!btn.classList || !btn.classList.contains("qbtn")) return;
  document.querySelectorAll(".qbtn").forEach(function (b) { b.removeAttribute("aria-pressed"); });
  btn.setAttribute("aria-pressed", "true");
});
