pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    required property var theme
    required property var controller
    required property string currentPage
    required property string frameMode
    required property string manualSection
    readonly property bool armDraftPending: manualPage.armDraftPending
    readonly property bool gripperDraftPending: manualPage.gripperDraftPending
    readonly property bool configurationDraftPending: settingsPage.hasPendingDrafts
    readonly property bool hasPendingDrafts:
        root.armDraftPending
        || root.gripperDraftPending
        || root.configurationDraftPending
    readonly property string pendingDraftSummary: {
        const labels = []
        if (manualPage.armDraftPending)
            labels.push(qsTr("机械臂目标"))
        if (manualPage.gripperDraftPending)
            labels.push(qsTr("夹爪开度"))
        if (settingsPage.hasPendingDrafts)
            labels.push(qsTr("重力补偿系数"))
        return labels.join("、")
    }
    signal pageRequested(string route)
    signal frameModeRequested(string mode)
    signal manualSectionRequested(string section)

    function synchronizeDraftLocks() {
        root.controller.setDraftLocks(
                    root.armDraftPending,
                    root.gripperDraftPending,
                    root.configurationDraftPending)
    }

    onArmDraftPendingChanged: root.synchronizeDraftLocks()
    onGripperDraftPendingChanged: root.synchronizeDraftLocks()
    onConfigurationDraftPendingChanged: root.synchronizeDraftLocks()

    function pageIndex(route) {
        switch (route) {
        case "manual": return 1
        case "vision": return 2
        case "grasp": return 3
        case "teaching": return 4
        case "settings": return 5
        case "diagnostics": return 6
        default: return 0
        }
    }

    spacing: root.theme.spacingS

    ConsoleNavigation {
        Layout.fillHeight: true
        Layout.preferredWidth: 190
        theme: root.theme
        currentPage: root.currentPage
        onPageRequested: function(route) {
            root.pageRequested(route)
        }
    }

    StackLayout {
        objectName: "pageStack"
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumWidth: 650
        currentIndex: root.pageIndex(root.currentPage)

        DashboardPage {
            theme: root.theme
            controller: root.controller
        }

        ManualControlPage {
            id: manualPage

            theme: root.theme
            controller: root.controller
            currentSection: root.manualSection
            motionSpeed: safetyRail.speed
            jointStepDeg: safetyRail.jointStep / 10.0
            linearStepMm: safetyRail.linearStepMm
            angularStepDeg: safetyRail.angularStepDeg / 10.0
            frameMode: root.frameMode
            onSectionRequested: function(section) {
                root.manualSectionRequested(section)
            }
        }

        VisionPage {
            theme: root.theme
            controller: root.controller
        }

        GraspTaskPage {
            theme: root.theme
            controller: root.controller
            motionDraftPending:
                root.armDraftPending || root.gripperDraftPending
        }

        TeachingPage {
            theme: root.theme
            controller: root.controller
            motionDraftPending:
                root.armDraftPending || root.gripperDraftPending
        }

        DeviceSettingsPage {
            id: settingsPage

            theme: root.theme
            controller: root.controller
            armDraftPending: root.armDraftPending
            gripperDraftPending: root.gripperDraftPending
        }

        DiagnosticsPage {
            theme: root.theme
            controller: root.controller
            armDraftPending: root.armDraftPending
            gripperDraftPending: root.gripperDraftPending
            configurationDraftPending: root.configurationDraftPending
        }
    }

    SafetyRail {
        id: safetyRail

        Layout.fillHeight: true
        Layout.preferredWidth: root.currentPage === "manual"
                               && root.manualSection === "movement" ? 272 : 220
        Layout.maximumWidth: root.currentPage === "manual"
                             && root.manualSection === "movement" ? 290 : 220
        theme: root.theme
        controller: root.controller
        frameMode: root.frameMode
        showMotionSettings: root.currentPage === "manual"
                            && root.manualSection === "movement"
        armDraftPending: root.armDraftPending
        gripperDraftPending: root.gripperDraftPending
        configurationDraftPending: root.configurationDraftPending
        onFrameModeRequested: function(mode) {
            root.frameModeRequested(mode)
        }
    }

    Component.onCompleted: root.synchronizeDraftLocks()

}
