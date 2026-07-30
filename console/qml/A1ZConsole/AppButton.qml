import QtQuick
import QtQuick.Controls.Basic

Button {
    id: root

    required property var theme
    property string kind: "secondary"
    property color customColor: "transparent"

    implicitHeight: 38
    implicitWidth: 104
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    autoRepeat: false

    readonly property color baseColor: customColor.a > 0 ? customColor
                                       : kind === "primary" ? theme.accent
                                       : kind === "danger" ? theme.red
                                       : kind === "success" ? theme.green
                                       : theme.control
    readonly property color foreground: kind === "secondary"
                                        ? theme.text : "#FFFFFFFF"

    contentItem: Text {
        text: root.text
        color: root.enabled ? root.foreground : root.theme.tertiaryText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        font.family: root.theme.fontFamily
        font.pixelSize: root.theme.typeLabel
        font.weight: Font.DemiBold
    }

    background: Rectangle {
        radius: root.theme.radiusControl
        color: !root.enabled ? root.theme.tile
               : root.down ? Qt.darker(root.baseColor, 1.18)
               : root.hovered ? Qt.lighter(root.baseColor, 1.10)
               : root.baseColor
        border.color: root.activeFocus ? root.theme.accent
                      : root.kind === "secondary" ? root.theme.borderStrong
                                                  : "transparent"
        border.width: root.activeFocus ? 2 : 1
        Behavior on color { ColorAnimation { duration: 90 } }
    }

    Accessible.name: text
}
