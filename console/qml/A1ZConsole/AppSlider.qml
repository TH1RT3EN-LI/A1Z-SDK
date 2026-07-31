import QtQuick
import QtQuick.Controls.Basic

Slider {
    id: root

    required property var theme

    implicitHeight: 28
    focusPolicy: Qt.StrongFocus

    background: Rectangle {
        x: root.leftPadding
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.availableWidth
        height: 4
        radius: 2
        color: root.theme.separatorStrong

        Rectangle {
            width: root.visualPosition * parent.width
            height: parent.height
            radius: parent.radius
            color: root.enabled ? root.theme.accent : root.theme.placeholderText
        }
    }

    handle: Rectangle {
        x: root.leftPadding + root.visualPosition
           * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        implicitWidth: 20
        implicitHeight: 20
        radius: 10
        color: root.theme.surface
        border.color: root.activeFocus ? root.theme.accent
                      : root.pressed ? root.theme.accent
                                     : root.theme.separatorStrong
        border.width: root.activeFocus ? 2 : 1
    }
}
