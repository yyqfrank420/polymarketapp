(function () {
    try {
        var hasPassed = window.localStorage && window.localStorage.getItem('ie_age_gate_passed') === 'true';
        var root = document.documentElement;
        root.dataset.ageGateStatus = hasPassed ? 'passed' : 'required';

        if (!hasPassed) {
            root.classList.add('age-gate-prelock');
        } else {
            root.classList.remove('age-gate-prelock');
        }
    } catch (error) {
        var fallbackRoot = document.documentElement;
        fallbackRoot.dataset.ageGateStatus = 'required';
        fallbackRoot.classList.add('age-gate-prelock');
    }
})();

