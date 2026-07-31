import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    required property var theme
    property string title: ""
    property string subtitle: ""

    spacing: 8

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 2

        Text {
            Layout.fillWidth: true
            text: root.title
            textFormat: Text.PlainText
            color: root.theme.text
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeTitle
            font.weight: Font.DemiBold
        }

        Text {
            Layout.fillWidth: true
            visible: root.subtitle.length > 0
            text: root.subtitle
            textFormat: Text.PlainText
            color: root.theme.tertiaryText
            wrapMode: Text.WordWrap
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
        }
    }
}
