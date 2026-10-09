.pragma library

function language(all, messages, lang, qtLocale) {
  // LC_ALL/LC_MESSAGES/LANG follow the process's message locale precedence.
  var locale = all || messages || lang || qtLocale || "en"
  var base = locale.toLowerCase().split(/[_.@-]/)[0]
  if (base === "zh") return "zh_CN"
  return ["en", "ja", "ko", "es", "fr", "de", "pt", "ru"].indexOf(base) >= 0 ? base : "en"
}

function text(catalog, locale, key, args) {
  var fallback = catalog.en || {}
  var translated = catalog[locale] || fallback
  var value = translated[key] || fallback[key] || key
  args = args || {}
  return value.replace(/\{(\w+)\}/g, function(match, name) {
    return args[name] === undefined ? match : String(args[name])
  })
}

function message(catalog, locale, value) {
  var source = catalog.en || {}
  for (var key in source)
    if (source[key] === value) return text(catalog, locale, key)
  return value || ""
}
