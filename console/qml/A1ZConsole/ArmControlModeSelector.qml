pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root

    required property var theme
    required property string controlMode
    property bool connected: false
    property bool interactive: false

    signal modeRequested(bool zeroGravityEnabled)

    readonly property bool positionHoldActive: controlMode === "position_hold"
    readonly property bool zeroGravityActive: controlMode === "gravity_comp_effort"
    readonly property bool modeKnown: positionHoldActive || zeroGravityActive

    implicitHeight: modeRow.implicitHeight

    component ModeButton: Button {
        id: modeButton

        required property var theme
        required property bool selected
        required property bool modeAvailable
        required property string title
        required property string detail
        required property string stateLabel

        Layout.fillWidth: true
        Layout.preferredHeight: 68
        padding: 10
        focusPolicy: Qt.StrongFocus
        hoverEnabled: true
        enabled: modeAvailable

        Accessible.role: Accessible.RadioButton
        Accessible.checked: selected
        Accessible.name: selected
                         ? qsTr("%1，当前模式").arg(title)
                         : qsTr("切换到%1").arg(title)
        Accessible.description: detail

        contentItem: RowLayout {
            spacing: 9

            Text {
                Layout.preferredWidth: 20
                text: modeButton.selected ? "✓" : "○"
                color: modeButton.selected
                       ? modeButton.theme.accent : modeButton.theme.tertiaryText
                horizontalAlignment: Text.AlignHCenter
                font.family: modeButton.theme.fontFamily
                font.pixelSize: modeButton.theme.typeTitle
                font.weight: Font.DemiBold
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

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
                    Layout.fillWidth: true
                    text: modeButton.detail
                    color: modeButton.selected
                           ? modeButton.theme.secondaryText
                           : modeButton.theme.tertiaryText
                    elide: Text.ElideRight
                    font.family: modeButton.theme.fontFamily
                    font.pixelSize: modeButton.theme.typeCaption
                }
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
            color: modeButton.selected ? modeButton.theme.accentSoft
                   : !modeButton.enabled ? modeButton.theme.tile
                   : modeButton.down ? modeButton.theme.controlPressed
                   : modeButton.hovered ? modeButton.theme.controlHover
                                        : modeButton.theme.tile
            border.color: modeButton.activeFocus ? modeButton.theme.text
                          : modeButton.selected ? modeButton.theme.accent
                                                : modeButton.theme.borderStrong
            border.width: modeButton.activeFocus || modeButton.selected ? 2 : 1
        }
    }

    RowLayout {
        id: modeRow
        anchors.fill: parent
        spacing: 8

        ModeButton {
            theme: root.theme
            title: qsTr("位置保持")
            detail: qsTr("锁定当前姿态")
            selected: root.positionHoldActive
            modeAvailable: root.interactive && root.modeKnown
            stateLabel: selected ? qsTr("当前")
                        : !root.connected ? qsTr("未连接")
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
            stateLabel: selected ? qsTr("当前")
                        : !root.connected ? qsTr("未连接")
                        : root.modeKnown ? qsTr("切换") : qsTr("状态未知")
            onClicked: {
                if (!selected)
                    root.modeRequested(true)
            }
        }
    }
}
