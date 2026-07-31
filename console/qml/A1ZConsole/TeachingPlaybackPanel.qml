pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

GridLayout {
    id: root
    objectName: "teachingPlaybackPanel"

    required property var theme
    required property var controller
    property string recordingDraftProfile: ""
    property bool motionDraftPending: false
    readonly property bool recordingOrphaned:
        root.controller.recordingState === "orphaned"
    readonly property string recordingStateLabel:
        root.controller.recordingState === "recording" ? qsTr("录制中")
        : root.controller.recordingState === "orphaned" ? qsTr("状态待确认")
        : root.controller.recordingState === "saved" ? qsTr("轨迹已保存")
        : root.controller.recordingState === "discarded" ? qsTr("会话已放弃")
        : qsTr("未录制")

    columns: 1
    columnSpacing: root.theme.spacingM
    rowSpacing: root.theme.spacingM

    function synchronizeRecordingDraft() {
        if (root.recordingDraftProfile === root.controller.profile)
            return
        root.recordingDraftProfile = root.controller.profile
        recordingName.text = root.controller.profile + "-teach.json"
    }

    GlassCard {
        Layout.fillWidth: true
        Layout.preferredHeight: 350
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

                StatusPill {
                    theme: root.theme
                    text: root.recordingStateLabel
                    level: root.recordingOrphaned ? "error"
                           : root.controller.recordingActive ? "warn" : "ok"
                }

                Text {
                    Layout.fillWidth: true
                    text: root.controller.recordingSummary
                    color: root.controller.recordingActive
                           ? root.theme.orange : root.theme.tertiaryText
                    elide: Text.ElideRight
                    font.family: root.theme.fontFamily
                    font.pixelSize: root.theme.typeCaption
                }
            }

            AppButton {
                Layout.fillWidth: true
                visible: root.controller.recordingRecoveryEnabled
                theme: root.theme
                kind: "danger"
                text: qsTr("放弃未保存会话并停止控制服务")
                onClicked: root.controller.discardDisconnectedRecording()
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
                    Accessible.name: qsTr("示教采样率")
                    enabled: !root.controller.recordingActive
                             && !root.controller.taskBusy
                }

                AppTextField {
                    id: recordingName

                    Layout.fillWidth: true
                    theme: root.theme
                    text: "sim-teach.json"
                    placeholderText: qsTr("轨迹文件名")
                    Accessible.name: qsTr("轨迹文件名")
                    enabled: root.controller.recordingActive
                             ? root.controller.recordingStopEnabled
                             : !root.controller.taskBusy
                }

                AppButton {
                    theme: root.theme
                    visible: !root.recordingOrphaned
                    kind: root.controller.recordingActive
                          ? "danger" : "primary"
                    text: root.controller.recordingActive
                          ? qsTr("停止并保存") : qsTr("开始零力示教")
                    enabled: root.controller.recordingActive
                             ? root.controller.recordingStopEnabled
                             : root.controller.recordingStartEnabled
                               && !root.motionDraftPending
                    onClicked: {
                        if (root.controller.recordingActive)
                            root.controller.stopRecording(recordingName.text)
                        else
                            root.controller.startRecording(sampleHz.value)
                    }
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
                    Accessible.name: qsTr("轨迹回放倍率")
                    enabled: root.controller.playbackEnabled
                             && !root.motionDraftPending
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
                    text: qsTr("回放当前配置轨迹")
                    enabled: root.controller.playbackEnabled
                             && !root.motionDraftPending
                    onClicked: root.controller.playRecording(
                                   recordingName.text,
                                   playbackSpeed.value / 10)
                }
            }

            Text {
                Layout.fillWidth: true
                text: root.motionDraftPending
                      ? qsTr("有未发送的机械臂或夹爪目标；开始示教和轨迹回放已锁定。")
                      : root.recordingOrphaned
                        ? qsTr("端点不可用不代表设备已经退出录制。恢复连接可重新确认状态；放弃会停止当前配置的控制服务，并丢弃未保存数据。")
                        : qsTr("开始后自动进入机械臂零力和夹爪自由拖动；停止保存后自动恢复位置保持和夹爪控制。轨迹按后端隔离，来源不一致时拒绝回放。")
                color: root.motionDraftPending || root.recordingOrphaned
                       ? root.theme.orange : root.theme.tertiaryText
                wrapMode: Text.WordWrap
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeCaption
            }
        }
    }

    Connections {
        target: root.controller

        function onStateChanged() {
            root.synchronizeRecordingDraft()
        }
    }

    Component.onCompleted: root.synchronizeRecordingDraft()
}
