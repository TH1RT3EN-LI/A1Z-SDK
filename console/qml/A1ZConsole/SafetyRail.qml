pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

GlassCard {
    id: root

    required property var controller
    property alias speed: speedSlider.value
    property alias jointStep: jointStepBox.value
    property alias linearStepMm: linearStepBox.value
    property alias angularStepDeg: angularStepBox.value
    property string frameMode: "base"
    signal frameModeRequested(string mode)

    padding: theme.spacingL

    ColumnLayout {
        anchors.fill: parent
        spacing: root.theme.spacingM

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("运动互锁")
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: gateColumn.implicitHeight + 26
            radius: root.theme.radiusControl
            color: root.controller.motionEnabled ? root.theme.greenSoft
                   : root.controller.commandOutcomeUncertain ? root.theme.redSoft
                   : root.theme.orangeSoft
            border.color: root.controller.motionEnabled ? root.theme.green
                          : root.controller.commandOutcomeUncertain ? root.theme.red
                          : root.theme.orange

            ColumnLayout {
                id: gateColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.margins: 13
                spacing: 4

                Text {
                    Layout.fillWidth: true
                    text: root.controller.motionEnabled ? qsTr("MOTION READY")
                                                : qsTr("MOTION LOCKED")
                    color: root.controller.motionEnabled ? root.theme.green
                           : root.controller.commandOutcomeUncertain ? root.theme.red
                           : root.theme.orange
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeCaption
                    font.weight: Font.Bold
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
            text: qsTr("现场确认后解除不确定锁")
            onClicked: root.controller.acknowledgeUncertain()
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: root.theme.border
        }

        Text {
            text: qsTr("关节速度  %1 rad/s").arg(speedSlider.value.toFixed(2))
            color: root.theme.secondaryText
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeLabel
        }

        Slider {
            id: speedSlider
            Layout.fillWidth: true
            from: 0.05
            to: 1.5
            value: 0.5
            stepSize: 0.05
            snapMode: Slider.SnapAlways

            background: Rectangle {
                x: speedSlider.leftPadding
                y: speedSlider.topPadding + speedSlider.availableHeight / 2 - height / 2
                width: speedSlider.availableWidth
                height: 5
                radius: 3
                color: root.theme.control

                Rectangle {
                    width: speedSlider.visualPosition * parent.width
                    height: parent.height
                    radius: parent.radius
                    color: root.theme.accent
                }
            }

            handle: Rectangle {
                x: speedSlider.leftPadding + speedSlider.visualPosition
                   * (speedSlider.availableWidth - width)
                y: speedSlider.topPadding + speedSlider.availableHeight / 2 - height / 2
                implicitWidth: 18
                implicitHeight: 18
                radius: 9
                color: speedSlider.pressed ? root.theme.accent : root.theme.text
                border.color: root.theme.accent
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 10
            rowSpacing: 8

            Text {
                text: qsTr("关节点动")
                color: root.theme.secondaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }
            SpinBox {
                id: jointStepBox
                Layout.fillWidth: true
                from: 1
                to: 200
                value: 20
                stepSize: 1
                editable: true
                textFromValue: function(value) { return (value / 10).toFixed(1) + "°" }
                valueFromText: function(text) { return Math.round(parseFloat(text) * 10) }
            }

            Text {
                text: qsTr("直线步长")
                color: root.theme.secondaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }
            SpinBox {
                id: linearStepBox
                Layout.fillWidth: true
                from: 1
                to: 100
                value: 10
                editable: true
                textFromValue: function(value) { return value + " mm" }
                valueFromText: function(text) { return Math.round(parseFloat(text)) }
            }

            Text {
                text: qsTr("转角步长")
                color: root.theme.secondaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }
            SpinBox {
                id: angularStepBox
                Layout.fillWidth: true
                from: 1
                to: 450
                value: 50
                editable: true
                textFromValue: function(value) { return (value / 10).toFixed(1) + "°" }
                valueFromText: function(text) { return Math.round(parseFloat(text) * 10) }
            }
        }

        Text {
            text: qsTr("增量坐标系")
            color: root.theme.secondaryText
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            AppButton {
                Layout.fillWidth: true
                theme: root.theme
                kind: root.frameMode === "base" ? "primary" : "secondary"
                text: qsTr("Base")
                onClicked: root.frameModeRequested("base")
            }
            AppButton {
                Layout.fillWidth: true
                theme: root.theme
                kind: root.frameMode === "tool" ? "primary" : "secondary"
                text: qsTr("Tool")
                onClicked: root.frameModeRequested("tool")
            }
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: estopColumn.implicitHeight + 24
            radius: root.theme.radiusControl
            color: root.theme.redSoft
            border.color: root.theme.red

            ColumnLayout {
                id: estopColumn
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    Layout.fillWidth: true
                    text: root.controller.estopped ? qsTr("软急停已锁定") : qsTr("软件紧急停止")
                    color: root.theme.red
                    horizontalAlignment: Text.AlignHCenter
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeLabel
                    font.weight: Font.Bold
                }

                AppButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                    theme: root.theme
                    kind: "danger"
                    text: root.controller.estopped ? qsTr("解除软急停") : qsTr("立即软急停")
                    enabled: root.controller.connected && !root.controller.emergencyBusy
                             && (!root.controller.estopped || (!root.controller.commandBusy && !root.controller.taskBusy))
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
            text: qsTr("硬件急停优先")
            color: root.theme.tertiaryText
            horizontalAlignment: Text.AlignHCenter
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
        }
    }
}
