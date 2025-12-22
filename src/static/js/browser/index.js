// static/js/browser/index.js
import { initCopyToast } from './copyToast.js';
import { initDeleteMixtape } from './deleteMixtape.js';

document.addEventListener('DOMContentLoaded', () => {
    initCopyToast();
    initDeleteMixtape();
});