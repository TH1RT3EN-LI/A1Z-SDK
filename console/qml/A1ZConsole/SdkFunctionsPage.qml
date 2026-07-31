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
                subtitle: qsTr("控制服务、重力补偿、预置动作、示教回放与 G1Z 夹爪")
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: root.theme.spacingM
                rowSpacing: root.theme.spacingM

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 270
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
                                text: qsTr("启动并保持当前位置")
                                enabled: !root.controller.taskBusy && !root.controller.connected
                                onClicked: root.controller.startServer(
                                               false, gravityFactor.value)
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
                            text: qsTr("端点  %1").arg(root.controller.endpoint)
                            color: root.theme.tertiaryText
                            elide: Text.ElideRight
                            font.family: "monospace"
                            font.pixelSize: root.theme.typeCaption
                        }

                        Text {
                            Layout.fillWidth: true
                            text: qsTr("服务是 SDK 与 CAN 的唯一所有者；启动默认使用位置保持，连接后再进入零力模式。")
                            color: root.theme.secondaryText
                            wrapMode: Text.WordWrap
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                        }
                    }
                }

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 270
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("机械臂控制模式（二选一）")
                            subtitle: qsTr("当前状态由机械臂 SDK 持续维护并回读")
                        }

                        ArmControlModeSelector {
                            Layout.fillWidth: true
                            theme: root.theme
                            connected: root.controller.connected
                            interactive: root.controller.motionEnabled
                            controlMode: root.controller.controlMode
                            onModeRequested: function(zeroGravityEnabled) {
                                root.controller.setGravityMode(
                                            zeroGravityEnabled,
                                            gravityFactor.value)
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            Text {
                                text: qsTr("重力补偿系数")
                                color: root.theme.secondaryText
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeLabel
                            }

                            Slider {
                                id: gravityFactor
                                Layout.fillWidth: true
                                from: 0.0
                                to: 1.0
                                stepSize: 0.05
                                value: root.controller.connected
                                       ? root.controller.gravityCompFactor : 0.3
                                snapMode: Slider.SnapAlways
                                Accessible.name: qsTr("重力补偿系数")
                            }

                            Text {
                                Layout.preferredWidth: 46
                                text: gravityFactor.value.toFixed(2)
                                color: root.theme.text
                                horizontalAlignment: Text.AlignRight
                                font.family: "monospace"
                                font.pixelSize: root.theme.typeLabel
                                font.weight: Font.DemiBold
                            }

                            AppButton {
                                theme: root.theme
                                text: qsTr("应用系数")
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.setGravityFactor(
                                               gravityFactor.value)
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: qsTr("SDK 参数 · %1")
                                  .arg(root.controller.sdkDynamicsSummary)
                            color: root.theme.tertiaryText
                            elide: Text.ElideRight
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                            ToolTip.visible: dynamicsHover.hovered && truncated
                            ToolTip.text: text
                            HoverHandler { id: dynamicsHover }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: qsTr("当前补偿回读 %1。零力漂浮仍会输出重力补偿，并非断电；真机首次拖动建议从 0.30 起。")
                                  .arg(root.controller.gravityCompFactor.toFixed(2))
                            color: root.theme.tertiaryText
                            wrapMode: Text.WordWrap
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                        }
                    }
                }
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: root.width < 900 ? 330 : 240
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("关节预置位")
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: root.width < 900 ? 4 : 6
                        columnSpacing: 8
                        rowSpacing: 8

                        Repeater {
                            model: [
                                { label: qsTr("归位"), value: "home" },
                                { label: qsTr("准备"), value: "ready" },
                                { label: qsTr("前伸"), value: "reach" },
                                { label: qsTr("致意"), value: "salute" },
                                { label: qsTr("左挥"), value: "wave_l" },
                                { label: qsTr("右挥"), value: "wave_r" },
                                { label: qsTr("点头起"), value: "nod_a" },
                                { label: qsTr("点头落"), value: "nod_b" },
                                { label: qsTr("摇头左"), value: "shake_a" },
                                { label: qsTr("摇头右"), value: "shake_b" },
                                { label: qsTr("鞠躬"), value: "bow" }
                            ]
                            AppButton {
                                required property var modelData
                                Layout.fillWidth: true
                                theme: root.theme
                                text: modelData.label
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.movePreset(modelData.value,
                                                                      root.motionSpeed)
                            }
                        }
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: root.width < 900 ? 4 : 8
                        columnSpacing: 8
                        rowSpacing: 8

                        Text {
                            text: qsTr("动作序列")
                            color: root.theme.orange
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                        }
                        Repeater {
                            model: [
                                { label: qsTr("致意"), value: "salute" },
                                { label: qsTr("挥手"), value: "wave" },
                                { label: qsTr("点头"), value: "nod" },
                                { label: qsTr("摇头"), value: "shake" },
                                { label: qsTr("前伸"), value: "reach" },
                                { label: qsTr("鞠躬"), value: "bow" },
                                { label: qsTr("完整序列"), value: "all" }
                            ]
                            AppButton {
                                required property var modelData
                                Layout.fillWidth: true
                                theme: root.theme
                                text: modelData.label
                                enabled: root.controller.motionEnabled
                                onClicked: root.controller.runDance(modelData.value,
                                                                    root.motionSpeed)
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
                    Layout.preferredHeight: 180
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("G1Z 夹爪")
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
                    }
                }
            }

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 430
                theme: root.theme

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    SectionHeader {
                        Layout.fillWidth: true
                        theme: root.theme
                        title: qsTr("ROS RGB-D 相机")
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 12

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumWidth: 520
                            radius: root.theme.radiusControl
                            color: "#FF0B0E13"
                            border.color: root.controller.cameraReady
                                          ? root.theme.cyan : root.theme.border
                            border.width: 1
                            clip: true

                            Image {
                                id: cameraPreview
                                objectName: "sdkCameraPreview"
                                readonly property int loadStatus: status
                                anchors.fill: parent
                                anchors.margins: 8
                                source: root.visible
                                        ? root.controller.cameraPreviewSource : ""
                                sourceSize.width: Math.min(
                                                      960,
                                                      Math.max(1, Math.ceil(width)))
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                                cache: false
                                retainWhileLoading: true
                                smooth: true
                                visible: root.controller.cameraPreviewSource.length > 0
                            }

                            Column {
                                anchors.centerIn: parent
                                spacing: 8
                                visible: root.controller.cameraPreviewSource.length === 0

                                BusyIndicator {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    running: root.controller.cameraBusy
                                    visible: running
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: root.controller.cameraBusy
                                          ? qsTr("正在读取 RGB-D 帧…")
                                          : qsTr("等待 ROS RGB-D 数据")
                                    color: root.theme.tertiaryText
                                    font.family: root.theme.fontFamily
                                    font.pixelSize: root.theme.typeBody
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.preferredWidth: 390
                            Layout.fillHeight: true
                            spacing: 10

                            StatusPill {
                                theme: root.theme
                                text: root.controller.cameraSummary
                                level: root.controller.cameraReady ? "ok" : "warn"
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                AppButton {
                                    Layout.fillWidth: true
                                    theme: root.theme
                                    text: qsTr("链路状态")
                                    enabled: !root.controller.cameraBusy
                                    onClicked: root.controller.queryCamera("camera_status")
                                }
                                AppButton {
                                    Layout.fillWidth: true
                                    theme: root.theme
                                    kind: "primary"
                                    text: qsTr("刷新画面")
                                    enabled: !root.controller.cameraBusy
                                    onClicked: root.controller.queryCamera("camera_capture")
                                }
                            }

                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                text: qsTr("读取相机外参")
                                enabled: !root.controller.cameraBusy
                                onClicked: root.controller.queryCamera("camera_extrinsic")
                            }

                            Text {
                                Layout.fillWidth: true
                                text: root.controller.cameraDetails
                                color: root.theme.secondaryText
                                wrapMode: Text.Wrap
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeCaption
                            }

                            Text {
                                Layout.fillWidth: true
                                text: qsTr("画面来自配置选定的 ROS 主题；GUI 不直接占用 USB，也不依赖 /dev/video 编号。")
                                color: root.theme.tertiaryText
                                wrapMode: Text.Wrap
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeCaption
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }

        }
    }
}
