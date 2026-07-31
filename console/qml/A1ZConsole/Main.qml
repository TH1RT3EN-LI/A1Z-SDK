pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import A1ZConsole

ApplicationWindow {
    id: window

    required property var controller
    property string currentPage: "overview"
    property string manualSection: "movement"
    property string frameMode: "base"
    readonly property var appTheme: theme

    width: 1560
    height: 940
    minimumWidth: 1220
    minimumHeight: 760
    visible: true
    title: qsTr("A1Z Control Console")
    color: theme.canvas
    flags: Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint
           | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint
           | Qt.WindowCloseButtonHint

    function updateCameraPreviewActivity() {
        const foreground = window.active && window.visibility !== Window.Minimized
        const previewPage = window.currentPage === "overview"
                            || window.currentPage === "vision"
        window.controller.setCameraPreviewEnabled(
                    previewPage && foreground)
    }

    onActiveChanged: {
        if (!active)
            window.controller.neutralizeUi()
        window.updateCameraPreviewActivity()
    }
    onVisibilityChanged: window.updateCameraPreviewActivity()
    onCurrentPageChanged: window.updateCameraPreviewActivity()
    onClosing: function(close) {
        if (window.controller.closeBlocked) {
            close.accepted = false
            window.controller.explainCloseBlocked()
        }
    }
    Component.onCompleted: window.updateCameraPreviewActivity()

    Theme {
        id: theme
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.spacingM
        spacing: theme.spacingS

        ConsoleHeader {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            theme: window.appTheme
            controller: window.controller
            profileSwitchAllowed: !workspace.hasPendingDrafts
            profileSwitchBlockedText: qsTr("请先发送或放弃：%1").arg(
                                          workspace.pendingDraftSummary)
        }

        ConsoleFeedback {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            theme: window.appTheme
            controller: window.controller
        }

        ConsoleWorkspace {
            id: workspace

            Layout.fillWidth: true
            Layout.fillHeight: true
            theme: window.appTheme
            controller: window.controller
            currentPage: window.currentPage
            frameMode: window.frameMode
            manualSection: window.manualSection
            onPageRequested: function(route) {
                window.currentPage = route
            }
            onFrameModeRequested: function(mode) {
                window.frameMode = mode
            }
            onManualSectionRequested: function(section) {
                window.manualSection = section
            }
        }
    }
}
