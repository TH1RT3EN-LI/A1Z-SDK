pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Item {
    id: root
    objectName: "gripperControlPage"

    required property var theme
    required property var controller
    readonly property bool hasPendingDrafts: root.gripperTargetDirty
    property real gripperTargetDraft: 1.0
    property bool gripperDraftInitialized: false
    property bool gripperTargetDirty: false
    property bool gripperTargetStale: false
    property string gripperDraftProfile: ""
    readonly property bool modeStateConfirmed:
        root.controller.gripperModeState === "confirmed"

    function discardGripperDraft() {
        root.gripperTargetDirty = false
        root.gripperTargetStale = false
        root.syncGripperDraft()
    }

    function invalidateGripperState() {
        if (root.gripperTargetDirty)
            root.gripperTargetStale = true
        else
            root.gripperDraftInitialized = false
    }

    function syncGripperDraft() {
        if (root.gripperDraftProfile !== root.controller.profile) {
            root.gripperDraftProfile = root.controller.profile
            root.gripperDraftInitialized = false
            root.gripperTargetDirty = false
            root.gripperTargetStale = false
        }

        if (!root.modeStateConfirmed) {
            root.invalidateGripperState()
            return
        }

        const target = Number(root.controller.gripperTarget)
        if (root.gripperTargetDirty) {
            if (root.gripperTargetStale
                    || root.controller.commandBusy
                    || target < 0
                    || Math.abs(target - root.gripperTargetDraft) > 0.005) {
                return
            }
            root.gripperTargetDirty = false
            root.gripperTargetStale = false
        }

        if (target >= 0) {
            root.gripperTargetDraft = target
            root.gripperDraftInitialized = true
            root.gripperTargetStale = false
        } else if (root.controller.gripperMeasured >= 0) {
            root.gripperTargetDraft = Number(root.controller.gripperMeasured)
            root.gripperDraftInitialized = true
            root.gripperTargetStale = false
        } else if (!root.gripperTargetDirty) {
            root.gripperDraftInitialized = false
        }
    }

    PageScrollView {
        id: gripperScroll

        anchors.fill: parent

        ColumnLayout {
            width: gripperScroll.availableWidth
            spacing: root.theme.spacingM

            GripperModePanel {
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                modeState: root.controller.gripperModeState
                freeDrive: root.controller.gripperFreeDrive
                controlEnabled: root.controller.gripperModeControlEnabled
                draftPending: root.gripperTargetDirty
                onModeRequested: function(freeDrive) {
                    root.controller.setGripperFreeDrive(freeDrive)
                }
            }

            GripperOpeningPanel {
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                measured: root.controller.gripperMeasured
                targetDraft: root.gripperTargetDraft
                draftInitialized: root.gripperDraftInitialized
                draftDirty: root.gripperTargetDirty
                draftStale: root.gripperTargetStale
                editingEnabled: root.gripperDraftInitialized
                                && !root.gripperTargetStale
                                && root.modeStateConfirmed
                                && !root.controller.commandBusy
                                && !root.controller.taskBusy
                                && !root.controller.emergencyBusy
                                && !root.controller.recordingActive
                                && !root.controller.gripperFreeDrive
                submitEnabled: root.controller.gripperControlEnabled
                               && root.gripperDraftInitialized
                               && !root.gripperTargetStale
                               && root.gripperTargetDirty
                discardEnabled: !root.controller.commandBusy
                                && !root.controller.taskBusy
                onTargetMoved: function(value) {
                    root.gripperTargetDraft = value
                    root.gripperTargetDirty = true
                }
                onTargetRequested: function(value) {
                    root.controller.setGripper(value)
                }
                onDiscardRequested: root.discardGripperDraft()
            }

            GripperActionPanel {
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                controlEnabled: root.controller.gripperControlEnabled
                draftPending: root.gripperTargetDirty
                onCloseRequested: root.controller.graspClose()
                onReleaseRequested: root.controller.graspRelease()
            }
        }
    }

    Connections {
        target: root.controller

        function onStateChanged() {
            if (root.visible)
                root.syncGripperDraft()
        }

        function onGripperTelemetryChanged() {
            if (root.visible)
                root.syncGripperDraft()
        }

        function onTelemetryTimingChanged() {
            if (root.visible)
                root.syncGripperDraft()
        }

        function onGripperStateInvalidated() {
            root.invalidateGripperState()
        }
    }

    onVisibleChanged: {
        if (visible)
            root.syncGripperDraft()
    }

    Component.onCompleted: root.syncGripperDraft()
}
