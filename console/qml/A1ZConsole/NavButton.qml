import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Button {
    id: root

    required property var theme
    required property bool selected
    property string iconName: "activity"
    property bool routeEnabled: true
    property string blockedText: ""

    implicitHeight: 44
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.role: Accessible.PageTab
    Accessible.name: text
    Accessible.checked: root.selected

    contentItem: RowLayout {
        spacing: 10

        AppIcon {
            Layout.leftMargin: 12
            Layout.preferredWidth: 18
            Layout.preferredHeight: 18
            name: root.iconName
            color: !root.routeEnabled ? root.theme.tertiaryText
                                 : root.selected ? root.theme.accent
                                 : root.theme.secondaryText
        }

        Text {
            Layout.fillWidth: true
            text: root.text
            color: !root.routeEnabled ? root.theme.tertiaryText
                   : root.selected ? root.theme.text : root.theme.secondaryText
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeLabel
            font.weight: root.selected ? Font.DemiBold : Font.Medium
        }
    }

    background: Rectangle {
        radius: root.theme.radiusControl
        color: root.routeEnabled && root.selected ? root.theme.accentSoft
               : root.down ? root.theme.controlPressed
               : root.hovered ? root.theme.controlHover
               : "transparent"
        border.color: root.activeFocus ? root.theme.accent : "transparent"
        border.width: root.activeFocus ? 2 : 0
        Behavior on color {
            ColorAnimation { duration: root.theme.motionFast }
        }
    }

    AppToolTip {
        theme: root.theme
        visible: root.hovered && !root.routeEnabled
        text: root.blockedText
    }
}
