// Live question: HTMX drops a 5xx or a timeout without a word, so say it where the answer would go.
// The form carries the message (data-error) in the visitor's language.
(function () {
  if (!window.htmx) return;
  htmx.config.timeout = 55000;
  function fail(e) {
    var form = e.detail.elt;
    if (!form || !form.classList || !form.classList.contains("live")) return;
    var slot = document.getElementById("answer-live");
    if (!slot) return;
    var line = document.createElement("p");
    line.className = "callout blocked";
    line.textContent = form.getAttribute("data-error") || "";
    slot.replaceChildren(line);
  }
  ["htmx:responseError", "htmx:sendError", "htmx:timeout"].forEach(function (name) {
    document.addEventListener(name, fail);
  });
})();
