import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    required property var theme
    property string title: ""

    spacing: 10

    Text {
        Layout.fillWidth: true
        text: root.title
        color: root.theme.text
        font.family: root.theme.fontFamily
        font.pixelSize: root.theme.typeTitle
        font.weight: Font.DemiBold
    }
}
