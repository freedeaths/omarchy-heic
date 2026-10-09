pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import qs.Ui as Ui
import qs.Commons as Commons

Column {
  id: root
  property var entries: []
  property string value: ""
  property string label: ""
  property string emptyText: ""
  property string removeText: ""
  signal chosen(string identity)
  signal removed(string identity)
  spacing: Commons.Style.spacing.labelGap
  function choose(index) {
    if (index < 0 || index >= entries.length) return
    chosen(entries[index].id)
    popup.close()
  }
  function remove(index) {
    if (index < 0 || index >= entries.length) return
    removed(entries[index].id)
    popup.close()
  }
  Text {
    text: root.label
    color: Commons.Color.popups.text
    font.pixelSize: Commons.Style.font.caption
    font.bold: true
  }
  Ui.Button {
    id: trigger
    objectName: "libraryTrigger"
    width: parent.width
    text: {
      for (var i = 0; i < root.entries.length; i++)
        if (root.entries[i].id === root.value) return root.entries[i].name + "  ▾"
      return root.emptyText + "  ▾"
    }
    bordered: true
    leftAlign: true
    focusable: true
    enabled: root.entries.length > 0
    onClicked: popup.opened ? popup.close() : popup.open()
    Popup {
      id: popup
      y: trigger.height + Commons.Style.spacing.xxs
      width: trigger.width
      height: Math.min(root.entries.length, 8) * Commons.Style.spacing.popupRowHeight + padding * 2
      padding: Commons.Style.spacing.hairline
      focus: true
      background: Rectangle {
        color: Commons.Color.popups.background
        border.color: Commons.Color.popups.border
        radius: Commons.Style.cornerRadius
      }
      onOpened: {
        list.currentIndex = 0
        for (var i = 0; i < root.entries.length; i++)
          if (root.entries[i].id === root.value) list.currentIndex = i
        list.forceActiveFocus()
      }
      contentItem: ListView {
        id: list
        objectName: "libraryList"
        clip: true
        model: root.entries
        boundsBehavior: Flickable.StopAtBounds
        Keys.onReturnPressed: root.choose(currentIndex)
        Keys.onEnterPressed: root.choose(currentIndex)
        Keys.onDeletePressed: root.remove(currentIndex)
        Keys.onEscapePressed: popup.close()
        delegate: Rectangle {
          id: row
          required property var modelData
          required property int index
          width: list.width
          height: Commons.Style.spacing.popupRowHeight
          color: hover.hovered || index === list.currentIndex ? Commons.Style.hoverFillFor(Commons.Color.popups.text, Commons.Color.accent) : "transparent"
          HoverHandler { id: hover }
          Text {
            anchors.left: parent.left
            anchors.right: erase.left
            anchors.margins: Commons.Style.spacing.controlPaddingX
            anchors.verticalCenter: parent.verticalCenter
            text: row.modelData.name
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: Commons.Color.popups.text
            font.pixelSize: Commons.Style.font.body
          }
          MouseArea {
            anchors.left: parent.left
            anchors.right: erase.left
            height: parent.height
            cursorShape: Qt.PointingHandCursor
            onClicked: root.choose(row.index)
          }
          Ui.Button {
            id: erase
            objectName: "libraryRemove" + row.index
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: "×"
            tooltipText: root.removeText
            focusable: true
            visible: hover.hovered || activeFocus
            onClicked: root.remove(row.index)
          }
        }
      }
    }
  }
}
