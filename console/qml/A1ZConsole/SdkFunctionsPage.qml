pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: root

    required property var theme
    required property var controller
    property real motionSpeed: 0.5
    property real gravityFactorDraft: 0.3
    property bool gravityFactorDirty: false

    function synchronizeGravityFactorDraft() {
        if (gravityFactor.pressed)
            return

        const liveFactor = root.controller.connected
                         ? root.controller.gravityCompFactor : 0.3
        if (!root.gravityFactorDirty
                || Math.abs(root.gravityFactorDraft - liveFactor) < 0.001) {
            root.gravityFactorDraft = liveFactor
            gravityFactor.value = liveFactor
            root.gravityFactorDirty = false
        }
    }

    Component.onCompleted: synchronizeGravityFactorDraft()

    Connections {
        target: root.controller

        function onStateChanged() {
            root.synchronizeGravityFactorDraft()
        }
    }

    ScrollView {
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: root.width
            spacing: root.theme.spacingM

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: root.theme.spacingM
                rowSpacing: root.theme.spacingM

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 205
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        Text {
                            Layout.fillWidth: true
                            text: qsTr("控制服务")
                            color: root.theme.text
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeTitle
                            font.weight: Font.DemiBold
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
                                onClicked: root.controller.startServer(
                                               false, root.gravityFactorDraft)
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
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

                    }
                }

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 205
                    theme: root.theme

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        SectionHeader {
                            Layout.fillWidth: true
                            theme: root.theme
                            title: qsTr("控制模式")
                        }

                        ArmControlModeSelector {
                            Layout.fillWidth: true
                            theme: root.theme
                            connected: root.controller.connected
                            interactive: root.controller.modeControlEnabled
                            controlMode: root.controller.controlMode
                            onModeRequested: function(zeroGravityEnabled) {
                                root.controller.setGravityMode(zeroGravityEnabled)
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            Text {
                                text: qsTr("补偿系数")
                                color: root.theme.secondaryText
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeLabel
                            }

                            AppSlider {
                                id: gravityFactor
                                objectName: "gravityFactor"
                                Layout.fillWidth: true
                                theme: root.theme
                                from: 0.0
                                to: 1.0
                                stepSize: 0.05
                                value: 0.3
                                snapMode: Slider.SnapAlways
                                enabled: !root.controller.commandBusy
                                         && !root.controller.taskBusy
                                onMoved: {
                                    root.gravityFactorDraft = value
                                    root.gravityFactorDirty = true
                                }
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
                                text: root.controller.connected
                                      ? qsTr("重启应用") : qsTr("启动应用")
                                enabled: root.gravityFactorDirty
                                         && !root.controller.commandBusy
                                         && !root.controller.taskBusy
                                onClicked: root.controller.setGravityFactor(
                                               root.gravityFactorDraft)
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: qsTr("系数不热切换；应用会重启服务并回到位置保持。参数 · %1")
                                  .arg(root.controller.sdkDynamicsSummary)
                            color: root.theme.tertiaryText
                            elide: Text.ElideRight
                            font.family: root.theme.fontFamily
                            font.pixelSize: root.theme.typeCaption
                            ToolTip.visible: dynamicsHover.hovered && truncated
                            ToolTip.text: text
                            HoverHandler { id: dynamicsHover }
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
                        title: qsTr("预置动作")
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
                            color: root.theme.secondaryText
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
                            title: qsTr("示教与回放")
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: qsTr("采样率")
                                color: root.theme.secondaryText
                                font.family: root.theme.fontFamily
                                font.pixelSize: root.theme.typeLabel
                            }
                            AppSpinBox {
                                id: sampleHz
                                theme: root.theme
                                from: 1
                                to: 250
                                value: 50
                                editable: true
                            }
                            AppTextField {
                                id: recordingName
                                Layout.fillWidth: true
                                theme: root.theme
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
                                text: qsTr("零力录制")
                                enabled: root.controller.modeControlEnabled
                                onClicked: root.controller.startRecording(sampleHz.value)
                            }
                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                text: qsTr("停止保存")
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
                            AppSpinBox {
                                id: playbackSpeed
                                theme: root.theme
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
                                text: qsTr("回放")
                                enabled: root.controller.modeControlEnabled
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
                                enabled: root.controller.modeControlEnabled
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
                        title: qsTr("RGB-D 相机")
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
                            color: root.theme.mediaCanvas
                            border.width: 0
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
                                          ? qsTr("加载中…")
                                          : qsTr("暂无画面")
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
                                    text: qsTr("检查链路")
                                    enabled: !root.controller.cameraBusy
                                    onClicked: root.controller.queryCamera("camera_status")
                                }
                                AppButton {
                                    Layout.fillWidth: true
                                    theme: root.theme
                                    kind: "primary"
                                    text: qsTr("刷新")
                                    enabled: !root.controller.cameraBusy
                                    onClicked: root.controller.queryCamera("camera_capture")
                                }
                            }

                            AppButton {
                                Layout.fillWidth: true
                                theme: root.theme
                                text: qsTr("读取外参")
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

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }

        }
    }
}
