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
    color: theme.windowBottom
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
        gradient: Gradient {
            GradientStop { position: 0.0; color: theme.windowTop }
            GradientStop { position: 1.0; color: theme.windowBottom }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.spacingM
        spacing: theme.spacingS

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 62
            radius: theme.radiusCard
            color: theme.toolbar
            border.color: theme.border
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: theme.spacingL
                anchors.rightMargin: theme.spacingM
                spacing: 9

                ColumnLayout {
                    Layout.preferredWidth: 190
                    spacing: 0
                    Text {
                        text: qsTr("A1Z SDK CONSOLE")
                        color: theme.text
                        font.family: theme.fontFamily
                        font.pixelSize: theme.typeTitle
                        font.weight: Font.Bold
                        font.letterSpacing: 0.8
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 28
                    color: theme.borderStrong
                }

                AppButton {
                    Layout.preferredWidth: 86
                    theme: window.appTheme
                    kind: window.controller.profile === "sim" ? "primary" : "secondary"
                    text: qsTr("SIM 仿真")
                    enabled: !window.controller.taskBusy && !window.controller.commandBusy
                    onClicked: window.controller.setProfile("sim")
                }
                AppButton {
                    Layout.preferredWidth: 86
                    theme: window.appTheme
                    kind: window.controller.profile === "real" ? "danger" : "secondary"
                    text: qsTr("REAL 真机")
                    enabled: !window.controller.taskBusy && !window.controller.commandBusy
                    onClicked: window.controller.setProfile("real")
                }

                StatusPill {
                    theme: window.appTheme
                    text: !window.controller.connected ? qsTr("控制服务离线")
                          : window.controller.backendMatched
                            ? qsTr("控制 %1 在线").arg(window.controller.backend)
                            : qsTr("控制身份未通过")
                    level: window.controller.connected && window.controller.backendMatched
                           ? "ok" : "error"
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
                    text: window.controller.telemetryAgeMs < 0 ? qsTr("无遥测")
                          : qsTr("%1 ms").arg(window.controller.telemetryAgeMs)
                    level: window.controller.telemetryFresh ? "ok" : "warn"
                }
                StatusPill {
                    theme: window.appTheme
                    text: window.controller.controlMode
                }

                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 80
                    text: window.controller.lastError.length > 0
                          ? window.controller.lastError
                          : window.controller.commandBusy || window.controller.taskBusy
                            ? window.controller.statusText : ""
                    color: window.controller.lastError.length > 0 ? theme.red
                           : window.controller.commandBusy || window.controller.taskBusy
                             ? theme.orange : theme.secondaryText
                    elide: Text.ElideRight
                    font.family: theme.fontFamily
                    font.pixelSize: theme.typeCaption
                    ToolTip.visible: statusHover.hovered && truncated
                    ToolTip.text: text
                    HoverHandler { id: statusHover }
                }

                AppButton {
                    theme: window.appTheme
                    text: qsTr("刷新")
                    enabled: !window.controller.commandBusy
                    onClicked: window.controller.refreshNow()
                }
            }
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
                border.color: theme.border
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: theme.spacingM
                    spacing: 7

                    Repeater {
                        model: [
                            { label: qsTr("运行总览"), glyph: "◈" },
                            { label: qsTr("手动控制"), glyph: "✣" },
                            { label: qsTr("AnyGrasp"), glyph: "◎" },
                            { label: qsTr("SDK 功能"), glyph: "◇" },
                            { label: qsTr("诊断与日志"), glyph: "≋" }
                        ]

                        NavButton {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            theme: window.appTheme
                            text: modelData.label
                            glyph: modelData.glyph
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
