pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root

    required property var theme
    required property string controlMode
    property bool interactive: false
    property string confirmationState: "unconfirmed"
    readonly property bool stateConfirmed:
        root.confirmationState === "confirmed"

    signal modeRequested(bool zeroGravityEnabled)

    readonly property bool positionHoldActive: controlMode === "position_hold"
    readonly property bool zeroGravityActive: controlMode === "gravity_comp_effort"
    readonly property bool modeKnown: positionHoldActive || zeroGravityActive

    implicitHeight: 60

    Rectangle {
        anchors.fill: parent
        radius: root.theme.radiusControl + 2
        color: root.theme.control
    }

    component ModeButton: Button {
        id: modeButton

        required property var theme
        required property bool selected
        required property bool modeAvailable
        required property string title
        required property string detail
        required property string stateLabel

        Layout.fillWidth: true
        Layout.preferredHeight: 54
        padding: 10
        focusPolicy: Qt.StrongFocus
        hoverEnabled: true
        enabled: modeAvailable

        Accessible.role: Accessible.RadioButton
        Accessible.checked: selected
        Accessible.name: selected
                         ? qsTr("%1，%2").arg(title).arg(stateLabel)
                         : qsTr("切换到%1").arg(title)
        Accessible.description: detail

        contentItem: RowLayout {
            spacing: 9

            Rectangle {
                Layout.preferredWidth: 16
                Layout.preferredHeight: 16
                radius: 8
                color: "transparent"
                border.color: modeButton.selected
                              ? modeButton.theme.accent
                              : modeButton.theme.placeholderText
                border.width: 1.5

                Rectangle {
                    anchors.centerIn: parent
                    width: 8
                    height: 8
                    radius: 4
                    visible: modeButton.selected
                    color: modeButton.theme.accent
                }
            }

            Text {
                Layout.fillWidth: true
                text: modeButton.title
                color: modeButton.theme.text
                elide: Text.ElideRight
                font.family: modeButton.theme.fontFamily
                font.pixelSize: modeButton.theme.typeLabel
                font.weight: Font.DemiBold
            }

            Text {
                text: modeButton.stateLabel
                color: modeButton.selected
                       ? modeButton.theme.accent : modeButton.theme.secondaryText
                font.family: modeButton.theme.fontFamily
                font.pixelSize: modeButton.theme.typeCaption
                font.weight: Font.DemiBold
            }
        }

        background: Rectangle {
            radius: modeButton.theme.radiusControl
            color: modeButton.selected ? modeButton.theme.surface
                   : !modeButton.enabled ? "transparent"
                   : modeButton.down ? modeButton.theme.controlPressed
                   : modeButton.hovered ? modeButton.theme.controlHover
                                        : "transparent"
            border.color: modeButton.activeFocus
                          ? modeButton.theme.accent : "transparent"
            border.width: modeButton.activeFocus ? 2 : 0
            Behavior on color {
                ColorAnimation { duration: modeButton.theme.motionFast }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 3
        spacing: 3

        ModeButton {
            theme: root.theme
            title: qsTr("位置保持")
            detail: qsTr("锁定当前姿态")
            selected: root.positionHoldActive
            modeAvailable: root.interactive && root.modeKnown
            stateLabel: root.confirmationState === "pending" ? qsTr("切换中")
                        : root.confirmationState === "uncertain"
                          ? qsTr("结果不确定")
                        : selected && root.stateConfirmed ? qsTr("当前")
                        : selected ? qsTr("最后显示")
                        : !root.stateConfirmed ? qsTr("未确认")
                        : root.modeKnown ? qsTr("切换") : qsTr("状态未知")
            onClicked: {
                if (!selected)
                    root.modeRequested(false)
            }
        }

        ModeButton {
            theme: root.theme
            title: qsTr("零力漂浮")
            detail: qsTr("重力补偿，可手动拖动")
            selected: root.zeroGravityActive
            modeAvailable: root.interactive && root.modeKnown
            stateLabel: root.confirmationState === "pending" ? qsTr("切换中")
                        : root.confirmationState === "uncertain"
                          ? qsTr("结果不确定")
                        : selected && root.stateConfirmed ? qsTr("当前")
                        : selected ? qsTr("最后显示")
                        : !root.stateConfirmed ? qsTr("未确认")
                        : root.modeKnown ? qsTr("切换") : qsTr("状态未知")
            onClicked: {
                if (!selected)
                    root.modeRequested(true)
            }
        }
    }
}
