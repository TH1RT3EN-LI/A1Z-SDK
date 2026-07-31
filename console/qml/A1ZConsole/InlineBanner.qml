import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    required property var theme
    property string text: ""
    property string level: "info"

    implicitHeight: text.length > 0 ? 38 : 0
    radius: theme.radiusControl
    color: level === "error" ? theme.redSoft
           : level === "warn" ? theme.orangeSoft
                              : theme.accentSoft

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 8

        Rectangle {
            Layout.preferredWidth: 18
            Layout.preferredHeight: 18
            radius: 9
            color: root.level === "error" ? root.theme.red
                   : root.level === "warn" ? root.theme.orange
                                          : root.theme.accent

            Text {
                anchors.centerIn: parent
                text: root.level === "error" ? "!" : "i"
                color: root.theme.textOnAccent
                font.family: root.theme.fontFamily
                font.pixelSize: 11
                font.weight: Font.Bold
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.text
            color: root.level === "error" ? root.theme.red
                   : root.theme.text
            elide: Text.ElideRight
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
            font.weight: Font.Medium
        }
    }
}
