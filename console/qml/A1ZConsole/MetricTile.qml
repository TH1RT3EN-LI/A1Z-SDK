import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    required property var theme
    property string label: ""
    property string value: "—"
    property string hint: ""
    property color accentColor: theme.accent

    implicitHeight: 92
    radius: theme.radiusControl
    color: theme.tile
    border.color: theme.border
    border.width: 1

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 3
        radius: 2
        color: root.accentColor
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 13
        anchors.leftMargin: 16
        spacing: 3

        Text {
            text: root.label
            color: root.theme.tertiaryText
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
            font.weight: Font.Medium
        }

        Text {
            Layout.fillWidth: true
            text: root.value
            color: root.theme.text
            elide: Text.ElideRight
            font.family: root.theme.fontFamily
            font.pixelSize: 18
            font.weight: Font.DemiBold
        }

        Text {
            Layout.fillWidth: true
            text: root.hint
            visible: text.length > 0
            color: root.theme.secondaryText
            elide: Text.ElideRight
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
        }
    }
}
