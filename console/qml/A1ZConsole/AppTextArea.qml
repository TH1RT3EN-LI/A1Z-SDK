import QtQuick
import QtQuick.Controls.Basic

TextArea {
    id: root

    required property var theme
    property bool dark: false

    leftPadding: 12
    rightPadding: 12
    topPadding: 10
    bottomPadding: 10
    color: dark ? "#FFF5F5F7"
                : enabled ? theme.text : theme.placeholderText
    placeholderTextColor: dark ? "#FF8E8E93" : theme.placeholderText
    selectionColor: dark ? "#660A84FF" : theme.accentSoft
    selectedTextColor: dark ? "#FFFFFFFF" : theme.text
    font.family: theme.fontFamily
    font.pixelSize: theme.typeLabel
    selectByMouse: true

    background: Rectangle {
        radius: root.theme.radiusControl
        color: root.dark ? root.theme.logCanvas
                         : root.hovered ? root.theme.controlHover
                                        : root.theme.control
        border.color: root.activeFocus ? root.theme.accent : "transparent"
        border.width: root.activeFocus ? 2 : 0
        Behavior on color {
            ColorAnimation { duration: root.theme.motionFast }
        }
    }
}
