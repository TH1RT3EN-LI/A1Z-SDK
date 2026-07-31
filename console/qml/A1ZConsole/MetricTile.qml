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
    border.width: 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 4

        Text {
            text: root.label
            textFormat: Text.PlainText
            color: root.theme.tertiaryText
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
            font.weight: Font.Medium
        }

        Text {
            Layout.fillWidth: true
            text: root.value
            textFormat: Text.PlainText
            color: root.theme.text
            elide: Text.ElideRight
            font.family: root.theme.fontFamily
            font.pixelSize: 18
            font.weight: Font.DemiBold
        }

        Text {
            Layout.fillWidth: true
            text: root.hint
            textFormat: Text.PlainText
            visible: text.length > 0
            color: root.theme.secondaryText
            elide: Text.ElideRight
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
        }
    }
}
