import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    required property var theme
    property string text: ""
    property string level: "neutral"

    implicitHeight: 28
    implicitWidth: row.implicitWidth + 20
    radius: height / 2
    color: level === "ok" ? theme.greenSoft
           : level === "warn" ? theme.orangeSoft
           : level === "error" ? theme.redSoft
           : theme.control
    border.width: 0

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 6

        Rectangle {
            Layout.preferredWidth: 7
            Layout.preferredHeight: 7
            radius: 4
            color: root.level === "ok" ? root.theme.green
                   : root.level === "warn" ? root.theme.orange
                   : root.level === "error" ? root.theme.red
                   : root.theme.tertiaryText
        }

        Text {
            text: root.text
            color: root.level === "error" ? root.theme.red
                   : root.level === "warn" ? Qt.darker(root.theme.orange, 1.35)
                   : root.theme.text
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
            font.weight: Font.Medium
        }
    }
}
