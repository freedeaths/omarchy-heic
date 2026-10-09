import QtQuick
import QtTest
import "../../plugin" as Plugin
Item {
  width: 500; height: 500
  Plugin.LibraryPicker {
    id: picker
    width: 440
    entries: [{id: "one", name: "One.heic"}, {id: "two", name: "Two.heic"}]
    value: "one"
    label: "Wallpapers"
    emptyText: "Select"
    removeText: "Remove"
  }
  SignalSpy { id: chosen; target: picker; signalName: "chosen" }
  SignalSpy { id: removed; target: picker; signalName: "removed" }
  TestCase {
    name: "LibraryPicker"
    when: windowShown
    function test_select_and_remove_have_separate_actions() {
      var trigger = findChild(picker, "libraryTrigger")
      verify(trigger !== null)
      mouseClick(trigger)
      var list = findChild(picker, "libraryList")
      tryVerify(function() { return list && list.count === 2 && list.currentItem })
      mouseClick(list.currentItem, 20, list.currentItem.height / 2)
      compare(chosen.count, 1)
      compare(chosen.signalArguments[0][0], "one")
      compare(removed.count, 0)
      wait(200)
      mouseClick(trigger)
      wait(200)
      var erase = findChild(list.currentItem, "libraryRemove0")
      verify(erase !== null)
      mouseMove(erase)
      tryCompare(erase, "visible", true)
      mouseClick(erase)
      compare(removed.count, 1)
      compare(removed.signalArguments[0][0], "one")
      compare(chosen.count, 1)
      console.log("HEIC_LIBRARY_UI_OK")
    }
  }
}
