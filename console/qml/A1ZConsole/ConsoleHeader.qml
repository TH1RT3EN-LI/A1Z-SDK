pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: root

    required property var theme
    required property var controller
    required property bool profileSwitchAllowed
    property string profileSwitchBlockedText: ""

    implicitHeight: 56
    radius: root.theme.radiusCard
    color: root.theme.toolbar

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: root.theme.spacingL
        anchors.rightMargin: root.theme.spacingM
        spacing: root.theme.spacingS

        Text {
            Layout.preferredWidth: 168
            text: qsTr("A1Z Console")
            color: root.theme.text
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeTitle
            font.weight: Font.DemiBold
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.preferredHeight: 28
            color: root.theme.borderStrong
        }

        Rectangle {
            Layout.preferredWidth: 180
            Layout.preferredHeight: 40
            radius: root.theme.radiusControl + 2
            color: root.theme.control

            RowLayout {
                anchors.fill: parent
                anchors.margins: 3
                spacing: 3

                AppButton {
                    objectName: "simProfileButton"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    theme: root.theme
                    kind: root.controller.profile === "sim"
                          ? "selected" : "quiet"
                    text: qsTr("SIM 仿真")
                    Accessible.role: Accessible.RadioButton
                    Accessible.checked: root.controller.profile === "sim"
                    enabled: root.controller.profileSwitchEnabled
                             && root.profileSwitchAllowed
                    ToolTip.visible: hovered && !root.profileSwitchAllowed
                    ToolTip.text: root.profileSwitchBlockedText
                    onClicked: root.controller.setProfile("sim")
                }

                AppButton {
                    objectName: "realProfileButton"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    theme: root.theme
                    kind: root.controller.profile === "real"
                          ? "selected" : "quiet"
                    text: qsTr("REAL 真机")
                    Accessible.role: Accessible.RadioButton
                    Accessible.checked: root.controller.profile === "real"
                    enabled: root.controller.profileSwitchEnabled
                             && root.profileSwitchAllowed
                    ToolTip.visible: hovered && !root.profileSwitchAllowed
                    ToolTip.text: root.profileSwitchBlockedText
                    onClicked: root.controller.setProfile("real")
                }
            }
        }

        StatusPill {
            objectName: "pendingDraftPill"
            visible: !root.profileSwitchAllowed
            theme: root.theme
            text: qsTr("有未处理草稿")
            level: "warn"
            ToolTip.visible: draftHover.hovered
            ToolTip.text: root.profileSwitchBlockedText

            HoverHandler {
                id: draftHover
            }
        }

        StatusPill {
            theme: root.theme
            text: !root.controller.connected ? qsTr("控制服务离线")
                  : !root.controller.backendMatched
                    ? qsTr("控制身份未通过")
                  : root.controller.faulted
                    ? qsTr("控制循环故障")
                  : !root.controller.robotRunning
                    ? qsTr("服务在线 · 控制停止")
                    : qsTr("%1运行中").arg(root.controller.backendLabel)
            level: root.controller.connected
                   && root.controller.backendMatched
                   && root.controller.robotRunning
                   && !root.controller.faulted ? "ok" : "error"
        }

        StatusPill {
            visible: root.width >= 1380
            theme: root.theme
            text: !root.controller.cameraBridgeOnline
                  ? qsTr("相机桥离线")
                  : root.controller.cameraReady
                    ? qsTr("RGB-D 在线")
                    : qsTr("相机桥在线 · 无帧")
            level: root.controller.cameraReady ? "ok"
                   : root.controller.cameraBridgeOnline ? "warn" : "error"
        }

        StatusPill {
            Layout.minimumWidth: 100
            Layout.preferredWidth: 100
            Layout.maximumWidth: 100
            theme: root.theme
            text: root.controller.telemetryAgeMs < 0 ? qsTr("无遥测")
                  : qsTr("%1 ms").arg(root.controller.telemetryAgeMs)
            level: root.controller.telemetryFresh ? "ok" : "warn"
        }

        StatusPill {
            theme: root.theme
            text: qsTr("模式 · %1").arg(root.controller.controlModeLabel)
        }

        StatusPill {
            visible: root.controller.recordingActive
            theme: root.theme
            text: root.controller.recordingState === "orphaned"
                  ? qsTr("示教状态待确认") : qsTr("示教录制中")
            level: root.controller.recordingState === "orphaned"
                   ? "error" : "warn"
        }

        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 80
            text: root.controller.commandBusy || root.controller.taskBusy
                  ? root.controller.statusText : ""
            color: root.controller.commandBusy || root.controller.taskBusy
                   ? root.theme.secondaryText : root.theme.tertiaryText
            elide: Text.ElideRight
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
            ToolTip.visible: statusHover.hovered && truncated
            ToolTip.text: text

            HoverHandler {
                id: statusHover
            }
        }

        AppButton {
            visible: root.controller.taskCancelable
            theme: root.theme
            kind: "danger"
            text: qsTr("中止任务")
            onClicked: root.controller.cancelTask()
        }

        AppButton {
            theme: root.theme
            kind: "quiet"
            text: qsTr("刷新")
            enabled: root.controller.telemetryRefreshEnabled
            onClicked: root.controller.refreshNow()
        }
    }
}
