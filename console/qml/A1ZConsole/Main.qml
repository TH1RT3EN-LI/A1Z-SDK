pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import A1ZConsole

ApplicationWindow {
    id: window

    required property var controller
    property int currentPage: 0
    property string frameMode: "base"
    readonly property var appTheme: theme

    width: 1560
    height: 940
    minimumWidth: 1220
    minimumHeight: 760
    visible: true
    title: qsTr("A1Z SDK Console")
    color: theme.canvas
    flags: Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint
           | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint
           | Qt.WindowCloseButtonHint

    onActiveChanged: {
        if (!active)
            window.controller.neutralizeUi()
    }
    onClosing: window.controller.neutralizeUi()
    onCurrentPageChanged: {
        window.controller.neutralizeUi()
        window.controller.setCameraPreviewEnabled(currentPage === 0 || currentPage === 3)
    }
    Component.onCompleted: window.controller.setCameraPreviewEnabled(
                               currentPage === 0 || currentPage === 3)

    Theme { id: theme }

    Rectangle {
        anchors.fill: parent
        color: theme.canvas
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.spacingM
        spacing: theme.spacingS

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            radius: theme.radiusCard
            color: theme.toolbar
            border.width: 0

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: theme.spacingL
                anchors.rightMargin: theme.spacingM
                spacing: theme.spacingS

                ColumnLayout {
                    Layout.preferredWidth: 168
                    spacing: 0
                    Text {
                        text: qsTr("A1Z Console")
                        color: theme.text
                        font.family: theme.fontFamily
                        font.pixelSize: theme.typeTitle
                        font.weight: Font.DemiBold
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 28
                    color: theme.borderStrong
                }

                Rectangle {
                    Layout.preferredWidth: 180
                    Layout.preferredHeight: 40
                    radius: theme.radiusControl + 2
                    color: theme.control

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 3
                        spacing: 3

                        AppButton {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            theme: window.appTheme
                            kind: window.controller.profile === "sim"
                                  ? "selected" : "quiet"
                            text: qsTr("SIM 仿真")
                            enabled: !window.controller.taskBusy
                                     && !window.controller.commandBusy
                            onClicked: window.controller.setProfile("sim")
                        }
                        AppButton {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            theme: window.appTheme
                            kind: window.controller.profile === "real"
                                  ? "selected" : "quiet"
                            text: qsTr("REAL 真机")
                            enabled: !window.controller.taskBusy
                                     && !window.controller.commandBusy
                            onClicked: window.controller.setProfile("real")
                        }
                    }
                }

                StatusPill {
                    theme: window.appTheme
                    text: !window.controller.connected ? qsTr("控制服务离线")
                          : !window.controller.backendMatched
                            ? qsTr("控制身份未通过")
                          : window.controller.faulted
                            ? qsTr("控制循环故障")
                          : !window.controller.robotRunning
                            ? qsTr("服务在线 · 控制停止")
                            : qsTr("%1运行中").arg(window.controller.backendLabel)
                    level: window.controller.connected
                           && window.controller.backendMatched
                           && window.controller.robotRunning
                           && !window.controller.faulted ? "ok" : "error"
                }
                StatusPill {
                    theme: window.appTheme
                    text: !window.controller.cameraBridgeOnline
                          ? qsTr("相机桥离线")
                          : window.controller.cameraReady
                            ? qsTr("RGB-D 在线")
                            : qsTr("相机桥在线 · 无帧")
                    level: window.controller.cameraReady ? "ok"
                           : window.controller.cameraBridgeOnline ? "warn" : "error"
                }
                StatusPill {
                    theme: window.appTheme
                    Layout.minimumWidth: 100
                    Layout.preferredWidth: 100
                    Layout.maximumWidth: 100
                    text: window.controller.telemetryAgeMs < 0 ? qsTr("无遥测")
                          : qsTr("%1 ms").arg(window.controller.telemetryAgeMs)
                    level: window.controller.telemetryFresh ? "ok" : "warn"
                }
                StatusPill {
                    theme: window.appTheme
                    text: qsTr("模式 · %1").arg(window.controller.controlModeLabel)
                }

                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 80
                    text: window.controller.commandBusy || window.controller.taskBusy
                            ? window.controller.statusText : ""
                    color: window.controller.commandBusy || window.controller.taskBusy
                           ? theme.secondaryText : theme.tertiaryText
                    elide: Text.ElideRight
                    font.family: theme.fontFamily
                    font.pixelSize: theme.typeCaption
                    ToolTip.visible: statusHover.hovered && truncated
                    ToolTip.text: text
                    HoverHandler { id: statusHover }
                }

                AppButton {
                    theme: window.appTheme
                    kind: "quiet"
                    text: qsTr("刷新")
                    enabled: !window.controller.commandBusy
                    onClicked: window.controller.refreshNow()
                }
            }
        }

        InlineBanner {
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? implicitHeight : 0
            visible: window.controller.lastError.length > 0
            theme: window.appTheme
            text: window.controller.lastError
            level: "error"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: theme.spacingS

            Rectangle {
                Layout.fillHeight: true
                Layout.preferredWidth: 190
                radius: theme.radiusPanel
                color: theme.sidebar
                border.width: 0

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: theme.spacingM
                    spacing: theme.spacingXs

                    Repeater {
                        model: [
                            { label: qsTr("运行总览"), icon: "activity" },
                            { label: qsTr("手动控制"), icon: "sliders" },
                            { label: qsTr("AnyGrasp"), icon: "target" },
                            { label: qsTr("SDK 功能"), icon: "command" },
                            { label: qsTr("诊断与日志"), icon: "waveform" }
                        ]

                        NavButton {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            theme: window.appTheme
                            text: modelData.label
                            iconName: modelData.icon
                            selected: window.currentPage === index
                            onClicked: window.currentPage = index
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 650
                currentIndex: window.currentPage

                DashboardPage {
                    theme: window.appTheme
                    controller: window.controller
                }
                ManualControlPage {
                    theme: window.appTheme
                    controller: window.controller
                    motionSpeed: safetyRail.speed
                    jointStepDeg: safetyRail.jointStep / 10.0
                    linearStepMm: safetyRail.linearStepMm
                    angularStepDeg: safetyRail.angularStepDeg / 10.0
                    frameMode: window.frameMode
                }
                AnyGraspPage {
                    theme: window.appTheme
                    controller: window.controller
                }
                SdkFunctionsPage {
                    theme: window.appTheme
                    controller: window.controller
                    motionSpeed: safetyRail.speed
                }
                DiagnosticsPage {
                    theme: window.appTheme
                    controller: window.controller
                }
            }

            SafetyRail {
                id: safetyRail
                Layout.fillHeight: true
                Layout.preferredWidth: 272
                Layout.maximumWidth: 290
                theme: window.appTheme
                controller: window.controller
                frameMode: window.frameMode
                onFrameModeRequested: function(mode) {
                    window.frameMode = mode
                }
            }
        }
    }
}
