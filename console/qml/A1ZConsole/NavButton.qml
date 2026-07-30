import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Button {
    id: root

    required property var theme
    required property bool selected
    property string glyph: "●"

    implicitHeight: 44
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true

    contentItem: RowLayout {
        spacing: 11

        Text {
            Layout.leftMargin: 13
            text: root.glyph
            color: root.selected ? root.theme.accent : root.theme.tertiaryText
            font.pixelSize: 14
        }

        Text {
            Layout.fillWidth: true
            text: root.text
            color: root.selected ? root.theme.text : root.theme.secondaryText
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeLabel
            font.weight: root.selected ? Font.DemiBold : Font.Medium
        }
    }

    background: Rectangle {
        radius: root.theme.radiusControl
        color: root.selected ? root.theme.accentSoft
               : root.down ? root.theme.controlPressed
               : root.hovered ? root.theme.controlHover
               : "transparent"
        border.color: root.activeFocus ? root.theme.accent : "transparent"
        border.width: 1
    }
}
