pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root

    required property var theme
    required property var controller
    property real motionSpeed: 0.5

    ScrollView {
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: root.width
            spacing: root.theme.spacingM

            SectionHeader {
                Layout.fillWidth: true
                theme: root.theme
                title: qsTr("官方 SDK 功能中心")
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: root.theme.spacingM
                rowSpacing: root.theme.spacingM

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 145
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("SDK 控制服务")
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                kind: "primary"
                                text: qsTr("启动服务")
                                enabled: !root.controller.taskBusy && !root.controller.connected
                                onClicked: root.controller.startServer(false)
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                kind: "danger"
                                text: qsTr("停止服务")
                                enabled: root.controller.connected && !root.controller.commandBusy
                                onClicked: root.controller.stopServer()
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: root.controller.endpoint
                            color: root.theme.tertiaryText
                            elide: Text.ElideRight
                            font.family: "monospace"
                            font.pixelSize: root.theme.typeCaption
                        }
                    }
                }

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 145
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("控制模式")
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                kind: "success"
                                text: qsTr("零力漂浮")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.setGravityMode(true)
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                kind: "primary"
                                text: qsTr("位置保持")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.setGravityMode(false)
                            }
                        }

                    }
                }
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 240
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("关节预置位")
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 8

                        Repeater {
                            model: ["home", "ready", "reach", "salute", "wave_l",
                                    "wave_r", "nod_a", "nod_b", "shake_a",
                                    "shake_b", "bow"]
                            AppButton {
                                required property string modelData
                                theme: root.theme
                                text: modelData
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.movePreset(modelData, root.motionSpeed)
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            text: qsTr("动作序列")
                            color: root.theme.orange
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                        }
                        Item { Layout.fillWidth: true }
                        Repeater {
                            model: ["salute", "wave", "nod", "shake", "reach", "bow", "all"]
                            AppButton {
                                required property string modelData
                                theme: root.theme
                                text: modelData
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.runDance(modelData, root.motionSpeed)
                            }
                        }
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: root.theme.spacingM
                rowSpacing: root.theme.spacingM

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 300
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("零力示教与回放")
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: qsTr("采样率")
                                color: root.theme.secondaryText
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeLabel
                            }
                            SpinBox {
                                id: sampleHz
                                from: 1
                                to: 250
                                value: 50
                                editable: true
                            }
                            TextField {
                                id: recordingName
                                Layout.fillWidth: true
                                text: "teach.json"
                                placeholderText: qsTr("轨迹文件名")
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                kind: "success"
                                text: qsTr("进入零力并开始录制")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.startRecording(sampleHz.value)
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                text: qsTr("停止并保存")
                                enabled: root.controller.connected && !root.controller.commandBusy
                                onClicked: root.controller.stopRecording(recordingName.text)
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: qsTr("回放倍率")
                                color: root.theme.secondaryText
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeLabel
                            }
                            SpinBox {
                                id: playbackSpeed
                                from: 1
                                to: 30
                                value: 10
                                textFromValue: function(value) {
                                    return (value / 10).toFixed(1) + "×"
                                }
                                valueFromText: function(text) {
                                    return Math.round(parseFloat(text) * 10)
                                }
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                kind: "primary"
                                text: qsTr("回放一次")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.playRecording(
                                               recordingName.text,
                                               playbackSpeed.value / 10)
                            }
                        }
                    }
                }

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 240
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("G1Z 与 D405")
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            StatusPill {
                                theme: root.theme
                                text: root.controller.gripperFreeDrive
                                      ? qsTr("自由拖动：开")
                                      : qsTr("自由拖动：关")
                                level: root.controller.gripperFreeDrive ? "warn" : "ok"
                            }

                            Item { Layout.fillWidth: true }

                            AppButton {
                                theme: root.theme
                                text: root.controller.gripperFreeDrive
                                      ? qsTr("恢复夹爪控制")
                                      : qsTr("启用自由拖动")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.setGripperFreeDrive(
                                               !root.controller.gripperFreeDrive)
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                text: qsTr("相机状态")
                                enabled: root.controller.connected && !root.controller.commandBusy
                                onClicked: root.controller.queryCamera("camera_status")
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                kind: "primary"
                                text: qsTr("采集一帧")
                                enabled: root.controller.connected && !root.controller.commandBusy
                                onClicked: root.controller.queryCamera("camera_capture")
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                text: qsTr("读取外参")
                                enabled: root.controller.connected && !root.controller.commandBusy
                                onClicked: root.controller.queryCamera("camera_extrinsic")
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: root.controller.cameraSummary
                            color: root.theme.tertiaryText
                            elide: Text.ElideRight
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                        }
                    }
                }
            }

        }
    }
}
