/**
 * i18n: loads locale dictionaries and translates UI text.
 *
 * - Default language is English.
 * - The chosen language is persisted in localStorage (a preference, not score data).
 * - Elements with a data-i18n="key" attribute have their textContent replaced
 *   when the language is applied or switched.
 * - t(key, params) returns a translated string, with {placeholder} substitution.
 */

const I18N_STORAGE_KEY = 'tetris.lang';
const I18N_DEFAULT = 'en';
const I18N_SUPPORTED = ['en', 'zh', 'es'];

class I18n {
  constructor() {
    this.lang = I18N_DEFAULT;
    this.dicts = {}; // { en: {...}, zh: {...} }
    this._listeners = [];
  }

  /** Load all supported locale files. Call once at startup. */
  async load() {
    await Promise.all(
      I18N_SUPPORTED.map(async (code) => {
        const res = await fetch(`locales/${code}.json`);
        this.dicts[code] = await res.json();
      })
    );
    const saved = localStorage.getItem(I18N_STORAGE_KEY);
    this.lang = I18N_SUPPORTED.includes(saved) ? saved : I18N_DEFAULT;
  }

  /** Translate a key, substituting {name} placeholders from params. */
  t(key, params = {}) {
    const dict = this.dicts[this.lang] || {};
    let text = dict[key];
    if (text === undefined) text = key; // fall back to the key itself
    return text.replace(/\{(\w+)\}/g, (_, name) =>
      params[name] !== undefined ? params[name] : `{${name}}`
    );
  }

  /** Change language, persist it, re-render, and notify listeners. */
  setLanguage(code) {
    if (!I18N_SUPPORTED.includes(code)) return;
    this.lang = code;
    localStorage.setItem(I18N_STORAGE_KEY, code);
    this.apply();
    this._listeners.forEach((fn) => fn(code));
  }

  /** Register a callback fired after each language change. */
  onChange(fn) {
    this._listeners.push(fn);
  }

  /** Replace text of all [data-i18n] elements and set <html lang>. */
  apply() {
    document.documentElement.lang = this.lang;
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = this.t(el.getAttribute('data-i18n'));
    });
  }
}

const i18n = new I18n();
