/* カップ酒を絞り込む。絞り込みの欄ごとに、data-for で指した一覧だけを絞る。
   同じ見出しの中は「どれか」、見出しどうしは「かつ」で絞る */
(function () {
  Array.prototype.forEach.call(document.querySelectorAll('.cz-filter[data-for]'), function (panel) {
    var list = document.getElementById(panel.getAttribute('data-for'));
    if (!list) return;
    var section = panel.closest('section');
    var count = section.querySelector('[data-count]');
    var empty = section.querySelector('[data-empty]');
    var cards = Array.prototype.slice.call(list.querySelectorAll('.cz-card, .kz-row'));
    var groups = Array.prototype.slice.call(list.querySelectorAll('[data-group]'));
    var on = {};
    function match(card, g) {
      var want = on[g] || [];
      if (!want.length) return true;
      var have = (card.getAttribute('data-' + g) || '').split(' ');
      return want.some(function (v) { return have.indexOf(v) >= 0; });
    }
    function apply() {
      var shown = 0, filtering = false;
      Object.keys(on).forEach(function (g) { if (on[g].length) filtering = true; });
      cards.forEach(function (c) {
        var ok = Object.keys(on).every(function (g) { return match(c, g); });
        c.hidden = !ok;
        if (ok) shown++;
      });
      groups.forEach(function (g) { g.hidden = !g.querySelector('.cz-card:not([hidden]), .kz-row:not([hidden])'); });
      if (count) count.textContent = shown + (count.getAttribute('data-unit') || '本') + (filtering ? '(絞り込み中)' : '');
      if (empty) empty.hidden = shown > 0;
    }
    panel.addEventListener('click', function (ev) {
      var b = ev.target.closest('.chip');
      if (!b) return;
      var g = b.getAttribute('data-group'), v = b.getAttribute('data-value');
      var pressed = b.getAttribute('aria-pressed') !== 'true';
      b.setAttribute('aria-pressed', String(pressed));
      on[g] = pressed ? (on[g] || []).concat(v) : (on[g] || []).filter(function (x) { return x !== v; });
      apply();
    });
    apply();
  });
})();
