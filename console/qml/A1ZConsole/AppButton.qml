import QtQuick
import QtQuick.Controls.Basic

Button {
    id: root

    required property var theme
    property string kind: "secondary"
    property color customColor: "transparent"

    implicitHeight: 40
    implicitWidth: 104
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    autoRepeat: false

    readonly property bool prominent: kind === "primary" || kind === "danger"
    readonly property color baseColor: customColor.a > 0 ? customColor
                                       : kind === "primary" ? theme.accentFill
                                       : kind === "danger" ? theme.redFill
                                       : kind === "quiet" ? "transparent"
                                       : kind === "selected" ? theme.accentSoft
                                       : theme.control
    readonly property color foreground: kind === "primary" || kind === "danger"
                                        ? theme.textOnAccent
                                        : kind === "selected" ? theme.accent
                                        : theme.text

    contentItem: Text {
        text: root.text
        color: root.enabled ? root.foreground
               : root.kind === "danger" ? root.theme.red
                                        : root.theme.tertiaryText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        font.family: root.theme.fontFamily
        font.pixelSize: root.theme.typeLabel
        font.weight: root.prominent ? Font.DemiBold : Font.Medium
    }

    background: Rectangle {
        radius: root.theme.radiusControl
        color: !root.enabled ? (root.kind === "danger"
                                ? root.theme.redSoft
                                : root.kind === "quiet"
                                  ? "transparent" : root.theme.control)
               : root.down ? (root.kind === "quiet"
                               ? root.theme.controlPressed
                               : Qt.darker(root.baseColor, 1.08))
               : root.hovered ? (root.kind === "quiet"
                                  ? root.theme.controlHover
                                  : root.prominent
                                    ? Qt.darker(root.baseColor, 1.04)
                                    : root.theme.controlHover)
               : root.baseColor
        border.color: root.activeFocus ? root.theme.accent
                      : "transparent"
        border.width: root.activeFocus ? 2 : 0
        Behavior on color {
            ColorAnimation { duration: root.theme.motionFast }
        }
    }

    Accessible.name: text
}
