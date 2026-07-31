pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Item {
    id: root
    objectName: "armControlPage"

    required property var theme
    required property var controller
    property real motionSpeed: 0.5
    property real jointStepDeg: 2.0
    property real linearStepMm: 10.0
    property real angularStepDeg: 5.0
    property string frameMode: "base"
    readonly property bool jointDraftInitialized:
        jointControl.jointDraftInitialized
    readonly property bool jointDraftDirty: jointControl.jointDraftDirty
    readonly property bool jointDraftValid: jointControl.jointDraftValid
    readonly property bool jointDraftStale: jointControl.jointDraftStale
    readonly property bool hasPendingDrafts: jointControl.draftPending

    function loadCurrentDrafts() {
        jointControl.loadCurrentDrafts()
    }

    function syncJointDrafts() {
        jointControl.syncJointDrafts()
    }

    function submitDrafts() {
        jointControl.submitDrafts()
    }

    function discardJointDraft() {
        jointControl.discardJointDraft()
    }

    function validateJointDrafts() {
        jointControl.validateJointDrafts()
    }

    PageScrollView {
        id: armScroll

        anchors.fill: parent

        ColumnLayout {
            width: armScroll.availableWidth
            spacing: root.theme.spacingM

            ArmModePanel {
                Layout.fillWidth: true
                Layout.preferredHeight: 155
                theme: root.theme
                controller: root.controller
                armDraftPending: root.jointDraftDirty
            }

            EndEffectorPosePanel {
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                controller: root.controller
            }

            JointControlPanel {
                id: jointControl

                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                controller: root.controller
                motionSpeed: root.motionSpeed
                jointStepDeg: root.jointStepDeg
            }

            CartesianControlPanel {
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                theme: root.theme
                controller: root.controller
                motionSpeed: root.motionSpeed
                linearStepMm: root.linearStepMm
                angularStepDeg: root.angularStepDeg
                frameMode: root.frameMode
                armDraftPending: root.jointDraftDirty
            }

            PresetMotionPanel {
                Layout.fillWidth: true
                Layout.preferredHeight: root.jointDraftDirty ? 210 : 190
                theme: root.theme
                controller: root.controller
                motionSpeed: root.motionSpeed
                armDraftPending: root.jointDraftDirty
            }
        }
    }
}
