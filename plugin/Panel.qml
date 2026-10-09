pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui as Ui
import qs.Commons as Commons
import "I18n.js" as I18n
import "FrameInfo.js" as FrameInfo

Ui.Panel {
  id: root
  moduleName: "org.omarchy.heic"
  ipcTarget: "org.omarchy.heic"
  property var desktop: ({mode: "disabled", library: [], service: false})
  property string message: ""
  property int previewIndex: 0
  property var catalog: ({})
  property string importNotice: ""
  property string seenImport: ""
  property bool statusLoaded: false
  readonly property bool bundledSetup: /\/plugin\/Panel.qml$/.test(Qt.resolvedUrl("Panel.qml").toString())
  readonly property string runtimeVersion: "0.3.1"
  readonly property bool importing: !!desktop.importing
  readonly property string language: I18n.language(Quickshell.env("LC_ALL"), Quickshell.env("LC_MESSAGES"), Quickshell.env("LANG"), Qt.locale().name)
  readonly property bool previewing: !!desktop.preview
  function t(key, args) { return I18n.text(catalog, language, key, args) }
  function translated(value) { return I18n.message(catalog, language, value) }
  FileView {
    path: decodeURIComponent(Qt.resolvedUrl("i18n.json").toString().replace(/^file:\/\//, ""))
    onLoaded: { try { root.catalog = JSON.parse(text()) } catch (e) { console.warn("HEIC translations:", e) } }
  }
  readonly property string executable: Quickshell.env("HOME") + "/.local/bin/omarchy-heic"
  readonly property var selected: {
    var entries = desktop.library || []
    for (var i = 0; i < entries.length; i++)
      if (entries[i].id === desktop.selected) return entries[i]
    return null
  }
  readonly property var frames: selected ? selected.frames : []
  readonly property color ink: root.barForeground
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function refresh() {
    if (!query.running && !action.running) query.running = true
  }
  function run(args) {
    if (action.running) return
    message = ""
    action.command = [executable].concat(args)
    action.running = true
  }
  function acceptStatus(text) {
    try {
      var value = JSON.parse(text)
      if (value.ok === false) { message = value.error; return }
      desktop = value
      if (value.import_result) {
        var token = JSON.stringify(value.import_result)
        if (statusLoaded && token !== seenImport) {
          importNotice = root.t("import_result", {count: value.import_result.imported.length, failed: value.import_result.errors.length})
          noticeTimer.restart()
        }
        seenImport = token
      }
      statusLoaded = true
      previewIndex = Math.min(previewIndex, Math.max(0, frames.length - 1))
    } catch (e) { message = root.t("status_error") }
  }
  onOpenedChanged: if (opened) refresh()

  Process {
    id: query
    command: [root.executable, "status", "--json"]
    stdout: StdioCollector { onStreamFinished: root.acceptStatus(text) }
    stderr: StdioCollector { onStreamFinished: if (text.trim()) root.message = text.trim() }
  }
  Process {
    id: action
    stdout: StdioCollector { onStreamFinished: if (text.trim()) root.acceptStatus(text) }
    stderr: StdioCollector {
      onStreamFinished: {
        if (!text.trim()) return
        try { root.message = JSON.parse(text).error || text } catch (e) { root.message = text }
      }
    }
    onExited: function(exitCode, exitStatus) { if (exitCode === 0) root.message = ""; root.refresh() }
  }
  Process {
    id: setup
    command: root.bundledSetup ? ["python3", decodeURIComponent(Qt.resolvedUrl("../install.py").toString().replace(/^file:\/\//, "")), "--shell-managed"] :
      ["systemctl", "--user", "restart", "omarchy-heic.service"]
    stderr: StdioCollector { onStreamFinished: if (text.trim()) root.message = text.trim() }
    onExited: function(exitCode, exitStatus) { if (exitCode === 0) root.message = ""; root.refresh() }
  }
  Timer { interval: root.previewing || root.importing ? 500 : 3000; repeat: true; running: true; triggeredOnStart: true; onTriggered: root.refresh() }
  Timer { id: noticeTimer; interval: 5000; onTriggered: root.importNotice = "" }
  Process {
    id: picker
    command: [Quickshell.env("HOME") + "/.local/bin/omarchy-heic-picker",
      "--title", root.t("import_title"), "--filter", root.t("file_filter"),
      "--accept", root.t("open_files"), "--cancel", root.t("cancel"), "--hint", root.t("multiselect_hint")]
    property var paths: []
    stdout: StdioCollector {
      onStreamFinished: {
        try { picker.paths = JSON.parse(text) } catch (e) { picker.paths = [] }
      }
    }
    stderr: StdioCollector { onStreamFinished: if (text.trim()) console.warn("HEIC picker:", text) }
    onExited: function(exitCode, exitStatus) {
      root.open()
      if (exitCode !== 0) { root.message = root.t("picker_error"); return }
      if (paths.length) root.run(["import", "--background"].concat(paths))
    }
  }
  Ui.WidgetButton {
    id: button
    bar: root.bar
    text: "󰸉"
    active: root.opened
    tooltipText: root.t("title") + " · " + root.t(root.desktop.mode)
    onPressed: root.toggle()
  }
  Ui.KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: body
    contentWidth: panel.fittedContentWidth(Commons.Style.space(440))
    contentHeight: panel.fittedContentHeight(body.implicitHeight)
    Column {
      id: body
      width: parent.width
      spacing: Commons.Style.space(10)
      Keys.onEscapePressed: root.close()
      Text {
        text: root.t("title")
        font.pixelSize: Commons.Style.font.heading
        font.bold: true
        color: root.ink
      }
      Text {
        width: parent.width
        text: !root.desktop.service ? root.t("service_off") : root.importing ? root.t("importing", root.desktop.importing) : action.running ? root.t("working") :
              root.t(root.desktop.mode) + (root.selected ? " · " + root.t(root.selected.kind) : "")
        color: root.ink
        elide: Text.ElideRight
      }
      Ui.Button {
        text: root.t("setup")
        visible: !root.desktop.service || (root.bundledSetup && root.desktop.plugin_version !== root.runtimeVersion)
        enabled: !setup.running
        focusable: true
        onClicked: { root.message = ""; setup.running = true }
      }
      LibraryPicker {
        width: parent.width
        label: root.t("library")
        value: root.desktop.selected || ""
        entries: root.desktop.library || []
        emptyText: root.t("empty_library")
        removeText: root.t("remove_wallpaper")
        enabled: !action.running && !root.importing
        onChosen: function(identity) { root.previewIndex = 0; root.run(["select", identity]) }
        onRemoved: function(identity) { root.previewIndex = 0; root.run(["remove", identity]) }
      }
      Item {
        width: parent.width
        height: Commons.Style.space(128)
        visible: root.frames.length > 0
        Image {
          id: thumbnail
          anchors.fill: parent
          sourceSize.width: 1024
          fillMode: Image.PreserveAspectFit
          asynchronous: true
          source: root.frames.length && root.frames[root.previewIndex].thumbnail ? Commons.Util.fileUrl(root.frames[root.previewIndex].thumbnail) : ""
        }
      }
      Row {
        visible: root.frames.length > 0
        spacing: Commons.Style.space(6)
        Ui.Button { text: "‹"; focusable: true; onClicked: root.previewIndex = (root.previewIndex + root.frames.length - 1) % root.frames.length }
        Text {
          text: root.t("frame", {index: root.previewIndex + 1, count: root.frames.length}) +
            (FrameInfo.detail(root.selected, root.previewIndex, root.t) ? " · " + FrameInfo.detail(root.selected, root.previewIndex, root.t) : "")
          color: root.ink
          anchors.verticalCenter: parent.verticalCenter
          font.pixelSize: Commons.Style.font.caption
        }
        Ui.Button { text: "›"; focusable: true; onClicked: root.previewIndex = (root.previewIndex + 1) % root.frames.length }
      }
      Flow {
        width: parent.width
        spacing: Commons.Style.space(6)
        Ui.Button {
          text: root.t("import"); focusable: true; enabled: !action.running && !picker.running && !root.importing
          onClicked: { root.message = ""; root.importNotice = ""; picker.paths = []; root.close(); picker.running = true }
        }
        Ui.Button {
          text: root.desktop.mode === "active" ? root.t("pause") : root.t("enable")
          focusable: true
          enabled: !!root.selected && !action.running && !root.previewing && !root.importing
          onClicked: root.run([root.desktop.mode === "active" ? "pause" : "enable"])
        }
        Ui.Button { text: root.t("disable"); focusable: true; enabled: !action.running; onClicked: root.run(["disable"]) }
        Ui.Button {
          text: root.t(root.previewing ? "preview_stop" : "preview")
          focusable: true
          enabled: !!root.selected && !action.running && !root.importing
          onClicked: root.run([root.previewing ? "preview-stop" : "preview"])
        }
      }
      Text {
        width: parent.width
        text: !root.desktop.preview ? "" : root.desktop.preview.phase === "preparing" ?
              root.t("preparing", {percent: Math.round(root.desktop.preview.progress * 100)}) :
              root.t("playing", {time: root.desktop.preview.appearance ? root.t(root.desktop.preview.appearance) : root.desktop.preview.time,
                index: root.desktop.preview.index, count: root.desktop.preview.count, duration: root.desktop.preview.total_seconds})
        visible: root.previewing
        color: root.ink
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
      }
      Text {
        width: parent.width
        visible: root.importNotice.length > 0
        text: root.importNotice
        color: root.ink
        elide: Text.ElideRight
      }
      Text {
        width: parent.width
        text: root.translated(root.message || root.desktop.error || root.desktop.reason || "")
        visible: text.length > 0
        color: Commons.Color.urgent
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
        textFormat: Text.PlainText
      }
      Column {
        width: parent.width
        spacing: Commons.Style.space(8)
        visible: !!root.selected && root.selected.kind === "solar"
        Text { text: root.t("location_title"); font.bold: true; color: root.ink }
        Text {
          width: parent.width
          text: root.desktop.location ? root.t("location_value", root.desktop.location) : root.t("no_location")
          color: root.ink
          elide: Text.ElideRight
        }
        Row {
          spacing: Commons.Style.space(6)
          Ui.TextField { id: lat; width: (body.width - Commons.Style.space(6)) / 2; placeholderText: root.t("latitude") }
          Ui.TextField { id: lon; width: lat.width; placeholderText: root.t("longitude") }
        }
        Flow {
          width: parent.width
          spacing: Commons.Style.space(6)
          Ui.Button { text: root.t("save_location"); focusable: true; enabled: !action.running; onClicked: root.run(["location", lat.text.replace(",", "."), lon.text.replace(",", ".")]) }
          Ui.Button { text: root.t("import_location"); focusable: true; enabled: !action.running; onClicked: root.run(["import-location"]) }
        }
      }
    }
  }
}
