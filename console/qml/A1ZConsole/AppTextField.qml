import QtQuick
import QtQuick.Controls.Basic

TextField {
    id: root

    required property var theme
    property bool dangerFocus: false

    implicitHeight: 40
    leftPadding: 12
    rightPadding: 12
    color: enabled ? theme.text : theme.placeholderText
    placeholderTextColor: theme.placeholderText
    selectionColor: theme.accentSoft
    selectedTextColor: theme.text
    font.family: theme.fontFamily
    font.pixelSize: theme.typeLabel
    selectByMouse: true

    background: Rectangle {
        radius: root.theme.radiusControl
        color: !root.enabled ? Qt.lighter(root.theme.control, 1.03)
               : root.hovered ? root.theme.controlHover
                              : root.theme.control
        border.color: root.activeFocus
                      ? (root.dangerFocus ? root.theme.red : root.theme.accent)
                      : "transparent"
        border.width: root.activeFocus ? 2 : 0
        Behavior on color {
            ColorAnimation { duration: root.theme.motionFast }
        }
    }
}
