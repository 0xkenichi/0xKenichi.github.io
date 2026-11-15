(function () {
    // Decorative short refs for builds, derived from the build name
    function ref(s) {
        var h = 2166136261;
        for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
        var x = (h >>> 0).toString(16).padStart(8, '0');
        return '0x' + x.slice(0, 4) + '…' + x.slice(4);
    }
    document.querySelectorAll('.build').forEach(function (row) {
        var name = row.querySelector('.b-name b');
        var r = row.querySelector('.ref');
        if (name && r) r.textContent = ref(name.textContent);
    });

    // Theme toggle
    var root = document.documentElement;
    document.getElementById('theme').addEventListener('click', function () {
        var dark = root.getAttribute('data-theme') === 'dark' ||
            (!root.getAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
        var next = dark ? 'light' : 'dark';
        root.setAttribute('data-theme', next);
        try { localStorage.setItem('theme', next); } catch (e) {}
    });

    // Toast + copy link
    var toast = document.getElementById('toast');
    function say(msg) {
        toast.textContent = msg; toast.classList.add('show');
        clearTimeout(say.t); say.t = setTimeout(function () { toast.classList.remove('show'); }, 1600);
    }
    document.querySelectorAll('[data-copy]').forEach(function (b) {
        b.addEventListener('click', function () {
            var v = b.getAttribute('data-copy');
            if (navigator.clipboard) navigator.clipboard.writeText(v).then(function () { say('Link copied'); }, function () { say(v); });
            else say(v);
        });
    });

    // Build filters
    var filter = 'all';
    var q = document.getElementById('q');
    document.querySelectorAll('.filter').forEach(function (b) {
        b.addEventListener('click', function () {
            document.querySelectorAll('.filter').forEach(function (x) { x.classList.remove('is-on'); });
            b.classList.add('is-on');
            filter = b.getAttribute('data-f');
            apply();
        });
    });

    // Search across everything marked .searchable
    var items = Array.prototype.slice.call(document.querySelectorAll('.searchable'));
    function apply() {
        var term = (q.value || '').trim().toLowerCase();
        var shown = 0;
        items.forEach(function (el) {
            var text = (el.textContent + ' ' + (el.getAttribute('data-keys') || '')).toLowerCase();
            var okTerm = !term || term.split(/\s+/).every(function (w) { return text.indexOf(w) !== -1; });
            var okFilter = !el.classList.contains('build') || filter === 'all' ||
                (el.getAttribute('data-tags') || '').split(' ').indexOf(filter) !== -1;
            var on = okTerm && okFilter;
            el.classList.toggle('is-hidden', !on);
            if (on && term) shown++;
            if (on && term && el.tagName === 'DETAILS') el.open = true;
        });
        // hide whole sections with nothing left while searching
        document.querySelectorAll('.block').forEach(function (sec) {
            var any = sec.querySelector('.searchable:not(.is-hidden)');
            sec.classList.toggle('is-hidden', !!term && !any);
        });
        document.getElementById('empty').hidden = !(term && shown === 0);
    }
    q.addEventListener('input', apply);
    document.addEventListener('keydown', function (e) {
        if (e.key === '/' && document.activeElement !== q) { e.preventDefault(); q.focus(); }
        if (e.key === 'Escape' && document.activeElement === q) { q.value = ''; apply(); q.blur(); }
    });

    // Highlight the tab for the section in view
    var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
    if ('IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (en) {
                if (!en.isIntersecting) return;
                tabs.forEach(function (t) { t.classList.toggle('is-on', t.getAttribute('href') === '#' + en.target.id); });
            });
        }, { rootMargin: '-45% 0px -50% 0px' });
        document.querySelectorAll('.block').forEach(function (s) { io.observe(s); });
    }
})();
