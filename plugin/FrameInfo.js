.pragma library

function detail(entry, slot, translate) {
  if (!entry) return ""
  var props = entry.properties || {}
  if (entry.kind === "time") {
    var item = (props.ti || [])[slot]
    if (!item || !Number.isFinite(Number(item.t))) return ""
    var minutes = ((Math.round(Number(item.t) * 1440) % 1440) + 1440) % 1440
    return String(Math.floor(minutes / 60)).padStart(2, "0") + ":" + String(minutes % 60).padStart(2, "0")
  }
  if (entry.kind === "solar") {
    var solar = (props.si || [])[slot]
    if (!solar) return ""
    return translate("solar_frame", {altitude: Number(solar.a).toFixed(1), azimuth: Number(solar.z).toFixed(1)})
  }
  return translate(slot === 0 ? "light" : "dark")
}
