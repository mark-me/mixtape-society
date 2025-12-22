// static/js/common/domUtils.js
export function getOrThrow(id) {
    const el = document.getElementById(id);
    if (!el) throw new Error(`Missing element with id="${id}"`);
    return el;
}

