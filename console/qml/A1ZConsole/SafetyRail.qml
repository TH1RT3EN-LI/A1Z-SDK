pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

GlassCard {
    id: root
    objectName: "safetyRail"

    required property var controller
    property alias speed: speedSlider.value
    property alias jointStep: jointStepBox.value
    property alias linearStepMm: linearStepBox.value
    property alias angularStepDeg: angularStepBox.value
    property string frameMode: "base"
    property bool showMotionSettings: true
    property bool armDraftPending: false
    property bool gripperDraftPending: false
    property bool configurationDraftPending: false
    readonly property bool recoveryChangesControlState:
        root.controller.motionRecoveryAction.length > 0
        && root.controller.motionRecoveryAction !== "refresh"
    readonly property bool recoveryDraftPending: {
        const action = root.controller.motionRecoveryAction
        if (action === "start_server" || action === "restart_server")
            return root.armDraftPending
                    || root.gripperDraftPending
                    || root.configurationDraftPending
        if (action === "position_hold")
            return root.armDraftPending
        return false
    }
    property string settingsProfile: ""
    signal frameModeRequested(string mode)

    function synchronizeProfileDefaults() {
        if (root.settingsProfile === root.controller.profile)
            return

        root.settingsProfile = root.controller.profile
        speedSlider.value = root.controller.manualMotionDefaultSpeed
        jointStepBox.value = Math.round(
                    root.controller.manualMotionDefaultJointStepDeg * 10)
        linearStepBox.value = root.controller.manualMotionDefaultLinearStepMm
        angularStepBox.value = Math.round(
                    root.controller.manualMotionDefaultAngularStepDeg * 10)
        root.frameModeRequested("base")
    }

    padding: theme.spacingL

    ColumnLayout {
        anchors.fill: parent
        spacing: root.theme.spacingM

        PageScrollView {
            id: motionSettingsScroll

            Layout.fillWidth: true
            Layout.fillHeight: true
            ColumnLayout {
                width: motionSettingsScroll.availableWidth
                spacing: root.theme.spacingM

                SectionHeader {
                    Layout.fillWidth: true
                    visible: root.showMotionSettings
                    theme: root.theme
                    title: qsTr("机械臂位置运动")
                }

                Rectangle {
                    Layout.fillWidth: true
                    visible: root.showMotionSettings
                    Layout.preferredHeight: gateColumn.implicitHeight + 26
                    radius: root.theme.radiusControl
                    color: root.controller.motionEnabled ? root.theme.greenSoft
                           : root.controller.commandOutcomeUncertain ? root.theme.redSoft
                           : root.theme.orangeSoft

                    ColumnLayout {
                        id: gateColumn

                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 13
                        spacing: 4

                        Text {
                            Layout.fillWidth: true
                            text: root.controller.motionEnabled
                                  ? qsTr("机械臂位置运动已就绪")
                                  : qsTr("机械臂位置运动已锁定")
                            color: root.controller.motionEnabled ? root.theme.green
                                   : root.controller.commandOutcomeUncertain
                                     ? root.theme.red : root.theme.orange
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                            font.weight: Font.DemiBold
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: !root.controller.motionEnabled
                            text: root.controller.motionGateText
                            color: root.theme.text
                            wrapMode: Text.WordWrap
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeLabel
                        }
                    }
                }

                AppButton {
                    Layout.fillWidth: true
                    visible: root.controller.commandOutcomeUncertain
                    theme: root.theme
                    kind: "danger"
                    text: root.controller.uncertainRecoveryPending
                          ? qsTr("等待遥测（点击重试）")
                          : qsTr("现场确认后重新核验")
                    onClicked: root.controller.acknowledgeUncertain()
                }

                AppButton {
                    Layout.fillWidth: true
                    visible: root.showMotionSettings
                             && root.controller.motionRecoveryAction.length > 0
                    theme: root.theme
                    kind: "primary"
                    text: root.recoveryDraftPending
                          && root.recoveryChangesControlState
                          ? qsTr("先处理未发送的控制草稿")
                          : root.controller.motionRecoveryLabel
                    enabled: !root.controller.commandBusy
                             && !root.controller.taskBusy
                             && !(root.recoveryDraftPending
                                  && root.recoveryChangesControlState)
                    onClicked: root.controller.runMotionRecovery()
                }

                Rectangle {
                    Layout.fillWidth: true
                    visible: root.showMotionSettings
                    Layout.preferredHeight: 1
                    color: root.theme.border
                }

                Text {
                    visible: root.showMotionSettings
                    text: qsTr("关节速度  %1 rad/s").arg(
                              speedSlider.value.toFixed(2))
                    color: root.theme.secondaryText
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeLabel
                }

                AppSlider {
                    id: speedSlider

                    Layout.fillWidth: true
                    visible: root.showMotionSettings
                    theme: root.theme
                    from: 0.05
                    to: 1.5
                    value: 0.5
                    stepSize: 0.05
                    snapMode: Slider.SnapAlways
                    Accessible.name: qsTr("关节速度")
                }

                GridLayout {
                    Layout.fillWidth: true
                    visible: root.showMotionSettings
                    columns: 2
                    columnSpacing: 10
                    rowSpacing: 8

                    Text {
                        text: qsTr("关节点动")
                        color: root.theme.secondaryText
                        font.family: root.theme.fontFamily
                        font.pixelSize: root.theme.typeCaption
                    }

                    AppSpinBox {
                        id: jointStepBox

                        Layout.fillWidth: true
                        theme: root.theme
                        from: 1
                        to: 200
                        value: 20
                        stepSize: 1
                        editable: true
                        Accessible.name: qsTr("关节点动步长")
                        textFromValue: function(value) {
                            return (value / 10).toFixed(1) + "°"
                        }
                        valueFromText: function(text) {
                            return Math.round(parseFloat(text) * 10)
                        }
                    }

                    Text {
                        text: qsTr("直线步长")
                        color: root.theme.secondaryText
                        font.family: root.theme.fontFamily
                        font.pixelSize: root.theme.typeCaption
                    }

                    AppSpinBox {
                        id: linearStepBox

                        Layout.fillWidth: true
                        theme: root.theme
                        from: 1
                        to: 100
                        value: 10
                        editable: true
                        Accessible.name: qsTr("直线点动步长")
                        textFromValue: function(value) {
                            return value + " mm"
                        }
                        valueFromText: function(text) {
                            return Math.round(parseFloat(text))
                        }
                    }

                    Text {
                        text: qsTr("转角步长")
                        color: root.theme.secondaryText
                        font.family: root.theme.fontFamily
                        font.pixelSize: root.theme.typeCaption
                    }

                    AppSpinBox {
                        id: angularStepBox

                        Layout.fillWidth: true
                        theme: root.theme
                        from: 1
                        to: 450
                        value: 50
                        editable: true
                        Accessible.name: qsTr("旋转点动步长")
                        textFromValue: function(value) {
                            return (value / 10).toFixed(1) + "°"
                        }
                        valueFromText: function(text) {
                            return Math.round(parseFloat(text) * 10)
                        }
                    }
                }

                Text {
                    visible: root.showMotionSettings
                    text: qsTr("增量坐标系")
                    color: root.theme.secondaryText
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeCaption
                }

                Rectangle {
                    Layout.fillWidth: true
                    visible: root.showMotionSettings
                    Layout.preferredHeight: 40
                    radius: root.theme.radiusControl + 2
                    color: root.theme.control

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 3
                        spacing: 3

                        AppButton {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            theme: root.theme
                            kind: root.frameMode === "base"
                                  ? "selected" : "quiet"
                            text: qsTr("基座 Base")
                            Accessible.role: Accessible.RadioButton
                            Accessible.checked: root.frameMode === "base"
                            onClicked: root.frameModeRequested("base")
                        }

                        AppButton {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            theme: root.theme
                            kind: root.frameMode === "tool"
                                  ? "selected" : "quiet"
                            text: qsTr("工具 TCP")
                            Accessible.role: Accessible.RadioButton
                            Accessible.checked: root.frameMode === "tool"
                            onClicked: root.frameModeRequested("tool")
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: estopColumn.implicitHeight + 24
            radius: root.theme.radiusControl
            color: root.theme.control
            border.width: 0

            ColumnLayout {
                id: estopColumn
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    Layout.fillWidth: true
                    text: root.controller.estopped ? qsTr("软急停已锁定") : qsTr("软件紧急停止")
                    color: root.controller.estopped ? root.theme.red
                           : root.theme.secondaryText
                    horizontalAlignment: Text.AlignHCenter
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeLabel
                    font.weight: Font.DemiBold
                }

                AppButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                    theme: root.theme
                    kind: "danger"
                    text: root.controller.estopped ? qsTr("解除软急停") : qsTr("立即软急停")
                    enabled: root.controller.estopped
                             ? root.controller.estopReleaseEnabled
                             : root.controller.connected
                               && !root.controller.emergencyBusy
                    onClicked: {
                        if (root.controller.estopped)
                            root.controller.releaseEmergencyStop()
                        else
                            root.controller.emergencyStop()
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: qsTr("软件急停不能替代现场硬件急停")
            color: root.theme.tertiaryText
            horizontalAlignment: Text.AlignHCenter
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
        }
    }

    Connections {
        target: root.controller

        function onStateChanged() {
            root.synchronizeProfileDefaults()
        }
    }

    Component.onCompleted: synchronizeProfileDefaults()
}
